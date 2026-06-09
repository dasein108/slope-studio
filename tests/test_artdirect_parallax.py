"""Parallax must never land on a dominant-subject scene (ghost-twin guard)."""

from __future__ import annotations

from studio.artdirect import _BODY_CYCLE, decorate
from studio.models import Scene, Script


def _scene(sid, role, animator=""):
    return Scene(id=sid, start_s=(sid - 1) * 6, end_s=sid * 6,
                 visual_prompt="x", narration="n", image_role=role, animator=animator)


def test_parallax_downgraded_on_subject_scene():
    s = Script(topic="t", duration_s=12,
               scenes=[_scene(1, "hero", "parallax"), _scene(2, "bg", "parallax")])
    decorate(s)
    assert s.scenes[0].animator != "parallax"           # person scene → drift/static
    assert s.scenes[0].animator.startswith("motion-")
    assert s.scenes[1].animator == "parallax"            # scenery scene → kept


def test_blurred_parallax_also_guarded_on_subject():
    s = Script(topic="t", duration_s=6, scenes=[_scene(1, "hero", "blurred-parallax")])
    decorate(s)
    assert s.scenes[0].animator not in ("parallax", "blurred-parallax")


def test_body_cycle_has_no_parallax_or_zoom():
    # body scenes have a subject — the auto rotation must not assign parallax or twitchy zoom
    assert "parallax" not in _BODY_CYCLE
    assert not any(a.startswith("motion-zoom") or a == "motion-pulse" for a in _BODY_CYCLE)


def test_banned_zoom_pulse_downgraded():
    s = Script(topic="t", duration_s=18, scenes=[
        _scene(1, "hero", "motion-zoomin"),
        _scene(2, "bg", "motion-zoomout"),
        _scene(3, "hero", "motion-pulse"),
    ])
    decorate(s)
    assert all(sc.animator.startswith("motion-drift") for sc in s.scenes)


def test_unset_subject_scene_never_autofills_parallax():
    # a middle body scene with no animator set → filled from _BODY_CYCLE, never parallax
    s = Script(topic="t", duration_s=18,
               scenes=[_scene(1, "hero"), _scene(2, "hero"), _scene(3, "hero")])
    decorate(s)
    assert all(sc.animator != "parallax" for sc in s.scenes)
