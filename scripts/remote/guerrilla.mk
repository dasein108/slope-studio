# Guerrilla remote deploy — run the transcript-grounded preview/tick on a VPS that has
# clean, unrestricted internet access to YouTube (Data API, transcripts, and the LLM
# providers). Useful when the machine you drive from cannot reach YouTube reliably.
#
# Deploys ONLY the studio package + lockfile + this runner into an isolated remote dir,
# plus the secrets needed to authenticate. Never touches the rest of the box.
#
# Usage:
#   make -f scripts/remote/guerrilla.mk deploy      # push code + secrets, install deps
#   make -f scripts/remote/guerrilla.mk preview      # run the batch on the VPS
#   make -f scripts/remote/guerrilla.mk pull         # bring results (db + batch.json) back
#   make -f scripts/remote/guerrilla.mk all          # deploy + preview + pull
#   make -f scripts/remote/guerrilla.mk shell        # interactive ssh into the remote dir

# Operator-specific values (your VPS host, ssh key) live in the gitignored
# guerrilla.local.mk — copy guerrilla.local.mk.example to it and fill in. Never
# hardcode a host or key path here: this file is public.
-include $(dir $(lastword $(MAKEFILE_LIST)))guerrilla.local.mk

REMOTE_USER ?= root
REMOTE_HOST ?=
SSH_KEY     ?= ~/.ssh/id_ed25519
REMOTE_DIR  ?= /opt/slope-studio-guerrilla

CHANNEL     ?= pilot-channel
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
LOCAL_RESULTS := runs/_guerrilla_remote

.PHONY: all deploy sync-code sync-secrets setup preview pull shell clean-remote

all: deploy preview pull

deploy: sync-code sync-secrets setup

# Code: only what the guerrilla pipeline needs. The repo holds GB of video artifacts,
# so this is an explicit allow-list, not an exclude list.
sync-code:
	@echo ">> syncing code to $(REMOTE_DIR)"
	$(SSH) 'mkdir -p $(REMOTE_DIR)'
	$(RSYNC) --delete --relative --exclude='__pycache__' --exclude='*.pyc' \
		./studio ./scripts/guerrilla_preview.py ./pyproject.toml ./uv.lock \
		./README.md $(DEST)/

# Secrets: pushed separately, locked to 0600. These are real credentials.
sync-secrets:
	@echo ">> syncing secrets (0600)"
	$(RSYNC) .env token_$(CHANNEL).json client_secret.json $(DEST)/
	$(SSH) 'chmod 600 $(REMOTE_DIR)/.env $(REMOTE_DIR)/token_$(CHANNEL).json $(REMOTE_DIR)/client_secret.json'
	# carry the seeded watchlist db (checkpoint WAL first so it's all in the .db file)
	@python3 -c "import sqlite3,os; p='runs/_guerrilla/$(CHANNEL)/guerrilla.db'; \
os.path.exists(p) and sqlite3.connect(p).execute('PRAGMA wal_checkpoint(TRUNCATE)')" 2>/dev/null || true
	$(RSYNC) --relative ./runs/_guerrilla/$(CHANNEL)/guerrilla.db $(DEST)/ 2>/dev/null || true

setup:
	@echo ">> installing uv + deps on remote"
	$(SSH) 'command -v uv >/dev/null 2>&1 || command -v $(UV) >/dev/null 2>&1 || \
		curl -LsSf https://astral.sh/uv/install.sh | sh'
	$(SSH) 'cd $(REMOTE_DIR) && $(UV) sync --extra guerrilla --extra youtube'

preview:
	@echo ">> running grounded preview batch on remote"
	$(SSH) 'cd $(REMOTE_DIR) && $(UV) run --extra guerrilla --extra youtube python scripts/guerrilla_preview.py \
		--channel $(CHANNEL) --target $(TARGET) --per-channel $(PER_CHANNEL) \
		> batch.json 2> batch.log; echo "exit=$$?"; tail -5 batch.log'

pull:
	@echo ">> pulling results into $(LOCAL_RESULTS)"
	mkdir -p $(LOCAL_RESULTS)
	$(RSYNC) $(DEST)/batch.json $(DEST)/batch.log $(LOCAL_RESULTS)/
	$(RSYNC) $(DEST)/runs/_guerrilla/ $(LOCAL_RESULTS)/db/ 2>/dev/null || true
	@echo ">> proposals:" && python3 -c "import json;d=json.load(open('$(LOCAL_RESULTS)/batch.json'));print(len(d['proposals']),'proposed,',len(d['rejected']),'rejected')" 2>/dev/null || true

shell:
	$(SSH) -t 'cd $(REMOTE_DIR) && exec bash -l'

# List every comment the bot has actually posted, as direct YouTube links.
posted:
	@$(SSH) 'cd $(REMOTE_DIR) && $(UV) run python -c "\
from studio.guerrilla import db; \
conn=db.connect(\"$(CHANNEL)\"); \
rows=list(conn.execute(\"SELECT c.posted_at,c.style_tag,c.video_id,c.comment_id,v.title FROM comments c JOIN videos v ON v.video_id=c.video_id ORDER BY c.posted_at\")); \
print(f\"{len(rows)} comment(s) posted\"); \
[print(f\"{r[0]}  [{r[1]}]  {r[4][:45]}\\n  https://www.youtube.com/watch?v={r[2]}&lc={r[3]}\") for r in rows]"'
