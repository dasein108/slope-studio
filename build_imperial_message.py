"""Build runs/imperial-message/01_script.json — Kafka's 'An Imperial Message' (Part II).

Public-domain parable (Muir translation), read in full over hand-built noir
illustration. LANDSCAPE 16:9, ~5 min. Same series look as 'Before the Law'.

Improved rules applied:
- CONTINUITY (guides #13): each recurring subject has ONE canonical description block
  (THE EMPEROR / THE MESSENGER / THE SUN EMBLEM / THE PALACE / THE THRONG / YOU) pasted
  VERBATIM into every scene that shows it — so the messenger is the same man, the palace
  the same place, every cut.
- `kinetic` only on explicit need (title, the crushing climax, outro) — guides #12/RULE.
- fill-zoom is enforced in ffmpeg.kinetic (full image at widest → zoom in).
- lateral motion only (parallax/slice/drift/static), no pulse/zoom; variety <=2 per 60s.
- tight silent interludes (~5-6s) carried by the music bed; sparse sound; no captions.
"""
from __future__ import annotations

import json
from pathlib import Path

# Same series style string as 'Before the Law' (verbatim) — keeps the two films a set.
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
EMP = ("the same dying emperor: a gaunt aged face, hollow cheeks, a thin long white beard, "
       "heavy black imperial robes bearing a small golden sun emblem, propped on a vast "
       "canopied deathbed, one warm candle beside him")
MSG = ("the same messenger: a powerful broad-shouldered man, shaved head, a plain dark belted "
       "tunic, a blazing golden SUN emblem on his chest, a worn leather message-pouch, a fierce "
       "set jaw")
SUN = "the golden sun emblem blazing — the only warm color in the frame"
HALL = ("the same imperial palace: an endless black labyrinth of colossal columns and vast "
        "open mounting staircases, cold grey stone, German-expressionist perspective")
THRONG = "the same throng: an oceanic endless crowd of dim faceless shadow-figures, no end in sight"
YOU = ("the same lone reader: a small dark silhouette seated at a window at dusk, one warm "
       "yellow lamp, a quiet evening sky beyond")

S = []
def add(visual, narration, animator, transition="fade", atmosphere="", ost="",
        hint="", tone="", sfx=None, secs=0.0):
    S.append(dict(visual=visual, narration=narration, animator=animator,
                  transition=transition, atmosphere=atmosphere, ost=ost,
                  hint=hint, tone=tone, sfx=sfx or [], secs=secs))

def interlude(visual, animator, hint, atmosphere="", secs=5.5, transition="fade", sfx=None):
    add(visual, "", animator, transition=transition, atmosphere=atmosphere,
        hint=hint, sfx=sfx, secs=secs)

# ---------------- AN IMPERIAL MESSAGE ----------------
add(f"{HALL}, a single huge disc of warm yellow imperial sun-light high in the gloom, a tiny "
    "shadow-subject cowering far below",
    "An Imperial Message.", "kinetic", transition="cut", atmosphere="fog",
    ost="AN IMPERIAL MESSAGE", hint="title under the imperial sun", secs=5.0,
    sfx=[("a distant solemn imperial bell", 0.0, 3, -10)])

interlude(f"a vast black palace under a low sky, an immense glowing yellow imperial sun high "
          f"above, and far below {YOU} dwarfed to an insignificant speck",
          "parallax", "clouds drift across the wide sky, the tiny figure fixed far below",
          atmosphere="wind", secs=6.0)

add(f"{EMP}, the cavernous dark throne-chamber around him drained to grey",
    "The Emperor — so the parable runs — has sent a message to you.", "static",
    hint="the dying emperor, still and severe")

add(f"{STYLE}, an immense dark hall, and far at the bottom {YOU}, a single insignificant "
    "shadow dwarfed beneath the glowing yellow imperial sun",
    "To you: the humble subject, the insignificant shadow cowering in the remotest distance "
    "before the imperial sun.",
    "parallax", hint="huge sun above, tiny shadow below")

