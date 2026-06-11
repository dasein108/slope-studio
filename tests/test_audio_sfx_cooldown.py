from __future__ import annotations

import json
from pathlib import Path

from studio import paths
from studio.providers.base import GenResult
from studio.stages import audio


def test_same_sfx_family_is_suppressed_inside_30_seconds(tmp_path: Path, monkeypatch) -> None:
    script = {
        "topic": "test",
        "duration_s": 40,
        "aspect": "9:16",
        "scenes": [
            {
                "id": 1,
                "start_s": 0,
                "end_s": 20,
                "narration": "First.",
                "visual_prompt": "first",
                "sfx": [{"prompt": "impact boom", "at": 1, "dur": 0.5, "gain_db": -10}],
            },
            {
                "id": 2,
                "start_s": 20,
                "end_s": 40,
                "narration": "Second.",
                "visual_prompt": "second",
                "sfx": [{"prompt": "short crash hit", "at": 5, "dur": 0.5, "gain_db": -10}],
            },
        ],
    }
    paths.script_json(tmp_path).write_text(json.dumps(script))

    def fake_generate_sfx(provider: str, prompt: str, seconds: float, dst: Path) -> GenResult:
        dst.write_bytes(b"audio")
        return GenResult(path=dst, provider=provider)

    monkeypatch.setattr(audio.audio, "generate_sfx", fake_generate_sfx)

    result = audio.run(tmp_path, "local", "silence", force=True)

    placements = json.loads(paths.sfx_placements_json(tmp_path).read_text())
    assert len(placements) == 1
    assert "1 repetitive sfx suppressed (<30s)" in result.note
