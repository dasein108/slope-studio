"""Build runs/first-sorrow/01_script.json — Kafka's 'First Sorrow' (Erstes Leid).

Public-domain parable (Muir translation), read over hand-built noir illustration.
LANDSCAPE 16:9. Same series look as 'Before the Law' / 'An Imperial Message'.

CHEAP build: short (~16 Nano-Banana stills, no silent interludes), minimal sound —
keeps the series quality/style while spending the least (stills dominate cost).
Continuity blocks (THE ARTIST / THE MANAGER / THE DOME / THE TRAIN) reused verbatim;
`kinetic` only on title / the cry / outro; lateral motion only; no captions.
"""
from __future__ import annotations

import json
from pathlib import Path

STYLE = (
    "high-contrast black-and-white ink-noir, German-expressionist woodcut shadows, "
    "Kafkaesque, monochrome charcoal and ash-grey, deep crushed blacks, harsh "
    "chiaroscuro rim-light, fine film grain, looming oppressive architecture, "
    "lonely tiny figures, a SINGLE small warm yellow light accent as the only color, "
    "cinematic 16:9 widescreen, wide horizontal composition"
)
MUSIC = (
    "slow ominous instrumental, deep double-bass drone, sparse detuned piano, "
    "distant cello, cold and vast, minimal, cinematic noir, no melody"
)

# --- CANONICAL SUBJECT BLOCKS (reuse verbatim for continuity) ---
ART = ("the same trapeze artist: a slender pale man in a plain pale acrobat's leotard, lean and "
       "graceful, a smooth childlike face, perched high on a single trapeze bar")
MGR = ("the same manager: a stout balding impresario in a dark travelling suit and waistcoat, "
       "anxious watchful eyes, a book in his hand")
DOME = ("the same vast vaulted dome of a grand variety theatre, immense shadowed rafters and "
        "ropes, a single shaft of warm yellow sunlight pouring from a high side window")
TRAIN = ("the same night train compartment, the artist up on the luggage rack, the manager in "
         "the opposite window seat, a warm yellow window-glow")

S = []
def add(visual, narration, animator, transition="fade", atmosphere="", ost="",
        hint="", tone="", sfx=None, secs=0.0):
    S.append(dict(visual=visual, narration=narration, animator=animator,
                  transition=transition, atmosphere=atmosphere, ost=ost,
                  hint=hint, tone=tone, sfx=sfx or [], secs=secs))

# ---------------- FIRST SORROW ----------------
add(f"{DOME}, a tiny lone figure on a trapeze suspended in the immense height",
    "First Sorrow.", "kinetic", transition="cut", ost="FIRST SORROW",
    hint="title under the dome", secs=5.0,
    sfx=[("a faint vast empty-theatre hush", 0.0, 3, -12)])

add(f"{ART}, alone in {DOME}",
    "A trapeze artist — practicing high in the vaulted domes of the great variety theaters — "
    "had so arranged his life that he never came down from his trapeze, by night or day.",
    "parallax", hint="the lone artist aloft, ropes drifting")

add(f"the height of {DOME} seen from far below, small specially-built containers being hauled "
    "up on long ropes toward the distant artist",
    "At first only from a desire to perfect his skill; but later, because custom was too strong "
    "for him. His modest needs were supplied by relays of attendants who watched from below.",
    "static", hint="dizzying height, ropes and containers")

add(f"{MGR} standing on the empty stage far below, gazing thoughtfully up toward {ART} almost "
    "beyond eyeshot",
    "The management overlooked the distraction he caused, because he was an extraordinary and "
    "unique artist — only this way could he keep his art at the pitch of perfection.",
    "motion-driftright", hint="the manager looks up the great height")

add(f"{DOME}, the side windows thrown open, shafts of warm golden sunlight and fresh air pouring "
    "into the dusky vault around the small figure of {ART}",
    "It was healthful up there; and when the side windows were thrown open and sun and fresh air "
    "came pouring into the dusky vault, it was even beautiful.",
    "parallax", hint="golden light pours through the dome")

add(f"{ART} and a fellow acrobat sitting together on the trapeze, leaning against the ropes, a "
    "workman's face at a distant open window",
    "His social life was limited — sometimes a fellow acrobat climbed up, or a workman exchanged "
    "a few words through an open window. Otherwise nothing disturbed his seclusion.",
    "static", hint="two on the trapeze in the height")

add(f"{ART} aloft but tense and restless, the warm dome light dimming, a sense of unease",
    "He could have gone on living peacefully like that — had it not been for the inevitable "
    "journeys from place to place, which he found extremely trying.",
    "motion-driftleft", hint="unease creeps in")

add(f"a racing automobile whirling through empty night streets at breakneck speed, {ART} a tense "
    "shape inside, a single warm streetlamp streaking past",
    "For town travel, racing automobiles whirled him through the empty streets by night at "
    "breakneck speed — too slow, all the same, for the artist's impatience.",
    "slice", transition="cut", hint="the speeding car at night",
    sfx=[("a car rushing past at speed on empty streets", 0.2, 2, -9)])

