"""Character cards — learn a recurring character from a reference-image folder.

A character lives in `<root>/<name>/` (default root: `characters/`). `build_card()`
runs an LLM-vision pass over the folder and writes `<root>/<name>/card.json`:

  - `descriptor` — the LOCKED identity text (face, hair, build, wardrobe, era).
    It is injected VERBATIM into every scene prompt at visuals time; the
    storyboard/script LLM never sees or rewrites it, so it cannot drift.
  - `canonical_refs` — the 1-2 cleanest reference images (or a generated master
    portrait). The SAME anchor image(s) are passed to the image model for every
    scene — never a random folder pick — which is the main anti-drift mechanism.

Keyless fallback: without an LLM key the card still builds (name-based descriptor,
first image as anchor) so the pipeline never hard-requires a vision model.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_ANALYZED = 4    # vision passes per build (cost guard)
MAX_SCENE_REFS = 3  # nano-banana edit handles ~3 reference images well

PORTRAIT_PROMPT = (
    "A single neutral three-quarter portrait of this exact person, head and shoulders, "
    "plain dark background, even soft lighting, facing slightly left, calm expression. "
    "Reproduce the face, hair, and facial hair from the reference exactly."
)


class CharacterCard(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)   # story spellings: "Gurdjieff", "G.I. Gurdjieff"
    descriptor: str = ""                               # locked identity text (verbatim at render time)
    canonical_refs: list[str] = Field(default_factory=list)  # filenames inside the character dir
    source_images: int = 0
    built_at: str = ""
    note: str = ""


def char_dir(root: Path, name: str) -> Path:
    return root / name


def card_path(root: Path, name: str) -> Path:
    return char_dir(root, name) / "card.json"


def _images(d: Path) -> list[Path]:
    return sorted(p for p in d.iterdir()
                  if p.suffix.lower() in IMAGE_EXTS and not p.name.startswith("_"))


def load_card(root: Path, name: str) -> CharacterCard:
    return CharacterCard.model_validate_json(card_path(root, name).read_text())


def roster(root: Path) -> dict[str, CharacterCard]:
    """All built cards under the root, keyed by character name."""
    out: dict[str, CharacterCard] = {}
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "card.json").exists():
            c = load_card(root, d.name)
            out[c.name] = c
    return out


def anchor_refs(card: CharacterCard, root: Path) -> list[Path]:
    """Absolute paths of the card's canonical anchor images (existing only)."""
    d = char_dir(root, card.name)
    return [d / r for r in card.canonical_refs if (d / r).exists()]


def _analyze_one(img: Path) -> dict | None:
    """One vision pass → identity observations + a quality score for anchor ranking."""
    try:
        from studio.providers import llm
        system = ("You describe a character's PERMANENT visual identity from one image, "
                  "for reuse across many illustrations.")
        user = (
            "Describe the person/figure in this image. Respond ONLY JSON: "
            '{"face": "<face shape, eyes, distinguishing features>", '
            '"hair": "<hair + facial hair>", "build": "<age, build, posture>", '
            '"wardrobe": "<typical clothing>", "era": "<period/setting if evident>", '
            '"face_visible": <0-1 how clearly the face reads>, '
            '"clean": <0-1 image cleanliness: single subject, no text, no crop damage>}')
        return json.loads(llm.vision_json(img, system, user))
    except Exception:
        return None


def _age_clause(age_shift: int) -> str:
    if not age_shift:
        return ""
    direction = "younger" if age_shift < 0 else "older"
    return (f" Depict the character {abs(age_shift)} years {direction} than observed: "
            f"state the resulting apparent age explicitly and adjust hair/skin/posture "
            f"to match, keeping every identifying feature.")


def _merge_descriptor(name: str, obs: list[dict], provider: str,
                      age_shift: int = 0) -> tuple[str, list[str]]:
    """Merge per-image observations into ONE locked descriptor paragraph."""
    try:
        from studio.providers import llm
        system = ("You write a single LOCKED character descriptor for an illustrator. "
                  "Only include attributes consistent across observations. Concrete and "
                  "visual; no story, no personality. One paragraph, <= 60 words."
                  + _age_clause(age_shift))
        user = (f"Character name: {name}\nObservations from {len(obs)} reference images:\n"
                + json.dumps(obs, indent=1)
                + '\nRespond ONLY JSON: {"descriptor": "<paragraph>", '
                  '"aliases": ["<common name variants seen in stories>"]}')
        d = json.loads(llm.complete(provider, system, user))
        return d.get("descriptor", ""), [a for a in d.get("aliases", []) if a]
    except Exception:
        return "", []


