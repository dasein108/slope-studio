#!/usr/bin/env python
"""Channel-truth prune: enumerate ALL uploads on the channel via the YouTube Data
API and unlist any PUBLIC video that is >= MIN_AGE_H old with < MIN_VIEWS views.

Unlike prune_low_views.py this does NOT trust the marketing journal — it reads the
real privacyStatus + viewCount from YouTube, so it catches journal-desynced entries
and untracked duplicate uploads. Best-effort syncs the journal `unlisted` flag after.

Dry-run by default; pass --apply to actually unlist.
    python scripts/prune_channel.py --channel pilot-channel [--apply]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from studio.providers import analytics, publish as pub

MIN_VIEWS = 25
MIN_AGE_H = 24


def all_upload_ids(yt) -> list[str]:
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        resp = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token
        ).execute()
        ids += [it["contentDetails"]["videoId"] for it in resp.get("items", [])]
        token = resp.get("nextPageToken")
        if not token:
            return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="pilot-channel")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--min-views", type=int, default=MIN_VIEWS)
    ap.add_argument("--min-age-h", type=float, default=MIN_AGE_H)
    args = ap.parse_args()

    yt = analytics._yt(args.channel)
    ids = all_upload_ids(yt)
    now = datetime.now(timezone.utc)

    hits = []
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(
            part="snippet,status,statistics,contentDetails", id=",".join(ids[i:i + 50])
        ).execute()
        for it in resp.get("items", []):
            if it["status"].get("privacyStatus") != "public":
                continue
            views = int(it.get("statistics", {}).get("viewCount", 0))
            pub_at = it["snippet"].get("publishedAt", "")
            age_h = (now - datetime.fromisoformat(pub_at.replace("Z", "+00:00"))).total_seconds() / 3600
            # broken/stuck upload: zero-media (P0D) or never finished processing —
            # remove immediately regardless of views/age (dead public zombie).
            dur = it.get("contentDetails", {}).get("duration", "")
            broken = it["status"].get("uploadStatus") != "processed" or dur in ("P0D", "", None)
            if broken:
                hits.append((it["id"], "[STUCK] " + it["snippet"]["title"][:40], views, age_h))
            elif age_h >= args.min_age_h and views < args.min_views:
                hits.append((it["id"], it["snippet"]["title"][:48], views, age_h))

    hits.sort(key=lambda h: h[3])
    print(f"channel has {len(ids)} uploads; {len(hits)} public <{args.min_views}v & >={args.min_age_h}h old")
    unlisted_ids = []
    for vid, title, views, age_h in hits:
        tag = f"{vid} {views:>3}v {age_h/24:4.1f}d  {title}"
        if not args.apply:
            print(f"  [dry] would unlist  {tag}")
            continue
        try:
            pub.set_privacy(vid, "unlisted", args.channel)
            unlisted_ids.append(vid)
            print(f"  unlisted  {tag}")
        except Exception as ex:
            print(f"  FAILED    {tag}: {ex}")

    if unlisted_ids:
        # best-effort journal sync
        from studio.marketing import journal as mj, score as mscore
        j = mj.load(args.channel)
        touched = 0
        for e in j.entries:
            if e.video_id in unlisted_ids and not e.unlisted:
                e.unlisted = True
                touched += 1
        if touched:
            measured = j.measured()
            for x, p in zip(measured, mscore.relativize([x.virality for x in measured])):
                x.percentile = p
                x.outcome = mscore.outcome(p, j.in_cold_start)
            mj.save(j)
        print(f"done: {len(unlisted_ids)} unlisted ({touched} journal entries synced)")


if __name__ == "__main__":
    main()
