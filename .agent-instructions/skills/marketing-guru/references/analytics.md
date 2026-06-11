# YouTube analytics — scopes, metrics, quota

Code: `studio/providers/analytics.py`. Reuses the publishing OAuth token
(`token_<channel>.json`) via `studio.providers.publish._creds`.

## Two APIs, two scopes

| Data | API | Scope | Re-auth? |
|------|-----|-------|----------|
| views, likes, comment count, titles, publish date | YouTube **Data API v3** | `youtube.readonly` | **No** — publishing already granted it |
| comment text (threads) | YouTube **Data API v3** | `youtube.readonly` | No |
| **retention** (averageViewPercentage), **subscribersGained** | YouTube **Analytics API v2** | `yt-analytics.readonly` | **Yes, once** |

`measure` fetches retention/subs **best-effort**: if the token lacks
`yt-analytics.readonly`, those calls return `None`/`0` and the loop continues on velocity +
engagement. The composite score just omits the missing terms.

## Unlocking retention (optional, one-time)

1. In Google Cloud Console → the same OAuth consent screen used for publishing → **add the
   scope** `https://www.googleapis.com/auth/yt-analytics.readonly`. Enable the **YouTube
   Analytics API** in the API library.
2. Force a fresh consent so the token re-grants with the new scope:
   ```bash
   # delete the channel's token, then re-authorize (browser opens)
   rm token_<channel>.json        # or token.json for the default
   studio yt-channel --channel <channel>
   ```
   `analytics._analytics()` requests the superset (`publish.SCOPES + yt-analytics.readonly`)
   so the new token carries both upload and analytics rights.

Setup parallels the publish flow — see [`docs/40-publishing/youtube.md`](../../../docs/40-publishing/youtube.md).

## Quota

Both APIs share the Data-API daily quota (default 10,000 units/day). `videos.list` and
`commentThreads.list` are ~1–5 units each, so a few hundred videos/day is fine. Batch:
`video_stats` already requests up to 50 ids per call. If you 403 on quota, wait for the
Pacific-midnight reset or request more in Cloud Console.

## Metric meanings (what the loop reads)

- **views** — lifetime view count (Data API; near-real-time).
- **age_days** — derived from `publishedAt`; drives velocity. A video <2–3 days old has a
  noisy velocity — see `references/loop.md` on cadence.
- **averageViewPercentage** — % of the video the average viewer watched. The single best
  Shorts health signal; needs the analytics scope.
- **engagement** — `(likes + comments) / views`. Cheap to get, decent share proxy.
- **comments text** — qualitative feedback; `learn` feeds the top ones to the LLM to read
  sentiment and spot what resonated or annoyed.
