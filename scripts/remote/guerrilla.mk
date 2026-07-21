# Guerrilla remote deploy — run the transcript-grounded preview/tick on a VPS that has
# clean, unrestricted internet access to YouTube (Data API, transcripts, and the LLM
# providers). Useful when the machine you drive from cannot reach YouTube reliably.
#
# LOCAL IS THE SOURCE OF TRUTH. Every operation follows the same shape:
#
#     _push (code + secrets + db  ->  server)  ->  exec on server  ->  _pull (db + logs -> local)
#
# so the durable state (the SQLite db, logs) lives on your machine. If the remote box
# is wiped, the next operation re-pushes everything and self-heals. Do NOT also run a
# server-resident cron that mutates the db — it would fight the push. Schedule from
# LOCAL instead (a local cron running `make -f scripts/remote/guerrilla.mk tick`).
#
# Usage:
#   make -f scripts/remote/guerrilla.mk tick      # push -> tick -> pull
#   make -f scripts/remote/guerrilla.mk track     # push -> track (breaker) -> pull
#   make -f scripts/remote/guerrilla.mk preview    # push -> preview batch -> pull
#   make -f scripts/remote/guerrilla.mk report     # push -> report -> pull
#   make -f scripts/remote/guerrilla.mk posted     # push -> list posted links -> pull
#   make -f scripts/remote/guerrilla.mk deploy      # full push + install deps (no exec)
#   make -f scripts/remote/guerrilla.mk shell        # interactive ssh into the remote dir

# Operator-specific values (your VPS host, ssh key) live in the gitignored
# guerrilla.local.mk — copy guerrilla.local.mk.example to it and fill in. Never
# hardcode a host or key path here: this file is public.
SELF := $(firstword $(MAKEFILE_LIST))
-include $(dir $(SELF))guerrilla.local.mk

REMOTE_USER ?= root
REMOTE_HOST ?=
SSH_KEY     ?= ~/.ssh/id_ed25519
REMOTE_DIR  ?= /opt/slope-studio-guerrilla

CHANNEL     ?= pilot-channel
CAP         ?= 10
MAX_AGE_MIN ?= 7200
TARGET      ?= 10
PER_CHANNEL ?= 4

# Fail fast with a clear message if the operator hasn't configured their host.
ifeq ($(strip $(REMOTE_HOST)),)
$(error REMOTE_HOST is unset. Copy scripts/remote/guerrilla.local.mk.example to \
guerrilla.local.mk and set REMOTE_HOST + SSH_KEY (see docs/50-marketing/guerrilla/).)
endif

SSH   := ssh -i $(SSH_KEY) -o ConnectTimeout=20 $(REMOTE_USER)@$(REMOTE_HOST)
RSH   := ssh -i $(SSH_KEY) -o ConnectTimeout=20
RSYNC := rsync -az -e "$(RSH)"
DEST  := $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)
UV    := $$HOME/.local/bin/uv
RUN   := $$HOME/.local/bin/uv run --extra guerrilla --extra youtube

LOCAL_STATE   := runs/_guerrilla/$(CHANNEL)
REMOTE_RELDIR := runs/_guerrilla/$(CHANNEL)
LOCAL_RESULTS := runs/_guerrilla_remote
MFLAGS        := --no-print-directory -f $(SELF)
CKPT          := import sqlite3,os,sys; p=sys.argv[1]; os.path.exists(p) and sqlite3.connect(p).execute("PRAGMA wal_checkpoint(TRUNCATE)")

.PHONY: tick track preview report posted resume deploy shell _push _pull

# ---------------------------------------------------------------- state sync

# Push everything the remote needs to run, with LOCAL state as the source of truth:
# code (self-heals a wiped box), secrets, and the canonical SQLite db.
_push:
	@echo ">> push: code + secrets + db -> $(REMOTE_HOST)"
	@$(SSH) 'mkdir -p $(REMOTE_DIR)/$(REMOTE_RELDIR)'
	@$(RSYNC) --delete --relative --exclude='__pycache__' --exclude='*.pyc' \
		./studio ./scripts/guerrilla_preview.py ./pyproject.toml ./uv.lock ./README.md $(DEST)/
	@$(RSYNC) .env token_$(CHANNEL).json client_secret.json $(DEST)/ 2>/dev/null || true
	@$(SSH) 'cd $(REMOTE_DIR) && chmod 600 .env token_$(CHANNEL).json client_secret.json 2>/dev/null || true'
	@python3 -c '$(CKPT)' $(LOCAL_STATE)/guerrilla.db 2>/dev/null || true
	@test -f $(LOCAL_STATE)/guerrilla.db && $(RSYNC) $(LOCAL_STATE)/guerrilla.db $(DEST)/$(REMOTE_RELDIR)/ || true
	@$(SSH) 'rm -f $(REMOTE_DIR)/$(REMOTE_RELDIR)/guerrilla.db-wal $(REMOTE_DIR)/$(REMOTE_RELDIR)/guerrilla.db-shm'
	@$(SSH) 'cd $(REMOTE_DIR) && $(UV) sync --extra guerrilla --extra youtube 2>&1 | tail -1'

