---
name: marketing-crosspost
description: >
  Use to take a channel's most successful YouTube Shorts (by measured virality) and
  cross-post the winners to TikTok as inbox drafts — never reposting the same video.
  Picks the top-N measured entries by percentile, reuses each run's finished master,
  uploads to the TikTok inbox, and stamps the journal. One lego-block of the growth loop;
  runs AFTER measure-learn has scored the portfolio. The operator finishes posting in-app.
---

# marketing-crosspost — winners → TikTok inbox

Recycle proven YouTube Shorts onto TikTok. Selection is deterministic (top virality);
the agent's job is to confirm setup, run it, and report.

## Preconditions
- The channel has **measured** entries (run `marketing-measure-learn` first — percentiles
  come from measurement). Cold-start channels with nothing measured have nothing to pick.
- A TikTok **sandbox** app exists with your account as a **target user**, env holds
  `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` / `TIKTOK_REDIRECT_URI`
  (`http://localhost:8721/callback`), and a token has been minted **once**:
  ```bash
  python scripts/tiktok_auth.py --channel <name>
  ```
  (writes `tiktok_token_<name>.json`, then auto-refreshes). Full setup:
  [`docs/40-publishing/tiktok.md`](../../../docs/40-publishing/tiktok.md). If the token is
  missing, `crosspost` errors telling you to run that command.

## Do this

1. **Preview the picks** (no upload, no spend):
   ```bash
   studio marketing crosspost --channel <name> --to tiktok --top 5 --dry-run
   ```
   Shows the ranked winners and any skips (`no 06_final.mp4 master` = that run was cleaned;
   crosspost only reuses the finished master, it never re-renders).
2. **Cross-post for real**:
   ```bash
   studio marketing crosspost --channel <name> --to tiktok --top 5
   ```
   Each winner uploads to the TikTok inbox; the journal entry is stamped `crossposts.tiktok`
   so it never reposts. Uploads can be slow (TikTok's CDN ~50 KB/s) — be patient. If you hit
   `spam_risk_too_many_pending_share`, post some pending drafts in the app first, then retry.
3. **Finish in-app** — open the **TikTok app** (mobile, as the target user) → **Inbox** →
   System notifications → each "video uploaded" draft → paste the caption (from the channel's
   `tiktok_captions.md` if present) → **Post**. (Inbox can't auto-publish public; that needs
   `video.publish` + TikTok's audit — see the doc.)

## Notes
- `--top` controls how many winners to push per run; raise it to drain the backlog of
  un-crossposted winners. Re-running is safe — already-posted entries are skipped via the
  `crossposts` stamp.
- Same `06_final.mp4` master YouTube got — 9:16 vertical MP4 is valid on both platforms,
  no conversion.
- This is the cross-post lego-block of the growth loop; the umbrella is
  [`marketing-guru`](../marketing-guru/SKILL.md). Memory model:
  [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
