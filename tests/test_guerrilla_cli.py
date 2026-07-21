from datetime import date

from typer.testing import CliRunner

from studio.cli import app
from studio.guerrilla import loop as gloop

runner = CliRunner()


def test_guerrilla_group_is_registered():
    res = runner.invoke(app, ["guerrilla", "--help"])
    assert res.exit_code == 0
    for cmd in ("watchlist", "tick", "track", "report", "queue", "approve", "rollup"):
        assert cmd in res.stdout


def test_watchlist_add_then_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    add = runner.invoke(app, ["guerrilla", "watchlist", "add", "UC1",
                              "--channel", "test-ch", "--median-views", "20000"])
    assert add.exit_code == 0
    out = runner.invoke(app, ["guerrilla", "watchlist", "list", "--channel", "test-ch"])
    assert out.exit_code == 0 and "UC1" in out.stdout


def test_report_on_a_fresh_db_succeeds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["guerrilla", "report", "--channel", "test-ch"])
    assert res.exit_code == 0
    assert "Guerrilla Marketing Report" in res.stdout


def _queue_one(channel: str) -> None:
    from studio.guerrilla import db as gdb

    conn = gdb.connect(channel)
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    conn.execute(
        "INSERT INTO videos (video_id, channel_id, decision, skip_reason) "
        "VALUES ('v1', 'UC1', 'queued', 'a considered thought about the scene')")
    conn.commit()


def _seed_journal_publish(channel: str, published_at: str) -> None:
    from studio.marketing import journal as mj

    j = mj.load(channel)
    j.entries.append(mj.Entry(id=j.next_id(), idea="x", published_at=published_at))
    mj.save(j)


def test_approve_default_cap_and_journal_publish_times_reach_post_comment(tmp_path, monkeypatch):
    """`guerrilla approve` should pass the operator's --cap (default 12, not a hardcoded 25)
    and should populate publish_times from the marketing journal so `rails.in_blackout` is
    not silently defeated by an empty list."""
    monkeypatch.chdir(tmp_path)
    _queue_one("test-ch")
    _seed_journal_publish("test-ch", "2026-07-10T12:00:00+00:00")

    captured = {}

    def fake_post_comment(conn, client, video_id, text, style_tag, verdict, variant_rank,
                          now, cfg):
        captured.update(cfg)
        return "cid1"

    monkeypatch.setattr("studio.guerrilla.client.build", lambda channel="": object())
    monkeypatch.setattr("studio.guerrilla.post.post_comment", fake_post_comment)

    res = runner.invoke(app, ["guerrilla", "approve", "v1", "--channel", "test-ch"])
    assert res.exit_code == 0, res.stdout
    assert captured["daily_cap"] == 12
    assert captured["publish_times"] == ["2026-07-10T12:00:00+00:00"]


def test_approve_cap_option_overrides_the_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _queue_one("test-ch")

    captured = {}

    def fake_post_comment(conn, client, video_id, text, style_tag, verdict, variant_rank,
                          now, cfg):
        captured.update(cfg)
        return "cid1"

    monkeypatch.setattr("studio.guerrilla.client.build", lambda channel="": object())
    monkeypatch.setattr("studio.guerrilla.post.post_comment", fake_post_comment)

    res = runner.invoke(app, ["guerrilla", "approve", "v1", "--channel", "test-ch",
                              "--cap", "20"])
    assert res.exit_code == 0, res.stdout
    assert captured["daily_cap"] == 20


def test_tick_passes_journal_publish_times_and_experiment_start_into_config(tmp_path, monkeypatch):
    """`guerrilla_tick` builds `Config` directly (no `post_comment` call to inspect, unlike
    `approve`), so this monkeypatches `loop.tick` itself and asserts on the `cfg` it
    receives — same technique as the existing `approve` tests. Without wiring
    `publish_times`, `rails.in_blackout` is always evaluated against `[]` and the
    automated tick path never enforces the publish blackout that `approve` does."""
    monkeypatch.chdir(tmp_path)
    _seed_journal_publish("test-ch", "2026-07-10T12:00:00+00:00")

    captured = {}

    def fake_tick(conn, client, cfg, now, complete=None, notify=None):
        captured["cfg"] = cfg
        return gloop.TickResult()

    monkeypatch.setattr("studio.guerrilla.client.build", lambda channel="": object())
    monkeypatch.setattr("studio.guerrilla.loop.tick", fake_tick)

    res = runner.invoke(app, ["guerrilla", "tick", "--channel", "test-ch",
                              "--experiment-start", "2026-07-01"])
    assert res.exit_code == 0, res.stdout
    assert captured["cfg"].publish_times == ["2026-07-10T12:00:00+00:00"]
    assert captured["cfg"].experiment_start == date(2026, 7, 1)


