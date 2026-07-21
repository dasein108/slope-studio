import pytest

from tests.fixtures.guerrilla.fake_yt import FakeYouTube, FakeHttpError


def test_playlist_items_returns_seeded_videos():
    yt = FakeYouTube(playlists={"PL1": [
        {"video_id": "v1", "title": "A", "description": "d", "published_at": "2026-07-18T10:00:00Z"},
    ]})
    resp = yt.playlistItems().list(part="snippet", playlistId="PL1", maxResults=5).execute()
    assert resp["items"][0]["snippet"]["resourceId"]["videoId"] == "v1"


def test_videos_list_returns_statistics():
    yt = FakeYouTube(videos={"v1": {"views": 900, "comments": 3, "comments_enabled": True}})
    resp = yt.videos().list(part="snippet,statistics", id="v1").execute()
    assert resp["items"][0]["statistics"]["commentCount"] == "3"


def test_insert_records_the_comment_and_returns_an_id():
    yt = FakeYouTube()
    cid = yt.commentThreads().insert(part="snippet", body={
        "snippet": {"videoId": "v1", "topLevelComment": {"snippet": {"textOriginal": "hi"}}}
    }).execute()["id"]
    assert yt.posted == [("v1", "hi")]
    assert cid.startswith("c-")


def test_insert_can_be_forced_to_raise():
    yt = FakeYouTube()
    yt.raise_on_insert = FakeHttpError(403, "commentsDisabled")
    with pytest.raises(FakeHttpError):
        yt.commentThreads().insert(part="snippet", body={
            "snippet": {"videoId": "v1", "topLevelComment": {"snippet": {"textOriginal": "hi"}}}
        }).execute()


def test_insert_returns_full_comment_thread_resource():
    yt = FakeYouTube()
    resp = yt.commentThreads().insert(part="snippet", body={
        "snippet": {"videoId": "v1", "topLevelComment": {"snippet": {"textOriginal": "hi"}}}
    }).execute()
    assert resp["id"].startswith("c-")
    assert resp["snippet"]["topLevelComment"]["snippet"]["textOriginal"] == "hi"


def test_videos_list_omits_comment_count_when_comments_disabled():
    yt = FakeYouTube(videos={"v1": {"views": 900, "comments": 3, "comments_enabled": False}})
    resp = yt.videos().list(part="snippet,statistics", id="v1").execute()
    stats = resp["items"][0]["statistics"]
    assert "commentCount" not in stats
    assert resp["items"][0]["_comments_enabled"] is False
