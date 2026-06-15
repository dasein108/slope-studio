# SEO And Packaging Policy

Owner: Growth Lead

This is the main controllable growth lever from Paperclip. Use the `Manage SEO
and packaging policy` task to change title, description, keywords, thumbnail,
and upload packaging rules without changing the whole company.

## Current SEO Priority

```yaml
seo_priority: main
goal: unlock YouTube monetization, not just views

## Monetization Metrics

Optimize SEO and packaging against:

- `1000` subscribers for full YPP monetization
- `4000` valid public watch hours in the last `365` days
- OR `10000000` valid public Shorts views in the last `90` days
- earlier access checkpoint: `500` subscribers, `3` valid public uploads in `90` days, and either `3000` valid public watch hours in `365` days or `3000000` valid public Shorts views in `90` days

Subscriber conversion remains the main quality signal. Empty reach is not enough.
title_policy: searchable curiosity gap
description_policy: concise summary, keywords, and channel promise
tags_policy: theme keywords plus audience intent keywords
thumbnail_policy: required for landscape/long-form, optional for Shorts
hook_policy: first 0-3 seconds must match title promise
```

## SEO Inputs Per Video

Growth Lead should require these before a bet goes to Screenwriter and Producer:

- target keyword or search phrase
- title candidate
- 0-3 second hook
- description angle
- tags
- audience intent
- thumbnail/cover decision
- how the video should convert viewers to subscribers

## Metadata Commands

```bash
studio metadata <run_id>
cat runs/<run_id>/06_final.json
```

Publishing:

```bash
studio publish <run_id> --target youtube --privacy <privacy> --channel <channel>
```

## SEO Change Requests From Paperclip

Comment on the SEO policy task:

```text
Change request:
Apply to:
Keyword/theme:
Title rule:
Description rule:
Tags:
Thumbnail rule:
Success metric:
```

Examples:

```text
Change request: make SEO the main focus.
Apply to: next 10 videos on pilot-channel.
Keyword/theme: searchable science and history questions.
Title rule: exact question or named phenomenon in title.
Description rule: first sentence answers the search intent.
Tags: include broad niche, specific topic, and format tags.
Thumbnail rule: no custom thumbnail for Shorts; first frame must visually match title.
Success metric: search impressions, CTR, subscriber conversion.
```

```text
Change request: test contrarian titles.
Apply to: 3 exploration videos.
Title rule: "Why <common belief> is wrong" when the script genuinely supports it.
Success metric: P75 view velocity without retention collapse.
```

## Packaging Quality Gate

Block publishing if:

- title promises something the script does not answer
- title is vague or generic
- description has no searchable terms
- tags do not match the actual video
- hook and title conflict
- thumbnail/first frame misleads

## Learning SEO Results

Analytics & Learning should include SEO observations in learning:

- title style
- keyword/theme
- traffic source when available
- CTR/search impressions when available
- subscriber conversion
- retention after first 30 seconds

Persist durable conclusions through:

```bash
studio marketing strategy --channel <channel> --note <entry_id>="<SEO learning>"
```