def build_card(root: Path, name: str, provider: str = "gemini",
               portrait_provider: str = "", style: str = "",
               age_shift: int = 0) -> CharacterCard:
    """Analyze `<root>/<name>/` and write card.json. Optionally render a master
    portrait (portrait_provider, e.g. fal-nanobanana) that becomes THE single anchor —
    one canonical image beats several inconsistent folder photos for drift."""
    d = char_dir(root, name)
    imgs = _images(d)
    if not imgs:
        raise FileNotFoundError(f"no reference images in {d}")

    obs = []
    for img in imgs[:MAX_ANALYZED]:
        o = _analyze_one(img)
        if o:
            o["_file"] = img.name
            obs.append(o)

    if obs:
        descriptor, aliases = _merge_descriptor(name, obs, provider, age_shift)
        # anchor = the cleanest, most face-forward reference
        ranked = sorted(obs, key=lambda o: (float(o.get("face_visible", 0)) +
                                            float(o.get("clean", 0))), reverse=True)
        canonical = [ranked[0]["_file"]]
        note = f"vision-built from {len(obs)}/{len(imgs)} images"
    else:
        # keyless / offline fallback — never block the pipeline
        descriptor, aliases = f"the character {name} exactly as shown in the reference image", []
        canonical = [imgs[0].name]
        note = "stub card (no vision key) — descriptor is name-only"

    if portrait_provider:
        from studio.providers import image
        pdst = d / "_portrait.png"
        prompt = PORTRAIT_PROMPT + _age_clause(age_shift) + (f" Art style: {style}." if style else "")
        image.generate(portrait_provider, prompt, pdst, refs=[d / canonical[0]])
        canonical = [pdst.name]  # the portrait becomes the one true anchor
        note += " + master portrait anchor"

    card = CharacterCard(name=name, aliases=aliases, descriptor=descriptor,
                         canonical_refs=canonical, source_images=len(imgs),
                         built_at=time.strftime("%Y-%m-%dT%H:%M:%S"), note=note)
    card_path(root, name).write_text(card.model_dump_json(indent=2))
    return card


def build_card_from_text(root: Path, name: str, story_text: str,
                         provider: str = "gemini", age_shift: int = 0) -> CharacterCard:
    """Text-derived card for a character with NO reference images: analyze the WHOLE
    story once, pull every physical detail the prose gives, and where the text is
    silent INVENT plausible era-consistent specifics — then COMMIT to them. The point
    is a constant shape: one locked descriptor decided up front and reused verbatim on
    every scene, instead of the image model re-imagining the character each time."""
    d = char_dir(root, name)
    d.mkdir(parents=True, exist_ok=True)
    descriptor, aliases = "", []
    try:
        from studio.providers import llm
        system = (
            "You build a LOCKED visual identity card for a story character who has no "
            "reference image. Read the ENTIRE story first. Extract every physical "
            "characteristic the text states or implies (age, face, hair, facial hair, "
            "build, wardrobe, era, distinguishing marks). Where the story is silent, "
            "INVENT concrete, plausible specifics consistent with the era and the "
            "character's role — and commit to them; vague words like 'average' are "
            "forbidden because the descriptor must render identically every time. "
            "Concrete and visual; no personality, no plot. One paragraph, <= 60 words."
            + _age_clause(age_shift))
        user = (f"Character: {name}\n\nSTORY:\n{story_text}\n\n"
                'Respond ONLY JSON: {"descriptor": "<paragraph>", '
                '"aliases": ["<name variants used in the story>"]}')
        data = json.loads(llm.complete(provider, system, user))
        descriptor = data.get("descriptor", "")
        aliases = [a for a in data.get("aliases", []) if a]
    except Exception:
        pass
    if not descriptor:  # keyless fallback: still a stable (if thin) identity
        descriptor = f"the character {name}, drawn identically in every scene"
    card = CharacterCard(name=name, aliases=aliases, descriptor=descriptor,
                         canonical_refs=[], source_images=0,
                         built_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                         note="text-derived (no reference images) — descriptor is the anchor")
    card_path(root, name).write_text(card.model_dump_json(indent=2))
    return card


def scene_identity_block(cards: list[CharacterCard],
                         with_refs: list[CharacterCard] | None = None) -> str:
    """The verbatim identity preamble for a multi-character scene prompt.

    `with_refs` = the subset whose anchor images are attached, in the SAME ORDER as
    the images. Text-derived cards (no reference image) are described from their
    locked descriptor alone — same constant identity, different anchor medium."""
    ref_cards = with_refs if with_refs is not None else [c for c in cards if c.canonical_refs]
    parts = []
    for i, c in enumerate(ref_cards, 1):
        parts.append(f"Reference image {i} shows {c.name}: {c.descriptor}")
    for c in cards:
        if c not in ref_cards:
            parts.append(f"{c.name} (no reference image, draw from this description "
                         f"IDENTICALLY in every scene): {c.descriptor}")
    parts.append("Keep every character's face, hair, and build EXACTLY consistent — "
                 "matching their reference image or description; change only pose, "
                 "action, and setting.")
    return " ".join(parts)


def match_names(text: str, cards: dict[str, CharacterCard]) -> list[str]:
    """Which roster characters are mentioned in a text chunk (name or alias)."""
    low = text.lower()
    hits = []
    for name, c in cards.items():
        needles = [name] + list(c.aliases)
        if any(n.lower() in low for n in needles if n):
            hits.append(name)
    return hits
