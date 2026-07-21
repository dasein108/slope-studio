"""Generate a preview batch of grounded guerrilla comments — posts NOTHING.

Runs the real transcript-grounded pipeline (discover -> transcript -> topic ->
highlight -> compose(moment) -> grounded critic -> content rails) against the
most recent uploads of every active watchlist channel, lifting only the
90-minute age gate so a reviewable batch can be produced on demand. `post` is
never imported, so there is no code path to YouTube posting here.

Intended to run where YouTube is reachable (e.g. the deploy VPS). Emits the
batch as JSON on stdout and per-video fetch progress on stderr.

Usage: uv run --extra guerrilla python scripts/guerrilla_preview.py \
           --channel pilot-channel --target 10 --per-channel 4
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from studio.guerrilla import client as gc
from studio.guerrilla import (compose, critic, db, discover, highlight, rails,
                              topic, transcript, watchlist)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def fetch_transcript(conn, video_id: str, tries: int = 4):
    """Cache-first transcript fetch with paced retries. Never caches an empty
    result, so a transient proxy miss does not poison the cache for later runs."""
    row = conn.execute("SELECT segments FROM transcripts WHERE video_id=?",
                       (video_id,)).fetchone()
    if row:
        return transcript.cached(conn, video_id)
    for i in range(tries):
        segs = transcript.fetch(video_id)
        if segs:
            conn.execute(
                "INSERT OR REPLACE INTO transcripts (video_id, fetched_at, duration, segments) "
                "VALUES (?, ?, ?, ?)",
                (video_id, db.now_iso(), transcript.duration(segs),
                 json.dumps([[s.start, s.text] for s in segs])))
            conn.commit()
            return segs
        time.sleep(2.5 * (i + 1))
    return []


def excerpt_for(segments, moment) -> str:
    if moment is not None:
        return transcript.as_prompt(segments, moment.timestamp - 120, moment.timestamp + 120)
    return transcript.as_prompt(segments, 0.0, 300.0)


def run(channel: str, target: int, per_channel: int, cite_ts: bool = False) -> dict:
    conn = db.connect(channel)
    yt = gc.build(channel)
    proposals: list[dict] = []
    rejected: list[dict] = []

    for ch in watchlist.active(conn):
        if len(proposals) >= target:
            break
        playlist = ch["uploads_playlist"] or discover.uploads_playlist_id(yt, ch["channel_id"])
        if not playlist:
            continue
        uploads = discover.recent_uploads(yt, playlist, max_results=per_channel)
        stats = discover.video_stats(yt, [u["video_id"] for u in uploads])

        for u in uploads:
            if len(proposals) >= target:
                break
            st = stats.get(u["video_id"], {})
            if not st.get("comments_enabled", True):
                rejected.append({"title": u["title"], "why": "comments_disabled"})
                continue

            conn.execute(
                "INSERT OR IGNORE INTO videos (video_id, channel_id, title, description) "
                "VALUES (?, ?, ?, ?)",
                (u["video_id"], ch["channel_id"], u["title"], u["description"]))
            conn.commit()

            segments = fetch_transcript(conn, u["video_id"])
            if not segments:
                rejected.append({"title": u["title"], "why": "no_transcript"})
                continue
            log(f"  {ch['title']}: fetched {u['video_id']} ({len(segments)} segs)")

            excerpt0 = transcript.as_prompt(segments, 0.0, 300.0)
            t = topic.classify(u["title"], u["description"], transcript_excerpt=excerpt0)
            if not topic.is_clear(t):
                rejected.append({"title": u["title"], "why": f"unclear_topic({t.confidence})"})
                continue

            moment = highlight.best_moment(segments, u["title"])
            # match the live tick default: timestamp citation off (buggy timestamps +
            # bot-detectable "At 0:0X" template). The moment still drives composition.
            cite = bool(cite_ts) and moment is not None and highlight.should_cite(moment)
            excerpt = excerpt_for(segments, moment)

            variants = compose.variants(u["title"], t.summary, moment=moment, cite=cite)
            pairs = critic.ranked(variants, u["title"], t.summary, transcript_excerpt=excerpt)
            texts = [q["text"] for q in proposals]
            styles = [q["style"] for q in proposals][:5]

            winner = verdict = None
            why = "no_eligible_variant"
            for cand, v in pairs:
                if v.decision == "skip":
                    low = ",".join(k for k, s in v.breakdown.items() if s < 3)
                    why = f"critic:{v.score}({low})"
                    continue
                if rails.violates_denylist(cand.text):
                    why = f"denylist:{rails.violates_denylist(cand.text)}"
                    continue
                if rails.too_similar(cand.text, texts):
                    why = "near_duplicate"
                    continue
                if rails.repeats_opening(cand.text, texts):
                    why = "repeats_opening"
                    continue
                if rails.style_overused(cand.style_tag, styles):
                    why = f"style_overused:{cand.style_tag}"
                    continue
                if rails.bad_timestamp(cand.text, segments):
                    why = f"bad_timestamp:{rails.bad_timestamp(cand.text, segments)}"
                    continue
                winner, verdict = cand, v
                break

            if winner is None:
                rejected.append({"title": u["title"], "why": why})
                continue

            proposals.append({
                "channel": ch["title"],
                "video": u["title"],
                "url": f"https://youtu.be/{u['video_id']}",
                "views": st.get("views", 0),
                "comments_now": st.get("comments", 0),
                "topic": t.topic,
                "moment_ts": transcript.stamp(moment.timestamp) if moment else None,
                "moment_quote": moment.quote if moment else None,
                "citability": moment.citability if moment else None,
                "cited": cite,
                "style": winner.style_tag,
                "score": verdict.score,
                "grounded": verdict.breakdown.get("grounded"),
                "text": winner.text,
            })
            log(f"    -> proposed [{winner.style_tag} {verdict.score}] {winner.text[:60]!r}")

    return {"proposals": proposals, "rejected": rejected}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="pilot-channel")
    ap.add_argument("--target", type=int, default=10)
    ap.add_argument("--per-channel", type=int, default=4)
    ap.add_argument("--cite-timestamps", action="store_true", help="opt in to timestamp citation (default off)")
    args = ap.parse_args()
    print(json.dumps(run(args.channel, args.target, args.per_channel, args.cite_timestamps),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
