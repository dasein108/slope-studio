#!/usr/bin/env python3
"""Paperclip stale-lock janitor.

Heartbeats are disabled on the Slope Studio org agents (token-bleed fix), so the
only thing that moves work is the assignment trigger. When an agent run dies
mid-task it leaves the issue with a live `executionRunId` but no `checkoutRunId`;
the assignee then hits a 409-on-own-checkout and the task strands in
`in_progress`/`in_review` forever with nothing to re-fire the trigger.

This janitor is a pure-mechanical sweep (no LLM): it finds stranded issues and
release→reassigns them to the same owner, which re-fires the assignment trigger
and wakes the agent. A per-issue retry cap stops a genuinely-broken task from
looping — after MAX_RETRIES it is left in place with an @operator comment.

Detection (ALL must hold):
  - status in {in_progress, in_review}
  - executionRunId set AND checkoutRunId is None   (dead run left a lock)
  - assignee set AND that agent's status == 'idle'  (nobody is actually working it)
  - updatedAt older than STALE_MIN minutes          (not just a brief gap)

Run:  .venv/bin/python scripts/paperclip_lock_janitor.py [--dry-run]
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys

import requests

BASE = os.environ.get("PAPERCLIP_BASE", "http://localhost:3100")
CID = os.environ.get("PAPERCLIP_CID", "e8c8d9b5-8bd9-4ee3-9515-9d32f7614e69")  # Slope Studio
STALE_MIN = int(os.environ.get("JANITOR_STALE_MIN", "30"))
MAX_RETRIES = int(os.environ.get("JANITOR_MAX_RETRIES", "3"))
ACTIVE_STATUSES = {"in_progress", "in_review"}
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "runs", "_marketing", ".lock_janitor_state.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "runs", "_marketing", "lock_janitor.log")
TIMEOUT = 15


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def log(msg: str) -> None:
    line = f"[{now_utc().isoformat(timespec='seconds')}] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def get(path: str):
    r = requests.get(BASE + path, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def parse_ts(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_state() -> dict:
    try:
        with open(STATE_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, STATE_PATH)


def unwrap(payload, *keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in keys:
            if isinstance(payload.get(k), list):
                return payload[k]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="detect and report, do not modify")
    args = ap.parse_args()
    mode = "DRY-RUN" if args.dry_run else "APPLY"

    try:
        agents = unwrap(get(f"/api/companies/{CID}/agents"), "agents", "data")
        issues = unwrap(get(f"/api/companies/{CID}/issues?limit=300"), "issues", "data")
    except requests.RequestException as e:
        log(f"ERROR sweep aborted — API unreachable: {e}")
        return 2

    status_by_agent = {a.get("id"): a.get("status") for a in agents}
    name_by_agent = {a.get("id"): a.get("name") for a in agents}
    state = load_state()
    cutoff = now_utc() - dt.timedelta(minutes=STALE_MIN)

    stranded = []
    for i in issues:
        if (i.get("status") or "").lower() not in ACTIVE_STATUSES:
            continue
        if not i.get("executionRunId") or i.get("checkoutRunId"):
            continue
        assignee = i.get("assigneeAgentId")
        if not assignee or status_by_agent.get(assignee) != "idle":
            continue
        upd = parse_ts(i.get("updatedAt"))
        if upd and upd > cutoff:
            continue  # touched recently — give it a chance
        stranded.append(i)

    if not stranded:
        log(f"{mode}: swept {len(issues)} issues — no stranded locks.")
        return 0

    for i in stranded:
        iid = i.get("id")
        assignee = i.get("assigneeAgentId")
        who = name_by_agent.get(assignee, assignee)
        title = (i.get("title") or "")[:60]
        st = state.get(iid, {"retries": 0})
        # reset the retry counter if the run lineage changed since we last acted
        if st.get("last_exec") != i.get("executionRunId"):
            st = {"retries": st.get("retries", 0)}
        retries = st.get("retries", 0)

        if retries >= MAX_RETRIES:
            log(f"{mode}: SKIP (retry cap {MAX_RETRIES}) {iid} '{title}' — leaving for human.")
            if not args.dry_run and not st.get("flagged"):
                try:
                    requests.post(f"{BASE}/api/issues/{iid}/comments", timeout=TIMEOUT, json={
                        "body": (f"🧹 Lock-janitor: released this stranded task {MAX_RETRIES}× and it keeps "
                                 f"dying mid-run. Not reassigning again — needs a human. @operator")})
                    st["flagged"] = True
                except requests.RequestException:
                    pass
            state[iid] = st
            continue

        log(f"{mode}: STRANDED {iid} '{title}' status={i.get('status')} owner={who} "
            f"execRun={i.get('executionRunId')} updated={i.get('updatedAt')} retries={retries}")
        if args.dry_run:
            continue
        try:
            requests.post(f"{BASE}/api/issues/{iid}/comments", timeout=TIMEOUT, json={
                "body": (f"🧹 Lock-janitor: dead run left a stale executionRunId "
                         f"(`{i.get('executionRunId')}`) with no checkout; agent **{who}** is idle and the "
                         f"task has been stranded >{STALE_MIN}m. Releasing lock and reassigning to re-fire the "
                         f"wake trigger (attempt {retries + 1}/{MAX_RETRIES}).")})
            requests.post(f"{BASE}/api/issues/{iid}/release", timeout=TIMEOUT).raise_for_status()
            requests.patch(f"{BASE}/api/issues/{iid}", timeout=TIMEOUT,
                           json={"status": i.get("status")}).raise_for_status()
            requests.patch(f"{BASE}/api/issues/{iid}", timeout=TIMEOUT,
                           json={"assigneeAgentId": assignee}).raise_for_status()
            log(f"APPLY: recovered {iid} → reassigned to {who}")
            st = {"retries": retries + 1, "last_exec": i.get("executionRunId"),
                  "last_action": now_utc().isoformat(timespec="seconds")}
            state[iid] = st
        except requests.RequestException as e:
            log(f"ERROR recovering {iid}: {e}")

    if not args.dry_run:
        # prune state for issues no longer active/stranded so retry counts don't linger
        active_ids = {i.get("id") for i in stranded}
        state = {k: v for k, v in state.items() if k in active_ids}
        save_state(state)
    log(f"{mode}: done — {len(stranded)} stranded handled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
