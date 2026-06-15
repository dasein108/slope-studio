---
schema: paperclip/v1
kind: goal
slug: unlock-youtube-monetization
title: Unlock Youtube monetization
status: planned
level: company
---

# Unlock Youtube monetization

Parent Paperclip goal for the Slope Studio company.

## Success Definition

Unlock full YouTube Partner Program monetization, including revenue sharing from
ads and YouTube Premium.

Full YPP monetization threshold:

- `subscribers`: 1000
- `valid_public_watch_hours_365d`: 4000
- OR `valid_public_shorts_views_90d`: 10000000

Earlier YPP access threshold for eligible countries/regions:

- `subscribers`: 500
- `valid_public_uploads_90d`: 3
- AND either `valid_public_watch_hours_365d`: 3000
- OR `valid_public_shorts_views_90d`: 3000000

## Readiness Requirements

Track these as explicit booleans:

- `country_region_ypp_available`: true
- `expanded_ypp_country_region_available`: true
- `channel_monetization_policies_followed`: true
- `active_community_guidelines_strikes`: 0
- `google_account_2_step_verification_enabled`: true
- `youtube_advanced_features_access`: true
- `adsense_for_youtube_ready_or_linked`: true
- `original_authentic_content_review`: pass

## Metric Rules

- Shorts Feed watch hours do not count toward the 4000 public watch hours threshold.
- Private, unlisted, deleted, and ad-campaign views do not count.
- Shorts views must be valid engaged views from public Shorts in the Shorts Feed.
- Keep uploading or posting at least once every 6 months to avoid inactivity risk.

## Operating Metrics

The company should track:

- current subscribers
- subscriber growth per video
- valid public uploads in the last 90 days
- valid public watch hours in the last 365 days
- valid public Shorts views in the last 90 days
- views, retention, CTR, title, traffic source, and subscriber conversion per video
- policy/compliance blockers
