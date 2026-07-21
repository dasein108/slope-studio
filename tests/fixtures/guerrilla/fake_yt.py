"""A fake YouTube Data API resource.

Mimics googleapiclient's chained builder (`yt.videos().list(...).execute()`) so
production code paths run unchanged under test. Records every comment insert in
`.posted` and can be forced to raise via `.raise_on_insert`.
"""

from __future__ import annotations


class FakeHttpError(Exception):
    """Stands in for googleapiclient.errors.HttpError."""

    def __init__(self, status: int, reason: str):
        super().__init__(f"{status} {reason}")
        self.status_code = status
        self.reason = reason


class _Req:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class FakeYouTube:
    def __init__(self, videos=None, playlists=None, threads=None, channels=None, search=None,
                 our_channel_id="UC_SELF", seed_threads=None):
        # videos: {video_id: {views, comments, comments_enabled, title, description, published_at}}
        self.videos_data = videos or {}
        # playlists: {playlist_id: [ {video_id, title, description, published_at}, ... ]}
        self.playlists_data = playlists or {}
        # threads: {comment_id: {likes, replies, hearted, pinned, status}}
        self.threads_data = threads or {}
        # channels: {channel_id: {uploads_playlist, title, subs}}
        self.channels_data = channels or {}
        self.search_data = search or []
        self.posted: list[tuple[str, str]] = []
        self.raise_on_insert: Exception | None = None
        # Simulates the SSL-ghost-success trap: the write reaches YouTube (shows
        # up in `.posted` and in a read-back by videoId) but the insert call
        # itself raises before returning the response, as if the confirmation
        # never arrived. Distinct from `raise_on_insert`, which raises before any
        # write happens at all.
        self.raise_after_insert: Exception | None = None
        self._next_id = 0
        # The identity `insert()` attributes new comments to — models
        # `authorChannelId` on the top-level comment snippet, the way the real
        # commentThreads API does, so `post._find_landed` has something to
        # match our own posts against.
        self.our_channel_id = our_channel_id
        # video_id -> list of commentThreads.list-shaped response items, in
        # post order, populated by every successful server-side write (even one
        # that then raises via `raise_after_insert`) so read-back tests can find
        # a comment the caller never got an id for. Also seedable up front via
        # `seed_threads` — {video_id: [{"text": ..., "author_channel_id": ...}]}
        # — to model a pre-existing comment thread from someone else, e.g. a
        # byte-identical comment by a different author already sitting on the
        # video before we ever try to post.
        self._threads_by_video: dict[str, list[dict]] = {}
        for vid, items in (seed_threads or {}).items():
            for it in items:
                self._next_id += 1
                cid = f"seed-{self._next_id}"
                self._threads_by_video.setdefault(vid, []).append(
                    self._thread_item(cid, it["text"], it.get("author_channel_id", "")))

    def _thread_item(self, cid: str, text: str, author_channel_id: str) -> dict:
        """One commentThreads.list-shaped item, matching the real API's
        `snippet.topLevelComment.snippet.authorChannelId.value` shape."""
        return {
            "id": cid,
            "snippet": {
                "isPublic": True,
                "topLevelComment": {"id": cid, "snippet": {
                    "textOriginal": text,
                    "textDisplay": text,
                    "likeCount": 0,
                    "authorChannelId": {"value": author_channel_id},
                }},
                "totalReplyCount": 0,
            },
        }

    # ---- resource accessors -------------------------------------------------
    def videos(self):
        return _Videos(self)

    def playlistItems(self):
        return _PlaylistItems(self)

    def channels(self):
        return _Channels(self)

    def commentThreads(self):
        return _CommentThreads(self)

    def search(self):
        return _Search(self)


class _Videos:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part="", id="", **kw):
        def run():
            items = []
            for vid in [v for v in id.split(",") if v]:
                d = self.yt.videos_data.get(vid)
                if d is None:
                    continue
                items.append({
                    "id": vid,
                    "snippet": {
                        "title": d.get("title", ""),
                        "description": d.get("description", ""),
                        "publishedAt": d.get("published_at", ""),
                        "channelId": d.get("channel_id", ""),
                    },
                    "statistics": {
                        "viewCount": str(d.get("views", 0)),
                        **(
                            {"commentCount": str(d.get("comments", 0))}
                            if d.get("comments_enabled", True)
                            else {}
                        ),
                    },
                    "status": {"madeForKids": d.get("made_for_kids", False)},
                    "_comments_enabled": d.get("comments_enabled", True),
                })
            return {"items": items}
        return _Req(run)


class _PlaylistItems:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part="", playlistId="", maxResults=5, **kw):
        def run():
            entries = self.yt.playlists_data.get(playlistId, [])[:maxResults]
            return {"items": [{
                "snippet": {
                    "resourceId": {"videoId": e["video_id"]},
                    "title": e.get("title", ""),
                    "description": e.get("description", ""),
                    "publishedAt": e.get("published_at", ""),
                }
            } for e in entries]}
        return _Req(run)


class _Channels:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part="", id="", **kw):
        def run():
            items = []
            for cid in [c for c in id.split(",") if c]:
                d = self.yt.channels_data.get(cid, {})
                items.append({
                    "id": cid,
                    "snippet": {"title": d.get("title", "")},
                    "statistics": {"subscriberCount": str(d.get("subs", 0))},
                    "contentDetails": {"relatedPlaylists": {
                        "uploads": d.get("uploads_playlist", "")}},
                })
            return {"items": items}
        return _Req(run)


class _CommentThreads:
    def __init__(self, yt):
        self.yt = yt

    def insert(self, part="", body=None):
        def run():
            if self.yt.raise_on_insert is not None:
                raise self.yt.raise_on_insert
            sn = body["snippet"]
            text = sn["topLevelComment"]["snippet"]["textOriginal"]
            self.yt.posted.append((sn["videoId"], text))
            self.yt._next_id += 1
            cid = f"c-{self.yt._next_id}"
            resp = self.yt._thread_item(cid, text, self.yt.our_channel_id)
            resp["snippet"]["videoId"] = sn["videoId"]
            self.yt._threads_by_video.setdefault(sn["videoId"], []).append(resp)
            if self.yt.raise_after_insert is not None:
                raise self.yt.raise_after_insert
            return resp
        return _Req(run)

    def list(self, part="", id="", videoId="", **kw):
        def run():
            if videoId:
                # Most recent first, like `order="time"` against a real feed.
                return {"items": list(reversed(self.yt._threads_by_video.get(videoId, [])))}
            items = []
            for cid in [c for c in id.split(",") if c]:
                d = self.yt.threads_data.get(cid)
                if d is None:
                    continue  # absent from the response == deleted
                items.append({
                    "id": cid,
                    "snippet": {
                        "totalReplyCount": d.get("replies", 0),
                        "topLevelComment": {"snippet": {
                            "likeCount": d.get("likes", 0),
                            "viewerRating": "like" if d.get("hearted") else "none",
                        }},
                        "isPublic": d.get("status", "live") != "held",
                    },
                })
            return {"items": items}
        return _Req(run)


class _Search:
    def __init__(self, yt):
        self.yt = yt

    def list(self, **kw):
        def run():
            return {"items": self.yt.search_data}
        return _Req(run)
