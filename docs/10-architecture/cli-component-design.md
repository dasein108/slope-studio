# CLI Component Design — Decomposed Scripts + One Pipeline

Concrete shape of the "automatic studio, decomposed into separate CLI scripts per stage, also combined into a single pipeline."

## Principles
- **One subcommand per stage**, each a pure transform over the run directory.
- **Run directory is the bus** — stages communicate via files + `project.json` manifest (see [`../00-overview/pipeline-stages.md`](../00-overview/pipeline-stages.md)).
- **Idempotent + resumable** — re-running a stage with existing valid output is a no-op (unless `--force`).
- **Provider-agnostic** — `--provider` per stage; adapters behind a stable interface.
- **Observable cost** — every external call logs cost + latency into the manifest.

## CLI surface

```
studio init   --idea "..." --duration 150 --aspect 9:16 --voice --tier balanced
              → creates runs/<id>/project.json

studio script   [--provider gpt-4o-mini|gemini-flash|groq|ollama] [--style ...]
studio visuals  [--provider nano-banana|seedream|flux|sdxl|pollinations]
                [--char-ref img] [--candidates 3] [--mode scene|character]
studio character[--views front,side,3q] [--expressions ...]   # avatar sheet
studio lora-train [--images dir] [--base flux-dev] [--runpod-gpu rtx4090]
studio clips    [--mode i2v|t2v|avatar] [--provider fal:kling|veo3|runpod:wan2.2|hedra]
                [--max-clip-s 8] [--face img] [--audio mp3]
studio stitch   [--transition fade|cut|wipeleft] [--transition-s 0.4] [--fps 30]
studio voice    [--provider openai-tts|elevenlabs|edge-tts|kokoro] [--voice ...]
                [--captions burn|soft|none] [--music bed.mp3]
studio save     [--aspect 9:16] [--fps 30]
studio publish  [--target youtube|tiktok|instagram] [--privacy public|self_only]

studio run      --idea "..." [all the above flags] [--from script] [--to save]
                [--publish youtube] [--max-cost 1.00]
                → runs the full chain with resume
studio status   runs/<id>          # show manifest: stages done, cost, timings
studio cost     runs/<id>          # estimated/actual cost breakdown
```

## `studio run` flow (with the avatar ordering wrinkle)

```
init → script → visuals ─┬─► (scene mode)  clips ──► stitch ──► voice ──► save ─► publish
                         └─► (avatar mode) voice(TTS only) ──► clips(avatar) ─┘
```
In avatar mode, TTS is produced before `clips` (lip-sync needs audio); the rest of `voice` (mux/captions) still runs after stitch.

## Provider adapter interface (per stage)

```python
class ImageProvider(Protocol):
    def generate(self, prompt: str, refs: list[Path], size: str) -> ImageResult: ...
class VideoProvider(Protocol):
    def generate(self, image: Path|None, prompt: str, seconds: float, mode: str) -> ClipResult: ...
class TTSProvider(Protocol):
    def synth(self, text: str, voice: str) -> AudioResult: ...
class Publisher(Protocol):
    def publish(self, video: Path, meta: dict, privacy: str) -> PublishResult: ...
# every *Result carries .cost_usd, .latency_s, .provider, .artifact_path → manifest
```
Register providers in a table keyed by name; `--provider` selects. Adding a model = one adapter, no pipeline changes.

## Manifest (`project.json`) — measured cost-per-video
```json
{
  "id": "2026-06-03_octopus", "duration_s": 150, "tier": "balanced",
  "stages": {
    "script":  {"done": true, "provider": "gpt-4o-mini", "cost_usd": 0.004, "latency_s": 3.1},
    "visuals": {"done": true, "provider": "nano-banana", "cost_usd": 0.31, "n": 8},
    "clips":   {"done": true, "provider": "fal:kling-2.5", "cost_usd": 0.42, "n": 8},
    "voice":   {"done": true, "provider": "openai-tts", "cost_usd": 0.06},
    "publish": {"done": false}
  },
  "total_cost_usd": 0.794
}
```

## Concurrency & rate limits
- Stages 2 & 3 fan out per scene with `asyncio.gather` behind a `Semaphore(max_parallel)`.
- Per-provider rate-limit config (e.g. Pollinations ~1/15s ✅, OpenRouter free ~50/day ✅) honored by the adapter.
- `--max-cost` gate evaluated before the expensive stage 3.

## Packaging
- Python package `studio/` with `cli.py` (typer), `stages/`, `providers/`, `manifest.py`, `ffmpeg.py`.
- Each stage importable as a function → reused by LangGraph nodes or Claude Code skills without shelling out.
- Dockerfile with ffmpeg baked in; optional RunPod template for the self-host GPU stages.