# Pull the mutated state back so local stays authoritative: the db (checkpointed
# first) plus logs. Runs even if the exec step failed.
_pull:
	@echo ">> pull: db + logs -> local"
	@$(SSH) 'cd $(REMOTE_DIR) && python3 -c "import sqlite3,os; p=\"$(REMOTE_RELDIR)/guerrilla.db\"; os.path.exists(p) and sqlite3.connect(p).execute(\"PRAGMA wal_checkpoint(TRUNCATE)\")" 2>/dev/null || true'
	@mkdir -p $(LOCAL_STATE) $(LOCAL_RESULTS)/logs
	@$(RSYNC) $(DEST)/$(REMOTE_RELDIR)/guerrilla.db $(LOCAL_STATE)/ 2>/dev/null || true
	@rm -f $(LOCAL_STATE)/guerrilla.db-wal $(LOCAL_STATE)/guerrilla.db-shm
	@$(RSYNC) $(DEST)/logs/ $(LOCAL_RESULTS)/logs/ 2>/dev/null || true

# ---------------------------------------------------------------- operations
# Each op: push state up, exec on the server, pull state back. The `-` on the exec
# line means a failed run still triggers _pull, so local never desyncs.

tick:
	@$(MAKE) $(MFLAGS) _push
	-@$(SSH) 'cd $(REMOTE_DIR) && $(RUN) studio guerrilla tick --channel $(CHANNEL) --cap $(CAP) --max-age-min $(MAX_AGE_MIN) 2>&1 | tail -4'
	@$(MAKE) $(MFLAGS) _pull

track:
	@$(MAKE) $(MFLAGS) _push
	-@$(SSH) 'cd $(REMOTE_DIR) && $(RUN) studio guerrilla track --channel $(CHANNEL) 2>&1 | tail -4'
	@$(MAKE) $(MFLAGS) _pull

report:
	@$(MAKE) $(MFLAGS) _push
	-@$(SSH) 'cd $(REMOTE_DIR) && $(RUN) studio guerrilla report --channel $(CHANNEL) 2>&1'
	@$(MAKE) $(MFLAGS) _pull

resume:
	@$(MAKE) $(MFLAGS) _push
	-@$(SSH) 'cd $(REMOTE_DIR) && $(RUN) studio guerrilla resume --channel $(CHANNEL) 2>&1 | tail -3'
	@$(MAKE) $(MFLAGS) _pull

preview:
	@$(MAKE) $(MFLAGS) _push
	-@$(SSH) 'cd $(REMOTE_DIR) && $(RUN) python scripts/guerrilla_preview.py --channel $(CHANNEL) --target $(TARGET) --per-channel $(PER_CHANNEL) > batch.json 2> batch.log; tail -4 batch.log'
	@$(RSYNC) $(DEST)/batch.json $(DEST)/batch.log $(LOCAL_RESULTS)/ 2>/dev/null || true
	@$(MAKE) $(MFLAGS) _pull

# Read-only, but still sync so the listing reflects (and preserves) canonical state.
posted:
	@$(MAKE) $(MFLAGS) _push
	-@$(SSH) 'cd $(REMOTE_DIR) && $(UV) run python -c "\
from studio.guerrilla import db; \
conn=db.connect(\"$(CHANNEL)\"); \
rows=list(conn.execute(\"SELECT c.posted_at,c.style_tag,c.video_id,c.comment_id,v.title FROM comments c JOIN videos v ON v.video_id=c.video_id ORDER BY c.posted_at\")); \
print(f\"{len(rows)} comment(s) posted\"); \
[print(f\"{r[0]}  [{r[1]}]  {r[4][:45]}\\n  https://www.youtube.com/watch?v={r[2]}&lc={r[3]}\") for r in rows]"'
	@$(MAKE) $(MFLAGS) _pull

# Full push + dependency install, no exec. Use once after configuring the host,
# or any time you want to force a clean redeploy.
deploy:
	@$(MAKE) $(MFLAGS) _push

shell:
	$(SSH) -t 'cd $(REMOTE_DIR) && exec bash -l'
