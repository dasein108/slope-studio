"""Publishing for stage 7. YouTube auto-publishes; TikTok uploads to the inbox.

Multi-channel: a Google account can own several channels (Brand Accounts). The OAuth
token is bound to ONE channel (the one picked in the browser consent). Use a named
`--channel` to keep a separate token per channel (token_<channel>.json) and verify
which channel a token points at before uploading.

TikTok: inbox upload (FILE_UPLOAD, chunked). The video lands in the creator's TikTok
notifications/drafts and they finish posting in-app — this works with an UNAUDITED app
(sandbox/test users), unlike direct public posting which needs the ~2-4 week audit.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from studio.providers.base import GenResult

CLIENT_SECRET = "client_secret.json"  # repo root, gitignored
# readonly lets us confirm WHICH channel a token is bound to before uploading.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _token_path(channel: str = "") -> Path:
    return Path(f"token_{channel}.json" if channel else "token.json")


def _creds(channel: str = "", scopes: list[str] | None = None):
    """Authorized creds for a channel's token. `scopes` overrides the default upload
    set — marketing-guru passes a superset (adds yt-analytics.readonly) so the token
    re-grants the analytics scope on next consent."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    scopes = scopes or SCOPES
    tok = _token_path(channel)
    creds = Credentials.from_authorized_user_file(str(tok), scopes) if tok.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
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


def publish(provider: str, video: Path, title: str, description: str,
            tags: list[str], privacy: str = "public", channel: str = "",
            thumbnail: Path | None = None) -> GenResult:
    t0 = time.time()
    if provider == "youtube":
        vid, ch = _youtube(video, title, description, tags, privacy, channel, thumbnail)
        note = f"https://youtube.com/watch?v={vid}  (channel: {ch})"
    elif provider == "tiktok":
        publish_id = _tiktok_inbox(video, channel)
        note = f"tiktok inbox: {publish_id} — open the TikTok app to finish posting"
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


# --------------------------------------------------------------------------- tiktok
TIKTOK_API = "https://open.tiktokapis.com"
_TIKTOK_CHUNK = 5 * 1024 * 1024        # 5 MB = TikTok min chunk; used to split bigger files


def _tiktok_token_path(channel: str = "") -> Path:
    return Path(f"tiktok_token_{channel}.json" if channel else "tiktok_token.json")


def _tiktok_access_token(channel: str = "") -> str:
    """Return a valid TikTok access token, refreshing it if expired. Mint the first token
    with `python scripts/tiktok_auth.py --channel <channel>` (cached at
    tiktok_token_<channel>.json, gitignored)."""
    from studio import config

    key = config.env("TIKTOK_CLIENT_KEY")
    secret = config.env("TIKTOK_CLIENT_SECRET")
    if not key or not secret:
        raise RuntimeError("set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET (TikTok dev app)")

    tok = _tiktok_token_path(channel)
    if not tok.exists():
        raise RuntimeError(
            f"no TikTok token — mint one with: python scripts/tiktok_auth.py --channel {channel}")
    data = json.loads(tok.read_text())
    now = time.time()
    if data.get("expires_at", 0) > now + 60:
        return data["access_token"]
    if not data.get("refresh_token"):
        raise RuntimeError("TikTok token expired without a refresh_token — re-run scripts/tiktok_auth.py")

    resp = httpx.post(
        f"{TIKTOK_API}/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"client_key": key, "client_secret": secret,
              "grant_type": "refresh_token", "refresh_token": data["refresh_token"]},
        timeout=30,
    ).json()
    if "access_token" not in resp:
        raise RuntimeError(f"TikTok token refresh failed: {resp}")
    resp["expires_at"] = now + int(resp.get("expires_in", 86400))
    tok.write_text(json.dumps(resp, indent=2))
    return resp["access_token"]


def _tiktok_inbox(video: Path, channel: str = "") -> str:
    """Upload a local video to the TikTok inbox (FILE_UPLOAD, chunked). Returns the
    publish_id. The creator finishes posting in the TikTok app."""
    token = _tiktok_access_token(channel)
    size = video.stat().st_size
    # TikTok rule: when total_chunk_count == 1, chunk_size MUST equal video_size. So only
    # multi-chunk once the file is big enough for ≥2 full chunks; smaller files go whole.
    if size < 2 * _TIKTOK_CHUNK:
        chunk, total_chunks = size, 1
    else:
        chunk = _TIKTOK_CHUNK
        total_chunks = size // chunk  # final PUT absorbs the remainder

    init = httpx.post(
        f"{TIKTOK_API}/v2/post/publish/inbox/video/init/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                              "chunk_size": chunk, "total_chunk_count": total_chunks}},
        timeout=30,
    ).json()
    if init.get("error", {}).get("code") not in ("ok", None):
        raise RuntimeError(f"TikTok init failed: {init['error']}")
    data = init["data"]
    publish_id, upload_url = data["publish_id"], data["upload_url"]

    timeout = httpx.Timeout(connect=30.0, read=120.0, write=600.0, pool=30.0)
    with video.open("rb") as fh:
        for i in range(total_chunks):
            start = i * chunk
            # last chunk grabs the rest (handles non-divisible sizes)
            end = size - 1 if i == total_chunks - 1 else start + chunk - 1
            fh.seek(start)
            body = fh.read(end - start + 1)
            headers = {"Content-Type": "video/mp4", "Content-Length": str(len(body)),
                       "Content-Range": f"bytes {start}-{end}/{size}"}
            last_err = None
            for _ in range(3):  # retry — uploads can hit transient write timeouts
                try:
                    put = httpx.put(upload_url, headers=headers, content=body, timeout=timeout)
                    if put.status_code in (200, 201, 206):
                        last_err = None
                        break
                    last_err = f"{put.status_code} {put.text}"
                except httpx.TransportError as e:
                    last_err = repr(e)
            if last_err:
                raise RuntimeError(
                    f"TikTok chunk {i + 1}/{total_chunks} upload failed: {last_err}")
    return publish_id
