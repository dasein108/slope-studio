from studio.guerrilla import db


def test_connect_memory_creates_all_tables():
    conn = db.connect_memory()
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"channels", "videos", "comments",
            "comment_metrics", "channel_daily"} <= names


def test_rows_are_mappings():
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id, title) VALUES ('UC1', 'Test')")
    row = conn.execute("SELECT * FROM channels").fetchone()
    assert row["title"] == "Test"
    assert row["status"] == "active"


def test_db_path_is_per_channel():
    assert db.db_path("pilot-channel").as_posix() == \
        "runs/_guerrilla/pilot-channel/guerrilla.db"
