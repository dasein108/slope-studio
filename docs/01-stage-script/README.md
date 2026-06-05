# Stage 1 — Script (Idea → Timed Scenario + Voiceover Text)

Turn a one-line idea into a structured, timed scenario the rest of the pipeline can consume mechanically.

## Output contract

`01_script.json`:
```json
{
  "topic": "why octopuses are aliens",
  "duration_s": 150,
  "aspect": "9:16",
  "voice": true,
  "style": "fast-paced explainer, slightly funny",
  "character": "a curious cartoon marine biologist, red beanie, round glasses, teal jacket",
  "scenes": [
    {
      "id": 1,
      "start_s": 0, "end_s": 6,
      "visual_prompt": "<consistent character desc> standing on a dock at dawn, pointing at the ocean, vibrant illustration, 9:16",
      "narration": "Octopuses might be the closest thing to aliens on Earth.",
      "on_screen_text": "ALIENS?",
      "motion_hint": "slow push-in, character gestures to sea"
    }
  ],
  "title": "Why Octopuses Are Basically Aliens 🐙 #Shorts",
  "description": "...",
  "hashtags": ["#shorts", "#octopus", "#science"]
}
```

### Hard requirements the prompt must enforce
- **Timings sum to N.** Scenes tile `[0, N]` with no gaps/overlaps. Validate in code; re-prompt if off.
- **Scene length ≤ clip cap.** Most video models max 5-10s. Keep `end_s - start_s` ≤ 8 (split long beats). For 150s that's ~19-30 scenes — or fewer longer scenes built from multiple extended clips.
- **Character string is reused verbatim** in every `visual_prompt` for consistency (cheap consistency lever before you even reach LoRA/reference-images).
- **Narration fits the time.** ~2.5-3 words/sec spoken → a 6s scene ≈ 15-18 words. Tell the LLM the word budget per scene.
- **On-screen text** short (hook retention). Title/desc/hashtags generated here for stage 7.

## Model options (price / features / speed / quality)

> Prices are 🔶 approximate (Jan 2026 knowledge); LLM pricing is low enough that stage 1 is never the cost driver. Re-check provider pages.

| Model | $/1M in / out (approx) 🔶 | Structured-JSON reliability | Speed | Notes |
|-------|--------------|------------------------------|-------|-------|
| **Gemini 2.5 Flash** | ~$0.30 / $2.50 | excellent (native JSON schema) | fast | great default; cheap; long context |
| **GPT-4o-mini** | ~$0.15 / $0.60 | excellent (json_schema mode) | fast | cheapest reliable; strong tool/JSON |
| **Claude Haiku 4.5** | ~$1 / $5 | excellent | fast | best at following nuanced style/tone |
| **Claude Sonnet/Opus** | higher | best creative quality | med | use only for hero scripts |
| **GPT-4o / o-series** | higher | excellent | med | overkill for scripting |
| **DeepSeek V3 / R1** | ~$0.27 / $1.10 | good | med | cheap, decent reasoning for outlines |
| **Groq (llama-3.1-8b-instant)** | **free tier** ✅ | ok with strict prompt | very fast | free, swappable ✅ |
| **OpenRouter `:free` models** | **free** ✅ (~50 req/day ✅) | ok | varies | verified free path ✅ |
| **Local Ollama (llama3.1:8b)** | **$0** ✅ | ok | depends on HW | fully offline ✅ |

✅ Verified: free scripting via OpenRouter free models / Groq `llama-3.1-8b-instant` / local Ollama `llama3.1:8b`, returning structured JSON of `{scene, narration}`, model swappable in code.

## Recommendation
- **Default:** GPT-4o-mini or Gemini 2.5 Flash with strict JSON-schema output.
- **Free path:** Groq `llama-3.1-8b-instant` (fast, free) → fall back to Ollama offline.
- **Hero/brand voice:** Claude Sonnet for the script, then a cheap model to expand into the timed JSON.

## Prompt design notes
- Two-pass is more reliable than one: (1) creative beat sheet, (2) deterministic "convert to timed JSON schema, enforce word budgets and timing sum = N." Cheap model can do pass 2.
- Pin the character description once at the top; instruct the model to copy it into every `visual_prompt`.
- Ask for `motion_hint` per scene — drives stage 3 i2v prompts and stage 4 transition choice.
- Return `title`/`description`/`hashtags` here so stage 7 needs no extra LLM call.

## CLI
```
studio script --idea "why octopuses are aliens" --duration 150 --voice \
  --style "fast explainer" --provider gpt-4o-mini --out runs/<id>/01_script.json
```