add(f"{TRAIN}, {ART} lying uncomfortably along the luggage rack near the ceiling of the compartment",
    "For railway journeys, a whole compartment was reserved, where he passed the time up on the "
    "luggage rack. The manager never knew a happy moment until the artist hung aloft again.",
    "static", hint="the artist on the luggage rack",
    sfx=[("rhythmic night train clatter on the rails", 0.3, 3, -11)])

add(f"{TRAIN}, {ART} on the luggage rack speaking softly down, {MGR} lowering his book to listen, "
    "all attention",
    "Once, traveling together, the artist spoke in a low voice: he must always have two trapezes "
    "for his performance — two, opposite each other.",
    "motion-driftright", hint="the quiet confession in the compartment")

add(f"{TRAIN}, {ART}'s face tight with dread, {MGR} nodding carefully, watchfully feeling his way",
    "The manager at once agreed. But the artist said that never again would he perform on only "
    "one trapeze — in no circumstances whatever. The very idea seemed to make him shudder.",
    "static", hint="the shudder, the dread")

add(f"{TRAIN}, {ART} suddenly weeping, {MGR} sprung up onto the seat, caressing him cheek to "
    "cheek, the manager's face wet with the artist's tears",
    "At that, the trapeze artist suddenly burst into tears. The manager sprang up, climbed onto "
    "the seat, and caressed him, cheek to cheek, his own face wet with the artist's tears.",
    "slice", hint="the emotional break")

add(f"a tight view of {ART}'s weeping childlike face, his hands clutching an imagined single bar, "
    "one tear catching the warm light",
    "'Only the one bar in my hands — how can I go on living!'", "kinetic",
    ost="HOW CAN I GO ON", hint="the cry", tone="sad")

add(f"{TRAIN}, {MGR} back in his corner, pretending calm but glancing secretly over the top of "
    "his book at the artist, deep uneasiness on his face",
    "The manager promised to wire for a second trapeze, and reassured him little by little. But he "
    "himself was far from reassured — glancing secretly at the artist over his book.",
    "motion-driftleft", hint="the manager's hidden dread")

add(f"an extreme close view of {ART}'s smooth childlike forehead as he sleeps, the very first "
    "faint furrows of care beginning to engrave themselves, a thin line of warm light across him",
    "Once such ideas begin to torment a man, would they ever leave him? And indeed, on that "
    "smooth, childlike forehead, he believed he could see the first furrows of care.",
    "static", tone="sad", hint="the first sorrow on the brow")

add("a black frame with the author's name in small ash-grey letters, a faint warm-yellow "
    "underline, silence",
    "Franz Kafka.", "kinetic", transition="fadeblack", ost="FRANZ KAFKA",
    hint="closing card", secs=5.0)

# ---------------- assemble + tile timing ----------------
def dur_for(sc):
    if sc["secs"]:
        return float(sc["secs"])
    w = len(sc["narration"].split())
    if sc["animator"] == "kinetic" and w <= 5:
        return 5.0
    return max(6.0, min(18.0, round(w / 2.3, 1)))

scenes = []
t = 0.0
for i, sc in enumerate(S, start=1):
    d = dur_for(sc)
    scene = {
        "id": i, "start_s": round(t, 2), "end_s": round(t + d, 2),
        "visual_prompt": f"{STYLE}, {sc['visual']}", "narration": sc["narration"],
        "on_screen_text": sc["ost"], "motion_hint": sc["hint"],
        "image_role": "hero" if sc["animator"] in ("parallax", "slice") else "",
        "animator": sc["animator"], "transition": sc["transition"], "transition_dur": 0.5,
    }
    if sc["atmosphere"]:
        scene["atmosphere"] = sc["atmosphere"]
    if sc["tone"]:
        scene["tone"] = sc["tone"]
    if sc["sfx"]:
        scene["sfx"] = [{"prompt": p, "at": a, "dur": dd, "gain_db": g}
                        for (p, a, dd, g) in sc["sfx"]]
    scenes.append(scene)
    t += d

doc = {
    "topic": "First Sorrow — a parable by Franz Kafka",
    "duration_s": int(round(t)), "aspect": "16:9", "voice": True,
    "voice_name": "narrator", "tone": "serious",
    "style": "Kafkaesque noir, B/W ink-woodcut with one warm-yellow accent; grave, literary",
    "character": STYLE, "music": MUSIC, "scenes": scenes,
    "title": "First Sorrow — Franz Kafka | A Noir Reading",
    "description": (
        "Franz Kafka's parable 'First Sorrow' (Erstes Leid), read over hand-built black-and-"
        "white noir illustration. A trapeze artist who will not come down, the manager who "
        "frets below, and the first furrows of care on a childlike brow.\n\nText: public domain "
        "(Muir translation). Part of a Kafka noir series with 'Before the Law' and 'An Imperial "
        "Message'."
    ),
    "hashtags": ["#kafka", "#firstsorrow", "#literature", "#noir", "#shortfilm", "#audiobook"],
}

out = Path("runs/first-sorrow/01_script.json")
out.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
print(f"wrote {out}  scenes={len(scenes)}  planned={t:.1f}s (~{t/60:.1f} min)  "
      f"est stills=${len(scenes)*0.039:.2f}")
