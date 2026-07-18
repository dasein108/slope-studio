"""Re-recording a stage must accumulate cost, never clobber it (resume/skip = $0 runs)."""

from __future__ import annotations

from studio.manifest import Manifest


def test_fresh_record_keeps_given_cost():
    m = Manifest(id="r", idea="i")
    m.record("clips", done=True, provider="auto:kling", cost_usd=2.5, note="first")
    assert m.stages["clips"].cost_usd == 2.5


def test_rerun_with_zero_cost_preserves_prior_spend():
    # the skip path (`dst.exists()`) renders nothing and reports $0 — that re-record
    # used to overwrite the real cost, making expensive runs look free in the journal.
    m = Manifest(id="r", idea="i")
    m.record("clips", done=True, provider="auto:kling", cost_usd=2.5, note="first")
    m.record("clips", done=True, provider="kenburns:kling", cost_usd=0.0, note="rerun")
    assert m.stages["clips"].cost_usd == 2.5


def test_partial_resume_accumulates():
    # crash after scenes 1-5 ($2), resume renders 6-8 ($1) → run really spent $3
    m = Manifest(id="r", idea="i")
    m.record("clips", done=False, provider="auto:kling", cost_usd=2.0)
    m.record("clips", done=True, provider="auto:kling", cost_usd=1.0)
    assert m.stages["clips"].cost_usd == 3.0
    assert m.total_cost_usd == 3.0


def test_rerecord_without_cost_carries_forward():
    m = Manifest(id="r", idea="i")
    m.record("publish", done=True, provider="youtube", cost_usd=0.1)
    m.record("publish", done=True, provider="youtube", note="privacy re-verified")
    assert m.stages["publish"].cost_usd == 0.1
