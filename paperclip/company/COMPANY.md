---
schema: agentcompanies/v1
kind: company
slug: slope-studio
name: Slope Studio
description: Organization-mode Slope Studio growth company for unlocking YouTube monetization.
---

# Slope Studio

Organization-mode Slope Studio growth company for unlocking YouTube monetization.

## Goal

Parent Paperclip goal: `Unlock Youtube monetization`.

Key child goals:

- `Reach 1000 subscribers`
- `Reach YPP traffic threshold`
- `Pass YPP readiness checks`

## Operating Model

This company uses native Paperclip agents, tasks, comments, approvals, and
recurring routines. It does not require company skills.

Slope Studio CLI commands are allowed as tooling for state, production, and
persistence. They must not replace Paperclip role ownership. The daily autopilot
delegates work to employees instead of running the legacy/internal autopilot
end-to-end.

Primary flow:

```text
Growth Lead -> Screenwriter -> QA / Critic -> Producer -> QA / Critic -> publish/link -> Analytics & Learning
```

Supporting roles:

- CEO / Operator owns approvals, budget, policy, and strategic decisions.
- Observability / Ops owns health, failures, missed routines, cost drift, and incidents.
- Secretary sends daily Telegram reports.

## Management Surface

Day-to-day control happens through Paperclip UI tasks:

- `Manage YouTube channel settings`
- `Tune autopilot settings, budgets, and publishing policy`
- `Manage SEO and packaging policy`
- `Run daily organization autopilot`
- `Send daily Telegram company report`
- `Weekly observability and cost review`

Use comments on those tasks to change behavior. Agents should apply changes to
the correct Slope Studio runtime source and report back with before/after values.
