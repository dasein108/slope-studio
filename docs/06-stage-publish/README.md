# Stage 7 — Publish (YouTube Shorts / TikTok)

Optional final stage. **The hardest constraint in the whole studio lives here.** YouTube is automation-friendly; TikTok is audit-gated.

(Stage 6 "Save" is documented separately in [`save.md`](save.md).)

## YouTube Shorts — permissive ✅ for automation

Use the **YouTube Data API v3** `videos.insert` (resumable upload).
- A video becomes a **Short** automatically when it's vertical (9:16) and ≤3 min — no special endpoint. Adding `#Shorts` to title/description helps classification.
- **Auth:** OAuth 2.0 (user consent), refresh token stored for unattended uploads.
- **Quota:** default **10,000 units/day**; `videos.insert` costs **~1600 units** → **~6 uploads/day** per project by default. Request a quota increase for more. 🔶
- **Status:** can upload as `private`/`unlisted`/`public` freely (no audit gate like TikTok).
- Caveat: API-uploaded videos may default to **private** until your API project completes Google's OAuth verification/audit for unverified apps with sensitive scopes — but unverified apps can still upload (with a warning screen) for testing. For public automated upload at scale, complete OAuth verification. 🔶

```python
# pseudo
from googleapiclient.discovery import build
yt = build("youtube", "v3", credentials=creds)
req = yt.videos().insert(
    part="snippet,status",
    body={"snippet": {"title": "...#Shorts", "description": "...", "tags": [...]},
          "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}},
    media_body=MediaFileUpload("06_final.mp4", chunksize=-1, resumable=True))
```

## TikTok — audit-gated ⚠️ (verified hard constraint)

TikTok **Content Posting API**, **Direct Post** flow (all ✅ verified):
1. `POST /v2/post/publish/video/init/` — requires **`video.publish`** scope. Provide source: `PULL_FROM_URL` (TikTok fetches from your server) or `FILE_UPLOAD` (chunked upload from device).
2. Upload chunks (FILE_UPLOAD) or TikTok pulls (PULL_FROM_URL).
3. Poll status.

**The blockers (verified):**
- **Unaudited clients can only post `SELF_ONLY` (private)** — public attempts return `unaudited_client_can_only_post_to_private_accounts`. ✅
- **Unaudited clients: max 5 users / 24h window.** ✅
- **Audit takes ~2-4 weeks.** ✅
- A user can *manually* flip a private post to public afterward — but that defeats full automation. ✅

**Implication:** true automated *public* TikTok posting is impossible until you pass TikTok's app audit. Options:
- **YouTube-first:** automate Shorts; treat TikTok as manual or post-audit.
- **Audit path:** submit your app for audit early (2-4 wk lead time), meet content-sharing guidelines.
- **Third-party posting APIs** (upload-post.com, postproxy, Blotato, etc. 🔶) — they hold the audited app and resell posting; adds cost + dependency + ToS risk. Verify each before relying.

## Instagram Reels (bonus) 🔶
Graph API supports Reels publishing for Business/Creator accounts via container + publish endpoints; rate-limited (~25-50 posts/day). Similar OAuth + review requirements as other Meta APIs.

## Recommendation
- Ship **YouTube Data API** publishing first (works for automation today; mind the 6-uploads/day quota and OAuth verification for public-at-scale).
- For TikTok: build the Direct Post integration but **default to `SELF_ONLY`** and surface a "needs audit for public" flag; pursue the audit if TikTok is a priority.
- Keep publish stage **optional + idempotent** (record video IDs in `07_publish.json`; never double-post).

## CLI
```
studio publish --in runs/<id>/06_final.mp4 --meta runs/<id>/06_final.json \
  --target youtube --privacy public
studio publish --in runs/<id>/06_final.mp4 --target tiktok --privacy self_only
```