def test_tick_experiment_start_defaults_to_none_when_omitted(tmp_path, monkeypatch):
    """Some operators will not run the switchback experiment; omitting the option
    must not gate ticks by an arbitrary implicit start date."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def fake_tick(conn, client, cfg, now, complete=None, notify=None):
        captured["cfg"] = cfg
        return gloop.TickResult()

    monkeypatch.setattr("studio.guerrilla.client.build", lambda channel="": object())
    monkeypatch.setattr("studio.guerrilla.loop.tick", fake_tick)

    res = runner.invoke(app, ["guerrilla", "tick", "--channel", "test-ch"])
    assert res.exit_code == 0, res.stdout
    assert captured["cfg"].experiment_start is None


def test_dry_run_tick_prints_every_proposed_comment(tmp_path, monkeypatch):
    """The dry-run gate is only real if the operator can read the comments it would
    have posted. `res.proposed` must reach the console, not just aggregate counts."""
    monkeypatch.chdir(tmp_path)

    from studio.guerrilla import loop as gloop

    def fake_tick(conn, client, cfg, now, complete=None, notify=None):
        r = gloop.TickResult()
        r.discovered = 1
        r.considered = 1
        r.posted = 1
        r.proposed = [{
            "video_id": "v1",
            "title": "The Ship of Theseus",
            "style_tag": "provocative_question",
            "score": 4.5,
            "text": "If every plank is replaced, when did it stop being the ship?",
        }]
        return r

    monkeypatch.setattr("studio.guerrilla.client.build", lambda channel="": object())
    monkeypatch.setattr("studio.guerrilla.loop.tick", fake_tick)

    res = runner.invoke(app, ["guerrilla", "tick", "--channel", "test-ch", "--dry-run"])
    assert res.exit_code == 0, res.stdout
    assert "The Ship of Theseus" in res.stdout
    assert "provocative_question" in res.stdout
    assert "If every plank is replaced, when did it stop being the ship?" in res.stdout
    assert "posted=1" in res.stdout


# ------------------------------------------------------------------ I3: breaker CLI surface

def test_guerrilla_resume_clears_a_tripped_breaker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from studio.guerrilla import db as gdb
    from studio.guerrilla import track as gtrack

    conn = gdb.connect("test-ch")
    gtrack.trip_breaker(conn, 0.2)
    assert gtrack.is_tripped(conn) is True

    res = runner.invoke(app, ["guerrilla", "resume", "--channel", "test-ch"])
    assert res.exit_code == 0, res.stdout
    assert gtrack.is_tripped(gdb.connect("test-ch")) is False


def test_approve_refuses_to_post_while_the_breaker_is_tripped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _queue_one("test-ch")
    from studio.guerrilla import db as gdb
    from studio.guerrilla import track as gtrack

    gtrack.trip_breaker(gdb.connect("test-ch"), 0.2)

    called = []
    monkeypatch.setattr("studio.guerrilla.client.build", lambda channel="": object())
    monkeypatch.setattr("studio.guerrilla.post.post_comment",
                        lambda *a, **kw: called.append(1) or "cid1")

    res = runner.invoke(app, ["guerrilla", "approve", "v1", "--channel", "test-ch"])
    assert res.exit_code != 0
    assert called == []


# ------------------------------------------------------------------ I5: watchlist resume and full listing

def test_watchlist_resume_reactivates_a_paused_channel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from studio.guerrilla import db as gdb
    from studio.guerrilla import watchlist as gwl

    conn = gdb.connect("test-ch")
    gwl.add(conn, "UC1", median_views=20000)
    gwl.set_status(conn, "UC1", "paused")

    res = runner.invoke(app, ["guerrilla", "watchlist", "resume", "UC1", "--channel", "test-ch"])
    assert res.exit_code == 0, res.stdout
    assert gwl.active(gdb.connect("test-ch"))[0]["channel_id"] == "UC1"


def test_watchlist_list_hides_paused_by_default_but_all_shows_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from studio.guerrilla import db as gdb
    from studio.guerrilla import watchlist as gwl

    conn = gdb.connect("test-ch")
    gwl.add(conn, "UC1", median_views=20000)
    gwl.set_status(conn, "UC1", "paused")

    default_list = runner.invoke(app, ["guerrilla", "watchlist", "list", "--channel", "test-ch"])
    assert default_list.exit_code == 0
    assert "(watchlist empty" in default_list.stdout

    full_list = runner.invoke(app, ["guerrilla", "watchlist", "list", "--channel", "test-ch", "--all"])
    assert full_list.exit_code == 0
    assert "UC1" in full_list.stdout
