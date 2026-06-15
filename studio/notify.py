"""Best-effort Telegram notifications for pipeline events.

Reuses the secretary agent's env convention so one bot/chat config drives both
the daily digest and per-event pings:
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHANNEL_ID  (TELEGRAM_CHAT_ID accepted as a fallback alias)

Never raises: a failed notification must not fail a publish. Returns True on a
sent message, False when unconfigured or on any error.
"""

from __future__ import annotations

from studio.config import env


def _target() -> tuple[str, str] | None:
    token = env("TELEGRAM_BOT_TOKEN")
    chat = env("TELEGRAM_CHANNEL_ID") or env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return None
    return token, chat


def telegram(text: str) -> bool:
    """Send `text` to the configured Telegram chat. Best-effort."""
    tc = _target()
    if not tc:
        return False
    token, chat = tc
    try:
        import requests

        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": text, "disable_web_page_preview": False},
            timeout=10,
        )
        return r.ok
    except Exception:
        return False


def published(title: str, url: str, channel: str = "", privacy: str = "public") -> bool:
    """Notify that a new video went live."""
    head = "🎬 Published" if privacy == "public" else f"🎬 Published ({privacy})"
    lines = [head]
    if title:
        lines.append(title)
    if channel:
        lines.append(f"channel: {channel}")
    if url:
        lines.append(url)
    return telegram("\n".join(lines))
