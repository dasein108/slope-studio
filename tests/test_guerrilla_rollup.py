# tests/test_guerrilla_rollup.py
from datetime import date

from studio.guerrilla import db, rollup


class FakeAnalytics:
    """Mimics youtubeAnalytics().reports().query(...).execute()."""

    def __init__(self, rows):
        self.rows = rows
        self.last_kwargs = None

    def reports(self):
        return self

    def query(self, **kw):
        self.last_kwargs = kw
        return self

    def execute(self):
        return {"columnHeaders": [{"name": "day"}, {"name": "views"},
                                  {"name": "subscribersGained"}],
                "rows": self.rows}


def test_daily_rows_are_normalized():
    a = FakeAnalytics([["2026-07-01", 500, 12], ["2026-07-02", 400, 8]])
    got = rollup.daily_rows(a, "UCme", date(2026, 7, 1), date(2026, 7, 2))
    assert got == [{"date": "2026-07-01", "views": 500, "subs_gained": 12},
                   {"date": "2026-07-02", "views": 400, "subs_gained": 8}]


def test_query_is_scoped_to_the_channel_and_range():
    a = FakeAnalytics([])
    rollup.daily_rows(a, "UCme", date(2026, 7, 1), date(2026, 7, 2))
    assert a.last_kwargs["ids"] == "channel==UCme"
    assert a.last_kwargs["startDate"] == "2026-07-01"
    assert a.last_kwargs["endDate"] == "2026-07-02"
    assert a.last_kwargs["dimensions"] == "day"


def test_run_stamps_switchback_arm_and_publish_flag():
    conn = db.connect_memory()
    a = FakeAnalytics([["2026-07-01", 500, 12], ["2026-07-05", 400, 8]])
    n = rollup.run(conn, a, "UCme", date(2026, 7, 1), date(2026, 7, 5),
                   experiment_start=date(2026, 7, 1),
                   publish_dates={"2026-07-05"})
    assert n == 2
    rows = {r["date"]: r for r in conn.execute("SELECT * FROM channel_daily")}
    assert rows["2026-07-01"]["switchback_state"] == "on"    # day 0 of a 4-on block
    assert rows["2026-07-05"]["switchback_state"] == "off"   # day 4 -> off
    assert rows["2026-07-05"]["published_video"] == 1
    assert rows["2026-07-01"]["subs_gained"] == 12


def test_run_counts_comments_posted_that_day():
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('v1', 'UC1')")
    for i in range(3):
        conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                     "VALUES (?, 'v1', 'x', '2026-07-01T14:00:00+00:00')", (f"c{i}",))
    conn.commit()
    a = FakeAnalytics([["2026-07-01", 500, 12]])
    rollup.run(conn, a, "UCme", date(2026, 7, 1), date(2026, 7, 1),
               experiment_start=date(2026, 7, 1), publish_dates=set())
    row = conn.execute("SELECT * FROM channel_daily").fetchone()
    assert row["comments_posted"] == 3


def test_run_is_idempotent():
    conn = db.connect_memory()
    a = FakeAnalytics([["2026-07-01", 500, 12]])
    for _ in range(2):
        rollup.run(conn, a, "UCme", date(2026, 7, 1), date(2026, 7, 1),
                   experiment_start=date(2026, 7, 1), publish_dates=set())
    assert conn.execute("SELECT COUNT(*) c FROM channel_daily").fetchone()["c"] == 1
