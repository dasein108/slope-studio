# YouTube Channel Settings

Owner: CEO Operator

This document defines which YouTube channel or channels the company works on.
The Paperclip UI task for this is `Manage YouTube channel settings`.

## Current Default

```yaml
default_channel: pilot-channel
channels:
  - name: pilot-channel
    purpose: initial growth loop and cold-start subscriber experiments
    token_file: token_pilot-channel.json
    status: active
```

## Runtime Meaning

Slope Studio commands use the channel name:

```bash
studio marketing journal --channel pilot-channel
studio yt-channel --channel pilot-channel
studio run "<idea>" --publish-to youtube --privacy public --channel pilot-channel
```

The channel name maps to local OAuth token files such as:

```text
token_<channel>.json
```

Those token files are local secrets and should not be committed.

## Changing Channels From Paperclip

Comment on the channel settings task:

```text
Change request: add channel
Channel name:
Purpose:
Default? yes/no
Publishing privacy:
Constraints:
```

or:

```text
Change request: switch default channel
Old default:
New default:
Reason:
```

The owning agent should verify:

```bash
studio yt-channel --channel <channel>
studio marketing journal --channel <channel>
```

## Multi-Channel Policy

If more than one channel is active:

- Growth Lead maintains separate journal state per channel.
- Secretary reports each active channel separately.
- Budgets are configured per channel.
- Producer must verify the OAuth token before upload.
- Analytics & Learning must not compare channel portfolios as if they are one audience.
