# TikTok cross-post — design

Date: 2026-06-07

## Goal

Take the most successful YouTube Shorts (by measured virality) and cross-post them
to TikTok as **inbox drafts**, never re-posting the same video twice. A skill drives
the flow hands-off (operator just taps "publish" in the TikTok app per draft).

## Scope (v1)

- TikTok **inbox upload** (FILE_UPLOAD, chunked) — works with an unaudited app in
  sandbox/test mode. NOT direct-public-post (that needs the ~2-4wk TikTok audit).
- Source = the same `06_final.mp4` master YouTube gets. 9:16 vertical MP4 H.264/AAC
  is valid on both platforms → zero re-encode, no new render path.
- Selection = **auto top-N** by `percentile` (fallback `virality`) over measured
  journal entries not yet cross-posted.
- Dedup = stamp the journal `Entry`. One stamp = never reposted.

### Out of scope

Direct public auto-publish (audit-gated), TikTok analytics back into the loop,
Instagram. Inbox draft only.

## Design

### 1. Provider — `studio/providers/publish.py`
- `_tiktok_creds(channel)` — TikTok Login Kit OAuth. Env `TIKTOK_CLIENT_KEY` /
  `TIKTOK_CLIENT_SECRET`. Token cached at `tiktok_token_<channel>.json` (mirrors the
  YouTube `token_<channel>.json` pattern; gitignored). Refresh access token on expiry.
- `_tiktok_inbox(video, channel)` — `POST /v2/post/publish/inbox/video/init/` with
  FILE_UPLOAD source (`video_size`, `chunk_size`, `total_chunk_count`) → returns
  `publish_id` + `upload_url`; PUT the bytes (chunked, `Content-Range`); return
  `publish_id`. Best-effort `/v2/post/publish/status/fetch/` poll for a note.
- `publish()` dispatch: `provider == "tiktok"` → `_tiktok_inbox` (replaces the current
  `NotImplementedError`). Returns `GenResult(note="tiktok inbox: <publish_id> — open the
  app to finish posting")`. Direct-post stays a documented future branch.

### 2. Dedup ledger — `studio/marketing/journal.py`
- Add `crossposts: dict[str, str] = {}` to `Entry` (e.g. `{"tiktok": "<iso>|<publish_id>"}`).
- Cross-post skips any entry where `"tiktok" in crossposts`. No new files; lives in the
  per-channel journal.

### 3. Selection (auto top-N)
- Candidates: `status == "measured"` AND `run_id` set AND `"tiktok" not in crossposts`.
- Sort `percentile` desc (fallback `virality` desc). Take top N.
- **Master guard:** skip + warn if `runs/<run_id>/06_final.mp4` missing (old runs may be
  cleaned). Cross-post only READS the master, never re-renders → no AI-clip-overwrite risk.

### 4. CLI — `studio marketing crosspost`
`studio marketing crosspost <channel> --to tiktok --top 3 [--dry-run]`
- `--dry-run`: print ranked picks + skip reasons, upload nothing.
- live: per pick → `pub.publish("tiktok", master, title, desc, tags, channel=channel)` →
  on success stamp `entry.crossposts["tiktok"]` + `mj.save(j)`. Report inbox publish_ids.

### 5. Skill — `marketing-crosspost` (marketing-guru lego-block)
Operator wrapper: confirm TikTok creds present, run the crosspost CLI, summarize what
landed in the inbox, remind to open the TikTok app and tap publish per draft. Linked
from the marketing-guru umbrella + skill map.

### 6. Docs
- `docs/40-publishing/tiktok.md` — OAuth app setup, sandbox test-user, inbox vs
  direct-post, audit path.
- Update `docs/40-publishing/` README pointer, `CLAUDE.md` stage-7 row + marketing map,
  marketing-guru skill map.

## Known gotchas captured
- Unaudited app: target TikTok account must be added as a test user in the dev portal;
  inbox upload then works. Public direct-post still gated by audit.
- TikTok access token ~24h, refresh ~365d — refresh like the Google flow.
- Never re-render on crosspost; reuse `06_final.mp4` only.
