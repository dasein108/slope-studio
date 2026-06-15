# How Paperclip Controls The Company

Paperclip is the management surface. You steer the company by changing tasks,
comments, approvals, and assignments in the UI.

## Practical Controls

| What you want | What to do in Paperclip |
|---|---|
| Change what videos are made | Comment on an ideation or autopilot task and assign Growth Lead. |
| Make SEO the main focus | Comment on `Manage SEO and packaging policy`. |
| Change channel | Comment on `Manage YouTube channel settings`. |
| Lower or raise budget | Comment on `Tune autopilot settings`. |
| Pause publishing | Comment on `Tune autopilot settings` and set public approval required. |
| Review quality manually | Move production issue to `in_review` and assign QA / Critic. |
| Get daily summary | Ensure `Send daily Telegram company report` is active and env is configured. |
| Investigate failures | Assign Observability / Ops or create an incident task. |

## Expected Agent Behavior

Agents should not require you to edit files directly. They should:

1. Read your Paperclip comment.
2. Apply the change to the correct runtime source.
3. Comment with commands run and before/after values.
4. Create follow-up tasks if the change requires credentials, approvals, or manual setup.

## Paperclip Status Meaning

- `todo`: ready for an agent to pick up.
- `in_progress`: an agent is actively working.
- `in_review`: waiting for QA, CEO, or another reviewer.
- `blocked`: cannot proceed without a named unblocker.
- `done`: output exists and next owner is clear.
- `cancelled`: no longer part of the plan.

## Approval Use

Use approvals for:

- public publishing changes
- spend increases
- adding new channels
- changing Telegram destination
- new agents
- destructive operations