add(f"{EMP}, seen closer, his hollow eyes turned toward you, the candle trembling",
    "The Emperor, from his deathbed, has sent a message to you alone.", "motion-driftleft",
    hint="a slow lateral push toward the dying emperor")

add(f"{EMP}, and {MSG} kneeling close at the bedside as the emperor whispers into his ear, "
    "the candle the only light in the black hall",
    "He commanded the messenger to kneel by the bed, and whispered the message to him.",
    "static")

add(f"a tight view of {EMP}'s lips at {MSG}'s ear, the secret passing back, intense and intimate",
    "So much store did he lay on it that he made the messenger whisper it back into his ear again.",
    "motion-driftright", hint="slow lateral push across the whisper")

add(f"{EMP} giving a slow final nod of confirmation, eyes half-closed, the warm candle steady",
    "Then, by a nod of the head, he confirmed that it was right.", "static")

interlude(f"{HALL}, the obstructing walls broken away, a ring of shadowy princes of the Empire "
          "standing in tiers on the mounting staircases beneath a pale sky",
          "parallax", "the ringed princes on the vast staircases, sky drifting", secs=6.0)

add(f"{HALL}, the great princes of the Empire ringed on the broken-open staircases, every face "
    "turned inward",
    "Before the assembled spectators of his death — the walls broken down, the princes of the "
    "Empire ringed on the mounting staircases —",
    "parallax", hint="vast staircases, ring of princes")

add(f"{EMP} on his bier raising the sealed message before the ringed court, a single warm glint "
    "on the letter",
    "before all these, he delivered his message.", "static")

interlude(f"{HALL}, the ring of shadowy princes holding in utter silence on the vast staircases, "
          "the sealed message glinting far below, dust in the cold air",
          "motion-driftleft", "a slow glide across the silent ringed court", secs=5.5)

add(f"{MSG} bursting forward out of the palace gates, {SUN}, motion and shadow, a corridor of "
    "columns behind him",
    "The messenger set out at once — a powerful, an indefatigable man.", "slice",
    transition="cut", hint="diagonal reveal, the messenger strides out",
    sfx=[("determined marching footsteps begin on stone", 0.3, 2, -9)])

add(f"{MSG} shoving through {THRONG}, one arm then the other, endless heads stretching away, "
    f"{SUN} cutting through",
    "Now with his right arm, now with his left, he cleaves a way through the throng.",
    "motion-driftright", hint="pushing laterally through the crowd")

add(f"a close view of {MSG}'s chest where {SUN}, hands parting before it, the way opening",
    "Where he meets resistance he points to his breast, where the symbol of the sun glitters,",
    "static")

add(f"{MSG} striding on as {THRONG} parts before him, the way made smooth",
    "and the way is made easier for him than for any other man.",
    "motion-driftright")

interlude(f"{THRONG} filling a vast plain to the horizon under a heavy sky, no edge, no end",
          "parallax", "the endless throng, depth to the horizon", atmosphere="wind", secs=6.0)

add(f"{MSG} small amid {THRONG}, the crowd swallowing the hall in every direction",
    "But the multitudes are so vast. Their numbers have no end.", "parallax",
    hint="endless crowd around the messenger")

add(f"{MSG} imagined flying free across open moonlit fields toward {YOU} at a single distant "
    "lit window, hope streaking past",
    "Could he reach the open fields, how fast he would fly — and soon you would hear his fists "
    "hammering at your door.",
    "motion-driftleft", hint="imagined flight drifts across")

interlude(f"a single distant lit window across dark empty fields at night — {YOU} waiting, the "
          "one warm lamp a tiny point in the vast dark",
          "static", "the far waiting window, held and still", secs=5.5)

add(f"{MSG} sagging exhausted against a black column deep in {HALL}, the sun emblem dimmed",
    "But instead — how vainly he wears out his strength.", "static")

add(f"{HALL}, chambers opening one into another into darkness, {MSG} a small figure swallowed "
    "within",
    "Still he is crossing the chambers of the innermost palace — never will he reach their end.",
    "motion-driftright", hint="endless halls sliding past")

