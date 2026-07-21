import random
from datetime import date, timedelta

from studio.guerrilla import db, experiment

START = date(2026, 7, 1)


def test_schedule_is_four_on_two_off():
    states = [experiment.state_for(date(2026, 7, d), START) for d in range(1, 13)]
    assert states == ["on"] * 4 + ["off"] * 2 + ["on"] * 4 + ["off"] * 2


def test_day_before_start_is_off():
    assert experiment.state_for(date(2026, 6, 30), START) == "off"


def _seed(conn, on_subs, off_subs, published_days=()):
    d = START
    for group, values in (("on", on_subs), ("off", off_subs)):
        for v in values:
            iso = d.isoformat()
            experiment.record_day(conn, iso, subs_gained=v, views=0,
                                  channel_page_views=0, comments_posted=0,
                                  state=group, published_video=iso in published_days)
            d += timedelta(days=1)


def _gen_days(seed: int, n: int, mean: float, stdev: float) -> list[int]:
    """Deterministic pseudo-random daily subs_gained values, floored at 0."""
    rng = random.Random(seed)
    return [max(0, round(rng.gauss(mean, stdev))) for _ in range(n)]


def test_readout_detects_an_injected_positive_effect():
    conn = db.connect_memory()
    on_subs = _gen_days(seed=1, n=20, mean=21.0, stdev=1.5)
    off_subs = _gen_days(seed=2, n=20, mean=10.5, stdev=1.5)
    _seed(conn, on_subs=on_subs, off_subs=off_subs)
    r = experiment.readout(conn)
    assert r["verdict"] == "positive"
    assert r["lift"] > 8
    assert r["ci_low"] > 0


def test_readout_reports_null_when_there_is_no_effect():
    conn = db.connect_memory()
    on_subs = _gen_days(seed=3, n=20, mean=10.5, stdev=1.5)
    off_subs = _gen_days(seed=4, n=20, mean=10.5, stdev=1.5)
    _seed(conn, on_subs=on_subs, off_subs=off_subs)
    r = experiment.readout(conn)
    assert r["verdict"] == "null"
    assert r["ci_low"] < 0 < r["ci_high"]


def test_publish_days_are_excluded_from_the_readout():
    conn = db.connect_memory()
    on_subs = [10] * 20 + [900]
    off_subs = [10] * 20
    outlier_date = (START + timedelta(days=len(on_subs) - 1)).isoformat()
    _seed(conn, on_subs=on_subs, off_subs=off_subs, published_days=(outlier_date,))
    r = experiment.readout(conn)
    assert r["on_days"] == 20
    assert r["on_mean"] == 10.0
    assert r["verdict"] == "null"


def test_thin_data_reports_insufficient_not_a_false_signal():
    conn = db.connect_memory()
    # A huge apparent effect (50 vs 1) just below the new threshold: proves
    # the gate blocks a verdict on sample size alone, not on effect size.
    on_subs = _gen_days(seed=5, n=19, mean=50.0, stdev=5.0)
    off_subs = _gen_days(seed=6, n=19, mean=1.0, stdev=0.5)
    _seed(conn, on_subs=on_subs, off_subs=off_subs)
    assert experiment.readout(conn)["verdict"] == "insufficient_data"


def test_readout_is_insufficient_at_nineteen_days_and_sufficient_at_twenty():
    on19 = _gen_days(seed=11, n=19, mean=15.0, stdev=2.0)
    off19 = _gen_days(seed=12, n=19, mean=15.0, stdev=2.0)
    conn19 = db.connect_memory()
    _seed(conn19, on_subs=on19, off_subs=off19)
    assert experiment.readout(conn19)["verdict"] == "insufficient_data"

    on20 = on19 + _gen_days(seed=13, n=1, mean=15.0, stdev=2.0)
    off20 = off19 + _gen_days(seed=14, n=1, mean=15.0, stdev=2.0)
    conn20 = db.connect_memory()
    _seed(conn20, on_subs=on20, off_subs=off20)
    assert experiment.readout(conn20)["verdict"] != "insufficient_data"


def test_readout_excludes_contaminated_off_days_and_reports_the_count():
    """`rollup.run` labels every day on/off purely from the switchback calendar — it
    has no idea whether a tick actually ran (`experiment_start` may not be wired into
    every invocation). An OFF day with `comments_posted > 0` means the loop posted
    anyway, so that day is not a real control observation: including it would compare
    two contaminated-with-"on" populations while calling one of them "off". Such days
    must be excluded from the comparison and counted in `contaminated_days`."""
    conn = db.connect_memory()
    on_subs = _gen_days(seed=1, n=20, mean=21.0, stdev=1.5)
    off_subs = _gen_days(seed=2, n=21, mean=10.5, stdev=1.5)  # one extra to survive exclusion
    _seed(conn, on_subs=on_subs, off_subs=off_subs)

    contaminated_date = (START + timedelta(days=len(on_subs))).isoformat()  # first off day
    conn.execute("UPDATE channel_daily SET comments_posted = 5 WHERE date = ?",
                (contaminated_date,))
    conn.commit()

    r = experiment.readout(conn)
    assert r["contaminated_days"] == 1
    assert r["off_days"] == 20  # 21 seeded, 1 excluded as contaminated
    assert r["verdict"] != "insufficient_data"


def test_uncontaminated_run_reports_zero_contaminated_days():
    conn = db.connect_memory()
    on_subs = _gen_days(seed=1, n=20, mean=21.0, stdev=1.5)
    off_subs = _gen_days(seed=2, n=20, mean=10.5, stdev=1.5)
    _seed(conn, on_subs=on_subs, off_subs=off_subs)
    assert experiment.readout(conn)["contaminated_days"] == 0


def test_readout_is_deterministic_for_a_fixed_seed():
    conn = db.connect_memory()
    on_subs = _gen_days(seed=1, n=20, mean=21.0, stdev=1.5)
    off_subs = _gen_days(seed=2, n=20, mean=10.5, stdev=1.5)
    _seed(conn, on_subs=on_subs, off_subs=off_subs)
    assert experiment.readout(conn, seed=7) == experiment.readout(conn, seed=7)
