# Task: Bootstrap Paperclip Company For Slope Studio

## Status

Draft for approval. Do not apply yet.

## Objective

Create a new Paperclip company that runs Slope Studio as an observable organization with explicit roles and recurring workflows.

Primary goal:

> Unlock Youtube monetization

## Scope

- Create a portable Paperclip company package.
- Define all agents and reporting structure.
- Define recurring operating tasks from the current Slope Studio autopilot.
- Create or update the native Paperclip goal tree after import.
- Include a Secretary role that sends daily Telegram reports.
- Provide one command for dry-run and one command for approved import.
- Document how to install and run Paperclip.

## Non-Goals

- Do not install Paperclip.
- Do not start the Paperclip server.
- Do not import the company yet.
- Do not create live tasks in Paperclip yet.
- Do not commit changes unless explicitly asked.

## Proposed Acceptance Criteria

- `paperclip/README.md` explains install, startup, dry-run import, apply import, and Telegram setup.
- `paperclip/scripts/bootstrap_company.sh --dry-run` is the first command to preview import after Paperclip is running.
- `paperclip/scripts/bootstrap_company.sh --apply` imports the company only after approval.
- Every agent in the company package uses `codex_local` with a GPT model assignment.
- The company package contains a Secretary daily report routine.
- The package uses native Paperclip tasks/settings docs rather than company skills.
- The bootstrap creates parent goal `Unlock Youtube monetization` and child goals for `1000` subscribers, YPP traffic threshold, and YPP readiness checks.

## Open Questions For Approval

- Should the issue prefix be `SLOPE` or another prefix?
- Should the company name be `Slope Studio` or `Slope Studio Growth Company`?
- Should the company be imported as new, or merged into an existing Paperclip company?
- Which Telegram chat should receive Secretary reports?