add(f"{HALL}, a colossal descending staircase with {MSG} going down and down, more stairs below, "
    "no bottom",
    "And if he did, nothing would be gained: he must fight down the great stair; and if he did, "
    "nothing would be gained.",
    "motion-driftdown", hint="descending the endless stair",
    sfx=[("echoing footfalls descending stone steps", 0.4, 3, -10)])

add(f"{HALL}, an impossible vista of courts, palaces, stairs and more courts repeating to the "
    "horizon, centuries layered in stone",
    "The courts must be crossed; then the second outer palace; more stairs, more courts; another "
    "palace; and so on, for thousands of years.",
    "kinetic", ost="THOUSANDS OF YEARS", hint="endless architecture")

add(f"{HALL}, the outermost gate ahead at last, blinding warm light beyond — but a black bar "
    "slams across, the way forever denied",
    "And should he ever burst through the outermost gate — but never, never can that happen —",
    "slice", transition="cut", hint="gate denied, light barred")

interlude(f"{HALL}, the colossal outermost gate looming shut, a thin blade of warm light dying "
          "at its seam, the messenger a speck before it",
          "motion-driftleft", "a slow drift across the sealed outermost gate", secs=5.5)

interlude(f"the imperial capital sprawling to the edge of the world, drowned in its own grey "
          "sediment, smoke and haze, a faint sick-yellow sun",
          "parallax", "the vast choked capital", atmosphere="fog", secs=6.0)

add("the imperial capital, the center of the world, crammed to bursting with its own sediment, "
    "a faint sick-yellow sun above",
    "the imperial capital would lie before him — the center of the world, drowned in its own "
    "sediment.",
    "motion-driftright", hint="slow pan across the vast choked city")

add(f"{HALL}, an empty throne-hall, the message undelivered, dust in a cold shaft of grey light, "
    "absolute stillness",
    "No one could fight his way through here — not even with a message from a dead man.",
    "static", transition="fadeblack")

add(f"{YOU}, dreaming, evening clouds and the first stars beyond the glass, one warm lamp inside",
    "But you sit at your window when evening falls — and dream it to yourself.",
    "parallax", tone="sad", hint="window at evening, stars, one warm lamp",
    sfx=[("faint quiet evening crickets and soft wind", 0.5, 4, -12)])

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
    return max(6.0, min(15.0, round(w / 2.3, 1)))

scenes = []
t = 0.0
for i, sc in enumerate(S, start=1):
    d = dur_for(sc)
    visual = sc["visual"] if sc["visual"].startswith(STYLE) else f"{STYLE}, {sc['visual']}"
    scene = {
        "id": i, "start_s": round(t, 2), "end_s": round(t + d, 2),
        "visual_prompt": visual, "narration": sc["narration"],
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
    "topic": "An Imperial Message — a parable by Franz Kafka",
    "duration_s": int(round(t)), "aspect": "16:9", "voice": True,
    "voice_name": "narrator", "tone": "serious",
    "style": "Kafkaesque noir, B/W ink-woodcut with one warm-yellow accent; grave, literary",
    "character": STYLE, "music": MUSIC, "scenes": scenes,
    "title": "An Imperial Message — Franz Kafka | A Noir Reading",
    "description": (
        "Franz Kafka's parable 'An Imperial Message', read in full over hand-built black-"
        "and-white noir illustration. A dying emperor's message, a tireless messenger, and "
        "the endless palace between you and the words meant for you alone.\n\nText: public "
        "domain (Muir translation). A companion to 'Before the Law'."
    ),
    "hashtags": ["#kafka", "#animperialmessage", "#literature", "#noir", "#shortfilm", "#audiobook"],
}

n_narr = sum(1 for s in scenes if s["narration"])
out = Path("runs/imperial-message/01_script.json")
out.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
print(f"wrote {out}  scenes={len(scenes)} ({n_narr} narrated + {len(scenes)-n_narr} interludes)  "
      f"planned={t:.1f}s (~{t/60:.1f} min)")
