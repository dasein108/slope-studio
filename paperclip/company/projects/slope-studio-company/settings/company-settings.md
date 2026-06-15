# Company Settings

These settings are meant to be changed through native Paperclip work:

1. Open the relevant settings task in the Paperclip UI.
2. Comment with the requested change.
3. Assign it to the owning agent.
4. The agent updates the actual Slope Studio source of truth when needed.
5. The agent comments with exactly what changed and how to verify it.

Paperclip is the management interface. Slope Studio remains the execution engine.

## Where Changes Take Effect

| Setting | UI task | Owner | Runtime source of truth |
|---|---|---|---|
| YouTube channels | Manage YouTube channel settings | CEO Operator | channel name and `token_<channel>.json` |
| Budgets | Tune autopilot settings | Growth Lead | `studio marketing budget` / journal config |
| Videos per day | Tune autopilot settings | Growth Lead | `runs/_marketing/<channel>/journal.json` loop config |
| Maturation window | Tune autopilot settings | Analytics & Learning | journal loop config |
| Publish approval policy | Tune autopilot settings | CEO Operator | Paperclip approval policy and task comments |
| SEO policy | Manage SEO and packaging policy | Growth Lead | metadata instructions and per-video publishing tasks |
| Daily Telegram report | Send daily Telegram company report | Secretary | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` or `TELEGRAM_CHAT_ID`, report task |

## How You Influence The Company

Use Paperclip comments like this:

```text
Change request:
Apply to:
Reason:
Constraints:
Success metric:
```

Examples:

```text
Change request: Make SEO the main optimization focus for the next 14 days.
Apply to: all new videos on pilot-channel.
Reason: Subscriber conversion is weak.
Constraints: keep max 1 public upload/day.
Success metric: higher search impressions and subscriber conversion.
```

```text
Change request: Reduce production budget to $0.60/video.
Apply to: pilot-channel.
Reason: cold-start exploration should stay cheap.
Constraints: keep audio local/synth.
Success metric: at least 10 deployed tests under budget.
```

## Native Paperclip Control Model

You do not need to edit YAML after import for day-to-day control.

- Use tasks to request changes.
- Use comments to set intent.
- Use approvals to gate spend or publishing.
- Use dashboard to see blocked work.
- Use recurring tasks for daily autopilot, daily Secretary reports, and weekly observability.

Agents should translate your Paperclip comments into CLI changes and report back
with the exact command or file they changed.
