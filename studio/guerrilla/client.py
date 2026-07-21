"""The single point where a real YouTube API resource is constructed.

Every other module takes a `client` argument, so tests inject the fake in
`tests/fixtures/guerrilla/fake_yt.py` and never touch the network.
"""

from __future__ import annotations

# force-ssl is what permits writing comments on other people's videos.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def build(channel: str = ""):
    """Authorized YouTube Data API resource for `channel`'s token."""
    from googleapiclient.discovery import build as _build

    from studio.providers.publish import _creds

    return _build("youtube", "v3", credentials=_creds(channel, SCOPES))
