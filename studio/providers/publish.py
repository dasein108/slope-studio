"""Publishing for stage 7. YouTube works for automation; TikTok is audit-gated.

Multi-channel: a Google account can own several channels (Brand Accounts). The OAuth
token is bound to ONE channel (the one picked in the browser consent). Use a named
`--channel` to keep a separate token per channel (token_<channel>.json) and verify
which channel a token points at before uploading.
"""

from __future__ import annotations

import time
from pathlib import Path

from studio.providers.base import GenResult

CLIENT_SECRET = "client_secret.json"  # repo root, gitignored
# upload = insert videos; readonly = confirm WHICH channel a token is bound to;
# force-ssl = manage videos already on the channel (e.g. flip privacy → unlist/retire an old
# version when a re-make replaces it). force-ssl is a superset of upload+readonly, but we list
# all three so the consent screen is explicit about what's granted.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def _token_path(channel: str = "") -> Path:
    return Path(f"token_{channel}.json" if channel else "token.json")


def _creds(channel: str = "", scopes: list[str] | None = None):
    """Authorized creds for a channel's token. `scopes` overrides the default upload
    set — marketing-guru passes a superset (adds yt-analytics.readonly) so the token
    re-grants the analytics scope on next consent."""
    import json

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    scopes = scopes or SCOPES
    tok = _token_path(channel)
    creds = Credentials.from_authorized_user_file(str(tok), scopes) if tok.exists() else None
    # The token's GRANTED scopes live in the file; from_authorized_user_file would otherwise
    # report whatever we *requested*, masking a missing grant. If a new scope (e.g.
    # force-ssl, added to retire old videos) isn't in the saved grant, force a full re-consent.
    granted = set(json.loads(tok.read_text()).get("scopes", [])) if tok.exists() else set()
    insufficient = not set(scopes).issubset(granted)
    if not creds or not creds.valid or insufficient:
        if creds and creds.expired and creds.refresh_token and not insufficient:
            creds.refresh(Request())
        else:
            if not Path(CLIENT_SECRET).exists():
                raise RuntimeError(f"missing {CLIENT_SECRET} (YouTube OAuth desktop client)")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, scopes)
            # the browser consent is where you PICK which channel/brand account to use.
            creds = flow.run_local_server(port=0,
                                          authorization_prompt_message="Pick the channel to authorize…")
        tok.write_text(creds.to_json())
    return creds


def channel_info(channel: str = "") -> dict:
    """Authorize (if needed) and return the bound channel's {title, id, url}."""
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=_creds(channel))
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        return {"title": "(no channel)", "id": "", "url": ""}
    it = items[0]
    return {"title": it["snippet"]["title"], "id": it["id"],
            "url": f"https://youtube.com/channel/{it['id']}"}


def set_privacy(video_id: str, privacy: str = "unlisted", channel: str = "") -> str:
    """Flip an existing video's privacy (public|unlisted|private). Needs the youtube.force-ssl
    scope — used to retire an old version when a re-make replaces it. Returns the new status."""
    from googleapiclient.discovery import build

    if privacy not in ("public", "unlisted", "private"):
        raise ValueError(f"privacy must be public|unlisted|private, got {privacy}")
    yt = build("youtube", "v3", credentials=_creds(channel))
    r = yt.videos().update(part="status", body={
        "id": video_id,
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }).execute()
    return r["status"]["privacyStatus"]


def publish(provider: str, video: Path, title: str, description: str,
            tags: list[str], privacy: str = "public", channel: str = "",
            thumbnail: Path | None = None) -> GenResult:
    t0 = time.time()
    if provider == "youtube":
        vid, ch = _youtube(video, title, description, tags, privacy, channel, thumbnail)
        note = f"https://youtube.com/watch?v={vid}  (channel: {ch})"
    elif provider == "tiktok":
        raise NotImplementedError(
            "TikTok Content Posting API forces SELF_ONLY + 5 users/24h until your "
            "app passes a ~2-4 week audit. See docs/06-stage-publish/README.md."
        )
    else:
        raise ValueError(f"unknown publish provider {provider}")
    return GenResult(path=video, latency_s=round(time.time() - t0, 2),
                     provider=provider, note=note)


def _youtube(video: Path, title: str, description: str, tags: list[str],
             privacy: str, channel: str, thumbnail: Path | None = None) -> tuple[str, str]:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _creds(channel)
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title, "description": description, "tags": tags,
                    "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True),
    )
    resp = req.execute()
    vid = resp["id"]
    # set the custom preview/thumbnail (requires a verified channel; ignore if refused).
    if thumbnail and thumbnail.exists():
        try:
            yt.thumbnails().set(
                videoId=vid, media_body=MediaFileUpload(str(thumbnail)),
            ).execute()
        except Exception:  # unverified channels can't set thumbnails — don't fail the upload
            pass
    return vid, resp.get("snippet", {}).get("channelTitle", "?")
