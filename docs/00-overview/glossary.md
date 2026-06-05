# Glossary

- **N / duration** — target video length in seconds. Default 150s (2.5 min). Note: YouTube Shorts now allows up to 3 min; TikTok up to 10 min. 150s is fine for both.
- **9:16 / vertical** — portrait aspect (1080x1920) required for Shorts/TikTok/Reels.
- **Scene** — a timed segment of the script with one visual prompt + narration line. Sum of scenes = N.
- **Keyframe** — a still image representing a scene, used as the seed for image-to-video.
- **i2v / t2v** — image-to-video / text-to-video generation modes.
- **Character consistency** — keeping the same character's face/outfit/style across multiple images/clips. Solved via reference images (Nano Banana), IP-Adapter, or a trained LoRA.
- **LoRA (Low-Rank Adaptation)** — small fine-tune weights that teach a base image/video model a specific character/style. Trained on ~10-30 images, ~$1-5 of GPU time on RunPod.
- **Talking avatar / lip-sync** — driving a face image/video to speak given audio (HeyGen, D-ID, Hedra, SadTalker, LatentSync).
- **Nano Banana** — Google's Gemini 2.5 Flash Image model (and Nano Banana 2 = newer). Strong at character consistency + multi-image compositing.
- **Wan / HunyuanVideo / LTX** — leading open-source video generation models (self-hostable on RunPod).
- **fal.ai / Replicate** — serverless GPU API marketplaces that host many of these models behind a pay-per-call API (no infra to manage).
- **RunPod** — GPU cloud with per-second billing; used to self-host open models and train LoRAs.
- **Forced alignment** — matching narration text to audio timestamps to generate accurate captions (whisper / aeneas / WhisperX).
- **Direct Post API** — TikTok's endpoint for posting videos programmatically; audit-gated.
- **Elo / Video Arena** — Artificial Analysis's human-preference leaderboard for video models.
- **Tier** — one of the three reference architectures: budget / balanced / premium. See [`../10-architecture/tiers.md`](../10-architecture/tiers.md).
