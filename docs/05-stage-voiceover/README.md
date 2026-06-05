# Stage 5 — Voiceover (TTS + Captions + Mux)

Synthesize the narration from `01_script.json`, generate captions (forced-aligned), mux audio over `04_stitched.mp4` → `final.mp4`.

> If using a **talking avatar** (stage 3 mode B), TTS must run **before** stage 3 (the avatar lip-syncs to this audio). For non-avatar videos, stage 5 runs after stitch.

## Sub-steps
1. **TTS** narration → `narration.mp3` (per-scene or one track + timestamps).
2. **Captions** — forced-align text to audio → `captions.srt`/`.ass` (whisper/WhisperX/aeneas). Burn-in (better for shorts) or soft subs.
3. **Mux** — combine video + narration (+ optional music bed, ducked) → `final.mp4`. Loudness-normalize to ~-14 LUFS.

## TTS options (price / quality / speed)

> ✅ edge-tts verified free. 🔶 others approximate, re-check provider pages.

| Engine | Price 🔶 | Quality | Speed | Notes |
|--------|------|---------|-------|-------|
| **edge-tts** (MS Edge voices) | **free** ✅ | good, slightly robotic | fast | no key, 200+ voices ✅; **violates MS ToS** ✅ (gray for commercial) |
| **ElevenLabs** | ~$5-330/mo by chars 🔶; ~$0.10-0.30/1k chars | best, most natural + emotion | fast | voice cloning; industry quality leader |
| **OpenAI TTS** (`gpt-4o-mini-tts`, `tts-1`) | 🔶 ~$15/1M chars (`tts-1`) | very good | fast | simple API, steerable tone (4o-mini-tts) |
| **Google Cloud TTS** | 🔶 free tier + ~$4-16/1M chars (Std/WaveNet/Neural2) | good-very good | fast | many langs/voices |
| **Azure / Amazon Polly** | 🔶 ~$4-16/1M chars | good | fast | enterprise, SSML |
| **Kokoro TTS** (open, 82M) | **self-host free** 🔶 | surprisingly good for size | very fast | tiny, runs on CPU/small GPU; great free-quality pick |
| **Chatterbox** (Resemble, open) | **self-host free** 🔶 | very good, emotion control | med | strong open option, voice cloning |
| **F5-TTS** (open) | **self-host free** 🔶 | very good, zero-shot clone | med | fast voice cloning from a few seconds |
| **XTTS-v2 / Piper** (open) | self-host free 🔶 | good / decent | fast | Piper = ultralight CPU; XTTS = cloning |

## Captions / forced alignment
- **WhisperX** (open) — word-level timestamps, best for accurate karaoke-style caption timing. Run on the generated narration.
- **faster-whisper** ✅ — verified component; fast whisper inference for transcribe/align.
- **aeneas** — classic forced-aligner (text known, align to audio).
- Burn captions with ffmpeg `subtitles=captions.ass` (style for big, centered, highlighted-word shorts captions) or libraries like `captacity`.

## Mux + master
```bash
# video + narration, normalize loudness, optional music bed ducked under VO
ffmpeg -i 04_stitched.mp4 -i narration.mp3 -i music.mp3 -filter_complex \
"[2:a]volume=0.15[m];[1:a][m]amix=inputs=2:duration=first[a];\
[a]loudnorm=I=-14:TP=-1.5:LRA=11[ao]" \
-map 0:v -map "[ao]" -c:v copy -c:a aac -shortest final.mp4
# burn captions
ffmpeg -i final.mp4 -vf "subtitles=captions.ass" -c:a copy final_cap.mp4
```

## Recommendation
- **Default:** OpenAI `gpt-4o-mini-tts` or ElevenLabs for natural VO; **WhisperX** for word-timed burned captions.
- **Free path:** **edge-tts** ✅ (drafts/non-commercial) or self-host **Kokoro** (free + genuinely good, commercial-safe).
- **Cloning a brand voice:** F5-TTS/Chatterbox (free, self-host) or ElevenLabs (paid, best).
- Always loudness-normalize (-14 LUFS) — platform audio consistency + retention.

## CLI
```
studio voice --script runs/<id>/01_script.json --video runs/<id>/04_stitched.mp4 \
  --provider openai-tts --voice alloy --captions burn \
  --music ./beds/lofi.mp3 --out runs/<id>/05_voice/final.mp4
```
