"""Stage-2 visuals: leaked aspect-ratio tokens must never reach the image prompt.

Prompt-literal models (fal-flux-schnell, pollinations) render a literal "9:16" as
on-screen text, which QA Gate-2 rejects. See SLO-17.
"""

from __future__ import annotations

import pytest

from studio.stages.visuals import _strip_aspect_token


@pytest.mark.parametrize("raw, expected", [
    ("Maxwell demon at a glowing gate, 9:16", "Maxwell demon at a glowing gate"),
    ("a vivid cinematic scene 9:16", "a vivid cinematic scene"),
    ("16:9 wide vista of mountains", "wide vista of mountains"),
    ("scene, 9:16, more text", "scene, more text"),
    ("no aspect here just a scene", "no aspect here just a scene"),
])
def test_strip_aspect_token(raw, expected):
    assert _strip_aspect_token(raw) == expected
