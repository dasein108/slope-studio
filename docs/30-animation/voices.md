# Voice & Tone

Semantic narrator voice + emotional tone, set in the scenario and resolved to concrete
TTS settings per provider. Registry: `studio/voices.py`. Applied in `narrate` (per
scene) and the `voice` fallback.

## Fields (in `01_script.json`)

| field | where | values |
|-------|-------|--------|
| `voice_name` | Script | `man` · `woman` (default) · `cartoon` · `narrator` |
| `tone` | Script | `neutral` (default) · `serious` · `mystical` · `friendly` · `sad` · `excited` · `poetic` |
| `tone` | Scene (optional) | same set — **overrides** the Script tone for that scene |

> **`poetic`** is the spoken-verse tone: slow, pauses at every line break / `…` / `—`,
> stresses the key word per line. On `openai-tts` this is real accent placement; `edge`
> only approximates it (−18% rate). Poetry preset: [`docs/recipes/poetry.md`](../../recipes/poetry.md).

CLI overrides: `studio run … --voice man --tone mystical` (or `studio narrate <id> --voice … --tone …`).

## What each provider actually does

| | edge (free) | openai-tts (paid) |
|--|-------------|-------------------|
| voice | real named voices (`woman`→Aria, `man`→Guy, `narrator`→Ryan-GB, `cartoon`→Ana child voice) | `woman`→nova, `man`/`narrator`→onyx, `cartoon`→fable |
| tone | **approximated** via rate+pitch (mystical=slow+low, excited=fast+high, sad=slow+lower…) | **real** tone via an `instructions` prompt ("Speak in a mystical, hushed tone…") |
| cost | $0 | ~$0.015/1k chars |

**Quality note:** edge tone is a believable approximation (good enough for most
Shorts). For genuine emotional delivery or a true *cartoon character* voice, use
`openai-tts`, or add a provider like ElevenLabs (per follow-up "commercial-safe TTS").
edge `cartoon` = child voice pitched +18 Hz — playful, not a true character voice.

## edge tone → (rate, pitch)

`neutral` (+0%,+0Hz) · `serious` (-8%,-3Hz) · `mystical` (-14%,-4Hz) · `friendly`
(+6%,+8Hz) · `sad` (-16%,-6Hz) · `excited` (+14%,+12Hz) · `poetic` (-18%,-3Hz). Tone changes pacing, so it
also changes scene length — which the narration-driven timing handles automatically.

## Per-scene tone example

```json
{
  "voice_name": "narrator", "tone": "serious",
  "scenes": [
    {"id": 1, "tone": "mystical", "narration": "What if everything was a lie?", "...": "..."},
    {"id": 2, "narration": "The proof is simple.", "...": "..."}
  ]
}
```
Scene 1 is mystical; scene 2 inherits the Script `serious` tone.

## Add a voice or tone

Edit `studio/voices.py`: add to `EDGE_VOICES`/`OPENAI_VOICES` (concrete ids) and
`EDGE_TONES` (rate,pitch) / `OPENAI_TONES` (instruction text). List edge voices with
`edge-tts --list-voices`. No other code changes needed.
