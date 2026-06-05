# Sources & Research Run

## Run stats
- 6 search angles · 29 sources fetched · 128 claims extracted · 25 verified · **19 confirmed / 6 killed** · 7 after synthesis · 112 agent calls · ~2.84M subagent tokens · ~17.5 min.
- Method: fan-out web search per angle → URL-dedup + fetch → extract falsifiable claims → 3-vote adversarial verification (≥2/3 refute = killed) → synthesis with semantic dedup + confidence ranking.
- 2 fetches failed (StructuredOutput non-compliance): spheron gpu-cloud-video-ai-2026; nextdiffusion fluxgym RunPod LoRA tutorial.

## Source quality legend
`primary` = official docs/blog of the vendor · `secondary` = reputable aggregator/comparison · `blog` = independent blog · `unreliable` = failed/low-trust.

## Sources by angle

### Broad / pipeline & orchestration
- ✅ primary — hackaday.io/project/205368-ffmpeg-ai-fully-free-ai-video-cli-pipeline (5 claims)
- ✅ primary — github.com/vennittechnologies-byte/youtube-automation-workflow (5 claims; broad-$0 claim refuted)
- blog — latenode.com/...langgraph-multi-agent-orchestration... (3 claims)

### Video generation — cost/quality benchmarks
- secondary — aifreeforever.com/blog/best-ai-video-generation-models... (5 claims; 2 refuted)
- blog — videotoprompt.app/posts/open-source-ai-video-models-comparison-2026 (5)
- blog — whitefiber.com/blog/best-open-source-video-generation-model (5)
- secondary — skywork.ai/blog/sora-2-vs-veo-3-vs-runway-gen-3-2025... (5)
- blog — ulazai.com/ai-video-models-guide-2025 (5)
- secondary — spheron.network/blog/deploy-wan-2-1-ai-video-generation-gpu-setup (5; **all refuted**)

### Image gen + character consistency + LoRA
- ✅ primary — developers.googleblog.com/en/introducing-gemini-2-5-flash-image (5)
- unreliable — nextdiffusion.ai/tutorials/how-to-train-a-flux-lora-with-fluxgym-on-runpod (0, fetch failed)
- blog — medium.com/@geronimo7/how-to-train-a-flux1-lora-for-1-dfd1800afce5 (5)
- secondary — melies.co/compare/ai-image-models (5)
- (+ blog.google nano-banana-2, fal.ai nano-banana-2 in findings)

### TTS, voiceover & talking-avatar lip-sync
- secondary — artificialanalysis.ai/text-to-speech/model-families/elevenlabs (3)
- blog — texttolab.com/blog/openai-tts-pricing (5)
- blog — reviewnexa.com/kokoro-tts-review (5)
- blog — reviewnexa.com/chatterbox-tts-review (5)
- secondary — lipsync.com/compare/heygen-vs-hedra (5)

### RunPod self-hosting economics vs hosted APIs
- unreliable — spheron.network/blog/gpu-cloud-video-ai-2026 (0, fetch failed)
- secondary — spheron.network/blog/gpu-cloud-pricing-comparison-2026 (5)
- ✅ primary — runpod.io/pricing (5; live 2026)
- blog — atlascloud.ai/blog/guides/cheapest-ai-video-generation-api-2026 (5)
- blog — localaimaster.com/blog/local-ai-video-generation (5)

### Publishing APIs & implementation reality
- ✅ primary — developers.tiktok.com/doc/content-posting-api-reference-direct-post (4)
- ✅ primary — developers.tiktok.com/doc/content-sharing-guidelines (5)
- ✅ primary — developers.tiktok.com/doc/tiktok-api-v2-rate-limit (3)
- blog — medium.com/@dorangao/...publishing-videos-to-youtube-via-api-2025 (5)
- blog — zernio.com/blog/tiktok-posting-api (5)
- blog — upload-post.com/how-to/auto-post-youtube-shorts (5)

## Component repos / tools referenced (verified-free stack)
- github.com/rany2/edge-tts · github.com/pollinations/pollinations · openrouter.ai/docs/api/reference/limits · console.groq.com/docs/rate-limits · faster-whisper · ffmpeg

## Reliability note
Surviving claims lean on primary docs (Google, RunPod, TikTok) where it matters most (prices, API constraints). The video-leaderboard and several prices rest on secondary/blog sources and churn fast — re-verify stages 2-3 at build time (see [`open-questions.md`](open-questions.md) Q6).
