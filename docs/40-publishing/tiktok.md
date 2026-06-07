# TikTok — Inbox Upload & Cross-Post Setup

The studio uploads finished masters to TikTok as **inbox drafts**: the video lands in your
TikTok app's notifications, and you open the app, add a caption, and tap **Post**. This
works with a **sandbox** app — no public audit, no tunnel.

Primary use: **cross-post your best YouTube Shorts to TikTok** (the `marketing-crosspost`
skill / `studio marketing crosspost`). The same `06_final.mp4` master YouTube got is valid
on TikTok — 9:16 vertical MP4, no re-encode.

## One-time setup (~15 min)

1. Create an app at <https://developers.tiktok.com/> → **Manage apps**.
2. Create/open the app's **Sandbox** and add **your TikTok account as a target user**.
   Sandbox needs no app review and **does not require** Terms/Privacy URLs or URL
   verification — that's only for production review (see *Going production* below).
3. Add **Login Kit** → **Desktop** tab → **Redirect URI**:
   ```
   http://localhost:8721/callback
   ```
   TikTok Desktop apps only accept localhost redirects — which is why login needs no tunnel.
4. Add **Content Posting API** → enable scope **`video.upload`** (inbox). Leave
   `video.publish` off (that's direct public posting — needs the audit).
5. Copy the sandbox **Client key** / **Client secret** into `.env`:
   ```
   TIKTOK_CLIENT_KEY=...
   TIKTOK_CLIENT_SECRET=...
   TIKTOK_REDIRECT_URI=http://localhost:8721/callback
   ```
   (`.env` is gitignored.)

## Mint the token (one-time)

```bash
python scripts/tiktok_auth.py --channel <name>
```
Runs a one-shot localhost catcher, opens TikTok consent (approve as your target user),
exchanges the code (PKCE), and writes `tiktok_token_<name>.json` (gitignored). After this it
**auto-refreshes** — access token ~24h, refresh ~365d, handled in `providers/publish.py`.

## Cross-post your top winners

```bash
# preview the ranked picks, upload nothing
studio marketing crosspost --channel <name> --to tiktok --top 5 --dry-run
# upload the top N measured winners not already on TikTok
studio marketing crosspost --channel <name> --to tiktok --top 5
```
Selection = highest `percentile` (then `virality`) over **measured** journal entries not
already stamped `crossposts.tiktok`. Each upload stamps the entry, so re-runs never repost.
A pick is skipped if its `06_final.mp4` master was cleaned — cross-post reuses the finished
master and never re-renders.

Standalone (one finished run): `studio publish <run_id> --target tiktok --channel <name>`.

## Finish posting — TikTok **mobile app**

Inbox uploads appear in the **phone app**, NOT TikTok Studio (web):
1. Open the TikTok app (logged in as your target user) → **Inbox** (💬, bottom-right).
2. Under **System notifications** → a "video uploaded — tap to edit and post" item.
3. Tap → add caption (see your channel's `tiktok_captions.md`) → **Post**.

## How it works (`providers/publish.py`)

- `_tiktok_inbox()` — `POST /v2/post/publish/inbox/video/init/` (FILE_UPLOAD; whole file in
  one chunk when ≤10 MB, else 5 MB chunks) → PUT the bytes (`Content-Range`, retried) →
  returns `publish_id`.
- `_tiktok_access_token()` — reads `tiktok_token_<channel>.json` and refreshes when expired.
  Uses `httpx` (the repo's core HTTP dep). Initial mint is `scripts/tiktok_auth.py`.

## Going production (only if you ever go public)

Sandbox covers personal cross-posting. To post on behalf of *other* users / go public you'd
submit the app for **production review**, which requires **always-on** Terms of Service and
Privacy Policy URLs (a tunnel to your laptop won't pass — reviewers need them reachable
anytime). These pages are published on GitHub Pages:
- `https://dasein108.github.io/slope-studio/tos.html`
- `https://dasein108.github.io/slope-studio/privacy.html`

Use those URLs in the app form, and host TikTok's URL-verification `tiktok<...>.txt` on the
same `gh-pages` branch. Public auto-posting additionally needs `video.publish` + the audit.

## Limits & gotchas

- **Inbox only** (`video.upload`). Public **direct-post** (`video.publish`) needs TikTok's
  app audit. Inbox + one in-app tap is the hands-off-ish path meanwhile.
- **`spam_risk_too_many_pending_share`**: TikTok caps how many *unposted* inbox drafts you
  can queue. If you hit it, post some pending drafts in the app, then upload more.
- **Slow upload**: TikTok's upload CDN can be ~50 KB/s; a 20 MB video can take several
  minutes. The chunked PUT + retry handles it — just be patient.
- **Token is per-channel** — `tiktok_token_<channel>.json`, like the YouTube tokens.
- Format is identical to a YouTube Short; a 181s+ video is "Short-ineligible" on YouTube but
  fine on TikTok.
