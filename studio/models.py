"""Data models shared across stages. The script JSON is the contract."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SoundCue(BaseModel):
    """One sound effect triggered within a scene. See providers/audio.py."""
    prompt: str             # what the sound is, e.g. "metallic sword clash, sharp"
    at: float = 0.0         # seconds into the scene to trigger it
    dur: float = 2.0        # requested length (SFX providers clamp to <=30s)
    gain_db: float = -3.0   # level relative to the narration mix


class Limb(BaseModel):
    """One articulated limb for the `puppet` animator — a region of the figure that
    rotates around a joint (e.g. an arm around the shoulder). All coords are FRACTIONS
    of the frame (0-1) so they're aspect-independent. See effects/puppet.md."""
    box: list[float]                 # [x0, y0, x1, y1] tight bounds of the limb
    pivot: list[float]               # [x, y] the joint to rotate around (shoulder/hip)
    move: str = "wave"               # wave | raise | point | swing
    amp: float = 35.0                # degrees (signed; +ccw, -cw)
    period: float = 0.8              # seconds per cycle (wave) or ramp time (raise/point)
    phase: float = 0.0               # seconds, to desync multiple limbs


class Scene(BaseModel):
    id: int
    start_s: float
    end_s: float
    visual_prompt: str
    narration: str = ""
    on_screen_text: str = ""
    motion_hint: str = ""
    priority: int = 0  # higher = more worth spending AI-video budget on (0 = auto-heuristic)
    image_role: str = ""  # "hero" (character/main person → quality model) | "bg" (background/overlay → cheap model) | "" (stage default)
    # --- presentation (free, context-driven; see docs/30-animation/) ---
    transition: str = ""        # transition INTO this scene: cut|fade|wipeleft|... (docs/30-animation/transitions.md)
    transition_dur: float = 0.0  # seconds for the transition (0 -> pipeline default)
    tone: str = ""              # per-scene voice tone override (else Script.tone); see voices.py
    animator: str = ""          # how the free clip is made: kenburns|motion-*|kinetic|parallax|slice|static|puppet|talkinghead|manim (docs/30-animation/)
    atmosphere: str = ""        # optional weather/particle overlay post-pass: rain|snow|embers|blood|petals|wind|fog (docs/30-animation/atmosphere.md)
    fx: list[str] = Field(default_factory=list)  # optional look post-passes (applied after atmosphere): grain|vignette|chroma|glitch|sunrise|sunset|godrays (effects/ffmpeg-recipes.md)
    manim_code: str = ""        # optional Manim Scene body for animator=manim (docs/30-animation/manim.md)
    # --- talking-head lip-sync (animator=talkinghead; docs/30-animation/effects/talking-head.md) ---
    mouth_set: str = ""         # sprite set under assets/mouths/<set>/ (A..H,X .png); "" -> drawn default
    mouth_xy: list[float] = Field(default_factory=list)  # [x,y] or [x,y,width] mouth anchor+size frac (0-1); omitted fields -> LLM auto-detect; default [0.5,0.6,0.18]
    limbs: list[Limb] = Field(default_factory=list)  # animator=puppet: per-limb joint rotation (hand up/wave); effects/puppet.md
    sfx: list[SoundCue] = Field(default_factory=list)  # sound effects to lay over this scene

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 3)


class Script(BaseModel):
    topic: str
    duration_s: int = 150
    aspect: str = "9:16"
    voice: bool = True
    voice_name: str = "woman"   # semantic: man|woman|cartoon|narrator (see voices.py)
    tone: str = "neutral"       # neutral|serious|mystical|friendly|sad|excited
    style: str = ""
    character: str = ""
    music: str = ""             # background-music mood prompt for the whole run ("" = none)
    scenes: list[Scene] = Field(default_factory=list)
    title: str = ""
    description: str = ""
    hashtags: list[str] = Field(default_factory=list)

    def validate_timing(self, tolerance: float = 1.0) -> list[str]:
        """Return a list of timing problems (empty == ok)."""
        problems: list[str] = []
        if not self.scenes:
            return ["no scenes"]
        total = self.scenes[-1].end_s
        if abs(total - self.duration_s) > tolerance:
            problems.append(f"scenes end at {total}s, expected ~{self.duration_s}s")
        cursor = 0.0
        for s in self.scenes:
            if abs(s.start_s - cursor) > 0.001:
                problems.append(f"scene {s.id}: gap/overlap at start ({s.start_s} != {cursor})")
            if s.duration_s <= 0:
                problems.append(f"scene {s.id}: non-positive duration")
            cursor = s.end_s
        return problems


# ---- critic gate (stage 1.5): score the scenario before spending on visuals ----
# The four content criteria a scenario must satisfy before it's worth rendering.
# Keys are stable (used in feedback notes); labels are shown to the operator.
CRITIC_CRITERIA: dict[str, str] = {
    "topic_revealed": "Does it deliver on the title/promise — viewer comes away KNOWING the thing?",
    "fact_explained": "Is there >=1 concrete fact/idea/event STATED and EXPLAINED (the what AND why/how)?",
    "informative_interesting": "Does it teach something non-obvious with a real curiosity gap?",
    "emotional_payoff": "Does it land a clear emotion (awe/dread/injustice/paradox-click)?",
}


class CriterionScore(BaseModel):
    """One critic criterion's verdict."""
    name: str                  # one of CRITIC_CRITERIA keys
    passed: bool = False
    score: int = 0             # 1-5 (used to pick the best attempt across retries)
    feedback: str = ""         # what's missing / how to fix (drives the rewrite)


class CriticVerdict(BaseModel):
    """The critic stage output for one scenario attempt (persisted to 01_critic.json)."""
    passed: bool = False                                  # all criteria passed
    scores: list[CriterionScore] = Field(default_factory=list)
    revision_notes: str = ""                              # concrete instructions for the rewrite
    summary: str = ""

    @property
    def total(self) -> int:
        """Sum of per-criterion scores — ranks attempts when none fully passes."""
        return sum(c.score for c in self.scores)

    def failures(self) -> list[CriterionScore]:
        return [c for c in self.scores if not c.passed]
