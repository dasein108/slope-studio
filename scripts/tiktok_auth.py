#!/usr/bin/env python3
"""Mint a TikTok access token for Slope Studio (one-time; then it auto-refreshes).

TikTok **Desktop** apps require a localhost redirect, so this runs a one-shot local
catcher — no tunnel needed. Register the SAME localhost URL as the Desktop "Redirect URI"
in your TikTok app's Login Kit, and set it in .env as TIKTOK_REDIRECT_URI.

  python scripts/tiktok_auth.py --channel pilot-channel

Writes tiktok_token_<channel>.json (gitignored), which studio/providers/publish.py reads
and refreshes. .env needs: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
TIKTOK_REDIRECT_URI=http://localhost:8721/callback
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
API = "https://open.tiktokapis.com"
SCOPES = "video.upload"


def _env(k: str) -> str:
    v = os.environ.get(k)
    return v.strip() if v and v.strip() else ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Mint a TikTok access token (localhost OAuth)")
    ap.add_argument("--channel", default="", help="token suffix → tiktok_token_<channel>.json")
    channel = ap.parse_args().channel

    key, secret, redirect = _env("TIKTOK_CLIENT_KEY"), _env("TIKTOK_CLIENT_SECRET"), _env("TIKTOK_REDIRECT_URI")
    if not (key and secret and redirect):
        raise SystemExit("set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI in .env")
    parsed = urllib.parse.urlparse(redirect)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        raise SystemExit(f"TIKTOK_REDIRECT_URI must be a localhost URL for TikTok Desktop apps, got {redirect}")

    # PKCE — TikTok requires it: code_challenge = HEX(SHA256(code_verifier)), method S256.
    verifier = secrets.token_hex(48)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    auth_url = ("https://www.tiktok.com/v2/auth/authorize/"
                f"?client_key={key}&scope={SCOPES}&response_type=code"
                f"&redirect_uri={urllib.parse.quote(redirect, safe='')}&state=slopestudio"
                f"&code_challenge={challenge}&code_challenge_method=S256")

    box: dict[str, str] = {}

    class OneShot(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — catches any path carrying ?code=
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            box["code"] = q.get("code", [""])[0]
            box["error"] = q.get("error", [""])[0]
            body = b"<h1>TikTok authorized.</h1><p>Token saved. Close this tab.</p>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            return

    srv = HTTPServer(("localhost", parsed.port or 8721), OneShot)
    print(f"Listening on {redirect} for the TikTok redirect…")
    print("Approve in the browser:", auth_url)
    webbrowser.open(auth_url)
    srv.handle_request()  # blocks until the redirect arrives

    if box.get("error"):
        raise SystemExit(f"TikTok returned error: {box['error']}")
    if not box.get("code"):
        raise SystemExit("no authorization code received")

    resp = httpx.post(
        f"{API}/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"client_key": key, "client_secret": secret, "code": box["code"],
              "grant_type": "authorization_code", "redirect_uri": redirect,
              "code_verifier": verifier},
        timeout=30,
    ).json()
    if "access_token" not in resp:
        raise SystemExit(f"token exchange failed: {resp}")
    resp["expires_at"] = time.time() + int(resp.get("expires_in", 86400))
    out = ROOT / (f"tiktok_token_{channel}.json" if channel else "tiktok_token.json")
    out.write_text(json.dumps(resp, indent=2))
    print(f"\n✅ token written → {out}  (open_id={resp.get('open_id', '?')})")


if __name__ == "__main__":
    main()
