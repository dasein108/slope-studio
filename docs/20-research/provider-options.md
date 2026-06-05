# Provider Options — TTS, Forced Alignment, Talking-Avatar (research)

🔶 **Research-grade, mostly unverified pricing** — re-check provider pages before relying
on a number. Only `edge-tts` (free) and `faster-whisper` are verified components today.
This page preserves the comparison research that informs the roadmap items
(commercial-safe TTS, avatar narrator format) — see
[`open-questions.md`](open-questions.md) for what's still unverified and
[`../10-architecture/cost-model.md`](../10-architecture/cost-model.md) for shipped costs.

Current shipped voice path: `edge` (free, `studio narrate`/`voice`) → `openai-tts`
(premium tier). Captions are Pillow-PNG overlays (this build lacks libass/drawtext —
see [`../30-animation/captions.md`](../30-animation/captions.md)); **do not** use the
`subtitles=`/`.ass` recipe that older research assumed.

## TTS engines (price / quality / speed)

| Engine | Price 🔶 | Quality | Speed | Notes |
|--------|----------|---------|-------|-------|
| **edge-tts** (MS Edge voices) | **free** ✅ | good, slightly robotic | fast | no key, 200+ voices ✅; **violates MS ToS** (gray for commercial) |
| **ElevenLabs** | ~$5–330/mo by chars; ~$0.10–0.30/1k chars | best, most natural + emotion | fast | voice cloning; quality leader |
| **OpenAI TTS** (`gpt-4o-mini-tts`, `tts-1`) | ~$15/1M chars (`tts-1`) | very good | fast | simple API, steerable tone (4o-mini-tts) |
| **Google Cloud TTS** | free tier + ~$4–16/1M chars (Std/WaveNet/Neural2) | good–very good | fast | many langs/voices |
| **Azure / Amazon Polly** | ~$4–16/1M chars | good | fast | enterprise, SSML |
| **Kokoro TTS** (open, 82M) | **self-host free** | surprisingly good for size | very fast | tiny, CPU/small-GPU; great free-quality pick |
| **Chatterbox** (Resemble, open) | **self-host free** | very good, emotion control | med | strong open option, voice cloning |
| **F5-TTS** (open) | **self-host free** | very good, zero-shot clone | med | fast voice cloning from a few seconds |
| **XTTS-v2 / Piper** (open) | self-host free | good / decent | fast | Piper = ultralight CPU; XTTS = cloning |

**For commercial-safe TTS** (edge-tts ToS is the gray area): Kokoro or Piper (free,
self-host) or OpenAI/Google/ElevenLabs (paid, clearly licensed).

## Captions / forced alignment

- **WhisperX** (open) — word-level timestamps; best for karaoke-style highlighted captions.
- **faster-whisper** ✅ — verified; fast whisper inference for transcribe/align.
- **aeneas** — classic forced-aligner (known text → align to audio).
- NOTE: today captions come from edge-tts `SubMaker` (sentence-level) and are burned as
  Pillow PNG strips. Word-level alignment (WhisperX) is the upgrade path for karaoke captions.

## Talking-avatar / lip-sync (avatar narrator format)

🔶 prices approximate; a HeyGen-vs-Hedra comparison was found but not current prices.

| Tool | Type | Notes |
|------|------|-------|
| **HeyGen** | SaaS | best polished talking avatars; API; credit/sub pricing; commercial-friendly |
| **D-ID** | SaaS | photo→talking-head API; per-minute pricing; fast |
| **Hedra** (Character-3) | SaaS | expressive character video from image+audio; strong emotion |
| **Synthesia** | SaaS | enterprise avatars, pricey |
| **LatentSync** (open) | self-host | SOTA open lip-sync; run on RunPod |
| **SadTalker / Wav2Lip / MuseTalk** (open) | self-host | cheaper/older; Wav2Lip robust but low-res; MuseTalk realtime |

**Ordering wrinkle for avatar mode:** lip-sync needs the audio first, so TTS (stage 5/narrate)
must run **before/with** the video stage. (The shipped 2D `talkinghead` animator already does
a free version of this via Rhubarb viseme swap — see
[`../30-animation/effects/talking-head.md`](../30-animation/effects/talking-head.md).)
