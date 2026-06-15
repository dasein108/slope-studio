---
schema: agentcompanies/v1
kind: task
slug: daily-org-autopilot
name: Run daily organization autopilot
project: slope-studio-company
assignee: growth-lead
recurring: true
priority: high
---

# Daily Organization Autopilot

Run the organizational version of the current Slope Studio growth loop.

This task must use company employees as the execution model. It may call Slope
Studio commands such as `studio marketing tick`, `studio marketing journal`, and
`studio marketing budget` only to read state, choose the next due action, or
persist a decision.

Do not run the old/internal autopilot end-to-end as a substitute for Paperclip
role ownership. If a legacy command would ideate, script, produce, QA, publish,
and learn in one pass, split that work into Paperclip tasks and handoffs.

Expected flow:

1. Inspect active backlog and marketing journal.
2. Inspect `Unlock Youtube monetization` goal progress: subscribers, 90-day uploads, 365-day watch hours, 90-day Shorts views, and readiness blockers.
3. Decide the next due action.
4. If producing, hand the selected growth/SEO bet to Screenwriter.
5. Screenwriter returns a script package to QA / Critic.
6. QA / Critic returns `PASS` or `FAIL`.
7. If `FAIL`, Screenwriter rewrites and resubmits.
8. If `PASS`, Producer creates the video and sends final output to QA / Critic.
9. QA / Critic returns final `PASS` or `FAIL`.
10. If final `PASS`, Producer publishes/links according to policy.
11. Track result in Paperclip and leave enough context for Secretary and Observability / Ops.

Recovery rule: if there are no open issues, inspect the most recent script and
QA gate tasks. If script QA passed and no Producer task exists, create the
Producer task immediately instead of ending idle.

Automation rule: comments do not move work by themselves. Each handoff must
create or update a native Paperclip issue assigned to the next owner. Paperclip's
assignment trigger enqueues the next agent's wake automatically; use `@`-mentions
only for comment-specific wakeups. Do not rely on a repo-level polling loop to
invoke agents.
