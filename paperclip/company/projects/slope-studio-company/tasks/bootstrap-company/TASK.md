---
schema: agentcompanies/v1
kind: task
slug: bootstrap-company
name: Bootstrap Slope Studio company
project: slope-studio-company
assignee: ceo-operator
recurring: false
priority: critical
---

# Bootstrap Slope Studio Company

Import the company package, verify all agents, verify settings tasks, verify
recurring tasks, and confirm Telegram report configuration.

Done means:

- company exists in Paperclip
- all agents use `codex_local`
- all agents have the expected GPT model assignment
- project exists
- settings tasks exist for channels, autopilot/budget policy, and SEO policy
- recurring routines are present
- native Paperclip goal tree exists with parent `Unlock Youtube monetization`
- Secretary can send a Telegram test report

Verify the native Paperclip goal tree through the Paperclip company goals API or
UI. Do not use the company-local Codex `goals_1.sqlite` file as the source of
truth; that database belongs to Codex's internal task-goal state, not the
Paperclip company goal tree.
