# Deploying to a Remote VPS

The transcript fetcher and the YouTube Data API both need reliable, unrestricted network access
to Google's endpoints, running frequently enough (every 20–40 minutes) that any network
instability shows up as missed ticks. If the machine you develop on can't guarantee that, run
the pipeline instead on **a VPS with clean, unrestricted internet access to YouTube** — a small,
cheap instance is enough, since the pipeline itself is mostly LLM calls and lightweight API
requests.

Everything below is driven by `scripts/remote/guerrilla.mk`, a self-contained Makefile that
deploys *only* what this pipeline needs — not the rest of the repository, which is much larger.

## Local is the source of truth

The important design point: **your local machine owns the state.** Every operation is the same
round-trip —

```
_push (code + secrets + db → server)  →  exec on server  →  _pull (db + logs → local)
```

The canonical SQLite database lives at `runs/_guerrilla/<channel>/guerrilla.db` on your machine.
Each operation checkpoints and pushes it up before running and pulls it back after, so the
server is effectively stateless compute. If the remote box is wiped (shared hosts get cleaned;
disks fail), the next operation re-pushes the code, secrets, and db and **self-heals** — you
never lose the watchlist, the posting history, or the circuit-breaker's memory.

The one rule this imposes: **all execution must go through the Makefile (or a local driver that
does the same push/pull).** Do not run a cron *on the server* that mutates the db directly — the
next local push would overwrite whatever it did. Schedule locally instead (see
[`operations.md`](operations.md#autonomous-scheduling)).

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

Every operation target wraps its command in `_push … exec … _pull`, so you never sync by hand:

| Target | What it does (all push-then-pull) |
|---|---|
| `tick` | one discover→…→post cycle on the server, then syncs the db back |
| `track` | refresh comment metrics + run the circuit breaker |
| `report` | print effectiveness by style tag + the switchback verdict |
| `resume` | clear a tripped circuit breaker |
| `preview` | run the review-batch runner (posts nothing), writing `batch.json`, and pull it back |
| `posted` | list every posted comment as a direct `youtube.com/watch?v=…&lc=…` link |
| `deploy` | full `_push` (code + secrets + db + `uv sync`) with no exec — run once after configuring the host, or to force a clean redeploy |
| `shell` | interactive SSH into the remote deploy directory |

Internally, `_push` and `_pull` are `.PHONY` helpers the targets call; you don't invoke them
directly. `_push` rsyncs an explicit allow-list (`studio/`, `scripts/guerrilla_preview.py`,
`pyproject.toml`, `uv.lock`, `README.md`) plus secrets and the db, then `uv sync`s; the exec line
is prefixed so that a failed run **still** triggers `_pull` and local never desyncs.

Overridable variables (pass as `VAR=value`, or set defaults in `guerrilla.local.mk`): `CHANNEL`
(default `pilot-channel`), `CAP` (daily cap, default 10), `MAX_AGE_MIN` (candidate age window in
minutes, default 7200 = 5 days), `TARGET` / `PER_CHANNEL` (preview batch sizing).

### Both extras are required on the remote

`_push` runs `uv sync --extra guerrilla --extra youtube` — `guerrilla` brings in
`youtube-transcript-api` (the transcript scraper) and `youtube` brings in
`google-api-python-client` (the Data API client). Missing either produces a `ModuleNotFoundError`
at runtime, so both are always installed.

## The preview batch runner (`scripts/guerrilla_preview.py`)

`make preview` runs this on the server. It exercises the real content pipeline —
`discover → transcript → topic → highlight → compose(moment) → grounded critic → content rails` —
against the most recent uploads on every active watchlist channel, but it never imports `post.py`,
so there is no code path to actually posting. It also lifts the normal 90-minute age gate so a
reviewable batch of meaningful size can be produced on demand rather than waiting for genuinely
fresh uploads.

Output is a JSON object with `proposals` (what would have been posted — style tag, score, the
grounding moment/quote) and `rejected` (what was filtered and why), pulled back to
`runs/_guerrilla_remote/batch.json`. Use it to sanity-check comment quality after any change to
the composer, critic, or rails — read every proposal before letting a live `tick` run.

## Walkthrough

```bash
# first time: configure the host, then a full push + dependency install
cp scripts/remote/guerrilla.local.mk.example scripts/remote/guerrilla.local.mk   # ...edit it...
make -f scripts/remote/guerrilla.mk deploy

# generate a review batch without posting anything (pulled back automatically)
make -f scripts/remote/guerrilla.mk preview
# read runs/_guerrilla_remote/batch.json — every proposal — before trusting a live tick

# run one live cycle (push → tick → pull)
make -f scripts/remote/guerrilla.mk tick

# see what's actually been posted
make -f scripts/remote/guerrilla.mk posted
```

For continuous operation, schedule the Makefile targets **from local** (not a server cron) — see
[`operations.md`](operations.md#autonomous-scheduling).

## The optional transcript proxy

If the VPS's own IP gets rate-limited or blocked by YouTube for caption scraping — this can happen
to datacenter IP ranges — route transcript fetches through an HTTP proxy by setting
`TRANSCRIPT_PROXY_URL` in your local `.env` (pushed to the remote on every `_push`):

```
TRANSCRIPT_PROXY_URL=http://user:pass@proxy-host:port
```

Left unset, `transcript.py` fetches directly, which is fine for a VPS with clean internet. When a
proxy is configured, the fetcher retries a few times per video — a proxied endpoint can hand out an
occasional rate-limited exit, and a retry usually lands a working one; a direct fetch doesn't
benefit from retrying a blocked IP, so it isn't retried the same way. See
[`architecture.md`](architecture.md#transcript-grounding-transcriptpy-highlightpy) for how this
fits the grounding pipeline.

## Secrets synced to the remote

`_push` sends these on every operation, chmod 600:

- `.env` — provider API keys (LLM, notification webhook, and `TRANSCRIPT_PROXY_URL` if used)
- `token_<channel>.json` — the OAuth token authorized with the `force-ssl` scope needed to post
- `client_secret.json` — the OAuth client used to refresh that token

They're real credentials — `guerrilla.mk` keeps them gitignored locally and only ever transfers
them to your own configured host. State (`db`, `logs`) flows *back* on `_pull`; secrets only flow
*up*.
