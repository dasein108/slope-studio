---
schema: agentcompanies/v1
kind: task
slug: daily-secretary-report
name: Send daily Telegram company report
project: slope-studio-company
assignee: secretary
recurring: true
priority: high
---

# Send Daily Telegram Company Report

Send a concise Telegram report covering company work, blockers, spend, published
videos, subscriber movement, and the next 24 hour plan.

Required runtime inputs:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `TELEGRAM_CHAT_ID` is accepted as a fallback alias.

Never expose secret values in comments, task bodies, or logs.
