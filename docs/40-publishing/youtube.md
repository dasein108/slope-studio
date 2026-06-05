# YouTube Shorts — Auto-Publish Setup & Run

End-to-end: idea → uploaded public Short. The studio generates title/description/tags;
you do a one-time Google OAuth setup; then `studio run … --publish-to youtube` uploads.

## What the studio generates (no setup needed)

- **Stage `metadata`** (`studio/stages/metadata.py`) SEO-polishes:
  - `title` — hook, ≤100 chars, ends with `#Shorts`
  - `description` — hook + payoff + CTA + hashtags
  - `tags` — 10–15 keyword tags
- Written to `runs/<id>/06_final.json`; `studio publish` uploads with them.
- With an LLM key it's optimized; without one it derives solid metadata from the
  script deterministically. Run standalone: `studio metadata <id> [--provider gpt-4o-mini]`.

A video becomes a **Short** automatically when it's vertical (9:16) and ≤3 min — the
pipeline already outputs 1080×1920; `#Shorts` in the title reinforces it.

## One-time Google setup (you do this — ~20 min)

1. **Install deps:** `uv pip install -e ".[youtube]"`
2. **Cloud project:** [console.cloud.google.com](https://console.cloud.google.com) → create a project.
3. **Enable API:** APIs & Services → Library → enable **YouTube Data API v3**.
4. **OAuth consent screen:** External; fill app name/email; add scope
   `…/auth/youtube.upload`; add your Google account under **Test users**.
5. **Credentials:** Create Credentials → **OAuth client ID** → type **Desktop app** →
   download JSON → save as **`client_secret.json`** in the repo root (gitignored).
6. **First run authorizes:** the first `studio publish` opens a browser → approve →
   a refresh token is cached to **`token.json`**. All later uploads are unattended.

## Publish

```bash
# whole pipeline, then upload public:
studio run "your idea" --tier cheap --publish-to youtube --privacy public

# or publish an existing finished run:
studio metadata <id>                       # refresh title/desc/tags (optional)
studio publish  <id> --target youtube --privacy public
# receipt (video id + URL) written to runs/<id>/07_publish.json
```

`--privacy`: `public` · `unlisted` · `private`.

## Multiple channels (Brand Accounts)

A Google account can own several channels. The OAuth token is bound to the channel you
pick in the **browser consent chooser**. To manage several safely, use named tokens:

```bash
# authorize + VERIFY which channel a token points at (browser the first time):
studio yt-channel --channel science      # -> token_science.json -> "My Science Channel"
studio yt-channel --channel gaming       # -> token_gaming.json  -> "My Gaming Channel"

# publish to a specific channel:
studio publish elnino --target youtube --privacy public --channel science
studio run "..." --publish-to youtube --channel science
```

- `--channel NAME` uses `token_<NAME>.json`; omit it for the default `token.json`.
- On first auth for a channel, **pick that channel/Brand Account in the browser**.
- **Always `studio yt-channel --channel NAME` first** to confirm the bound channel
  before uploading — it prints the channel title + URL. (Uses the `youtube.readonly`
  scope; no upload.)
- All `token*.json` are gitignored.

## Constraints (know these)

- **Quota:** 10,000 units/day; `videos.insert` ≈ **1,600 units** → **~6 uploads/day**
  by default. Request more in the Cloud console if you scale.
- **Public at scale:** test users can upload public immediately. To remove the
  "unverified app" screen for a wider audience, complete Google's OAuth app
  verification (one-time review). Not needed for personal/test use.
- **Auth files are secrets:** `client_secret.json` and `token.json` are gitignored —
  never commit them.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `missing client_secret.json` | Do step 5; place it in the repo root. |
| browser doesn't open / headless | Run once on a desktop to mint `token.json`, then copy it over. |
| `quotaExceeded` | Hit the daily cap (~6 uploads) — wait or request more quota. |
| video not classified as Short | Ensure 9:16 + ≤3 min (pipeline already does) and `#Shorts` in title. |
| 403 on insert | Account not added as Test user, or consent scope missing. |
| **403 access_denied "app being tested / developer-approved testers"** | OAuth consent screen is in **Testing** mode. Add your login email under **OAuth consent screen → Test users**. Add the channel **owner** email (not the Brand Account name). |
| auth stops working after ~a week | Testing-mode refresh tokens expire in **7 days**. Re-run `studio yt-channel`, or **Publish app → In production** (click through the unverified-app warning as the owner). |

## TikTok note

TikTok auto-publish is **private-only until a 2–4 week app audit** (verified in
[`../20-research/findings.md`](../20-research/findings.md)). YouTube is the
automation-friendly path today.
