# Deploying to a Remote VPS

The transcript fetcher and the YouTube Data API both need reliable, unrestricted network access
to Google's endpoints, running frequently enough (every 20–40 minutes) that any network
instability shows up as missed ticks. If the machine you develop on can't guarantee that, run
the pipeline instead on **a VPS with clean, unrestricted internet access to YouTube** — a small,
cheap instance is enough, since the pipeline itself is mostly LLM calls and lightweight API
requests.

Everything below is driven by `scripts/remote/guerrilla.mk`, a self-contained Makefile that
deploys *only* what this pipeline needs — not the rest of the repository, which is much larger.

## One-time local config

The Makefile reads your VPS host, SSH key, and remote directory from a gitignored local file so
none of that ever enters version control:

```bash
cp scripts/remote/guerrilla.local.mk.example scripts/remote/guerrilla.local.mk
```

Edit it:

```make
REMOTE_USER := root
REMOTE_HOST := <your-vps-ip-or-hostname>
SSH_KEY     := ~/.ssh/<your-deploy-key>
REMOTE_DIR  := /opt/slope-studio-guerrilla
```

`guerrilla.mk` includes this file automatically (`-include`) and fails fast with a clear message
if `REMOTE_HOST` is still unset. `guerrilla.local.mk` is gitignored — never hardcode a host or
key path in the tracked `guerrilla.mk` itself.

## Makefile targets

Run everything from the repo root:

```bash
make -f scripts/remote/guerrilla.mk <target> [VAR=value]
```

| Target | What it does |
|---|---|
| `deploy` | `sync-code` + `sync-secrets` + `setup`, in that order — full first-time or after-dependency-change deploy |
| `sync-code` | rsync only `studio/`, `scripts/guerrilla_preview.py`, `pyproject.toml`, `uv.lock`, `README.md` — an explicit allow-list, since the rest of the repo holds gigabytes of video artifacts this pipeline doesn't need |
| `sync-secrets` | rsync `.env`, `token_<channel>.json`, `client_secret.json` to the remote, chmod 600; also checkpoints and syncs the local watchlist DB (`runs/_guerrilla/<channel>/guerrilla.db`) if one exists, so the remote starts from your seeded watchlist rather than empty |
| `setup` | installs `uv` on the remote if missing, then `uv sync --extra guerrilla --extra youtube` |
| `preview` | runs `scripts/guerrilla_preview.py` on the remote — a review batch that posts nothing (see below) — writing `batch.json` |
| `pull` | rsyncs `batch.json`, `batch.log`, and the remote DB back into `runs/_guerrilla_remote/` locally, and prints the proposed/rejected counts |
| `all` | `deploy` + `preview` + `pull` |
| `shell` | interactive SSH into the remote deploy directory |
| `posted` | lists every comment the bot has actually posted, as direct `youtube.com/watch?v=...&lc=...` links, by querying the remote DB over SSH |

Overridable variables (pass as `VAR=value` on the command line, or set defaults in
`guerrilla.local.mk`): `CHANNEL` (which `token_<channel>.json` / watchlist to deploy — default
`pilot-channel`), `TARGET` (how many proposals `preview` should aim for — default 10),
`PER_CHANNEL` (how many recent uploads per watchlist channel `preview` inspects — default 4).

### Both extras are required on the remote

`setup` installs both `guerrilla` (which brings in `youtube-transcript-api`, the transcript
scraper) and `youtube` (which brings in `google-api-python-client`, the Data API client). Missing
either one produces a `ModuleNotFoundError` at runtime — always deploy with both, even if you
only intend to run part of the pipeline.

## The preview batch runner (`scripts/guerrilla_preview.py`)

`make preview` runs this script on the remote. It exercises the real content pipeline —
`discover → transcript → topic → highlight → compose(moment) → grounded critic → content rails`
— against the most recent uploads on every active watchlist channel, but it never imports
`post.py`, so there is no code path to actually posting a comment. It also lifts the normal
90-minute age gate so a reviewable batch of a meaningful size can be produced on demand rather
than waiting for genuinely fresh uploads.

Output is a JSON object with `proposals` (what would have been posted, including the style tag,
score, and the grounding moment/quote) and `rejected` (what was filtered and why) on stdout, with
per-video fetch progress logged to stderr. Use it to sanity-check comment quality after any
change to the composer, critic, or rails — read every proposal before letting a live tick run
with the same code.

## Deploy walkthrough

```bash
# first time
cp scripts/remote/guerrilla.local.mk.example scripts/remote/guerrilla.local.mk
# ...edit REMOTE_HOST / SSH_KEY...
make -f scripts/remote/guerrilla.mk deploy

# generate a review batch without posting anything
make -f scripts/remote/guerrilla.mk preview
make -f scripts/remote/guerrilla.mk pull
# review runs/_guerrilla_remote/batch.json — every proposal, before trusting a live tick

# after a code change, redeploy just the code (no dependency changes)
make -f scripts/remote/guerrilla.mk sync-code

# see what's actually been posted
make -f scripts/remote/guerrilla.mk posted

# poke around interactively
make -f scripts/remote/guerrilla.mk shell
```

For running `tick`/`track` continuously once you trust the output, schedule them on the remote
the same way described in [`operations.md`](operations.md#autonomous-cron-setup) — cron or a
systemd timer inside `REMOTE_DIR`, invoking `uv run --extra guerrilla --extra youtube studio
guerrilla tick ...` / `... track ...` directly rather than through the Makefile (the Makefile's
`preview`/`pull` round-trip is for review batches, not the live loop).

## The optional transcript proxy

If the VPS's own IP gets rate-limited or blocked by YouTube for caption scraping — this can
happen to datacenter IP ranges independent of anything else about the setup — route transcript
fetches through an HTTP proxy by setting `TRANSCRIPT_PROXY_URL` in the remote's `.env` (synced
by `sync-secrets`):

```
TRANSCRIPT_PROXY_URL=http://user:pass@proxy-host:port
```

Left unset, `transcript.py` fetches directly with no proxy, which is fine for a VPS with clean
internet access. When a proxy is configured, the fetcher also retries a few times per video — a
proxied endpoint can hand out an occasional rate-limited exit, and a retry usually lands a
working one; a direct fetch doesn't benefit from retrying a blocked IP, so it isn't retried the
same way. See [`architecture.md`](architecture.md#transcript-grounding-transcriptpy-highlightpy)
for how this fits into the grounding pipeline.

## Secrets synced to the remote

`sync-secrets` pushes, chmod 600:

- `.env` — provider API keys (LLM, TTS/image providers if configured, notification webhook,
  and `TRANSCRIPT_PROXY_URL` if you're using one)
- `token_<channel>.json` — the OAuth token authorized with the `force-ssl` scope needed to post
  comments
- `client_secret.json` — the OAuth client used to refresh that token

These are real credentials — `guerrilla.mk` is written to sync them separately from code
(`sync-code` never touches them) and the target chmods them to owner-only immediately after
transfer.
