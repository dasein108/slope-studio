"""Build runs/before-the-law/01_script.json — Kafka's 'Before the Law' (Part I).

Public-domain parable (Muir translation) read in full over hand-built noir
illustration. LANDSCAPE 16:9 (classic YouTube), ~8-9 min.

Aesthetic: high-contrast B/W ink-noir, German-expressionist, the ONLY color a
small warm YELLOW accent (the gateway's radiance). Lateral motion only (parallax
multi-layer + drift + slice reveals + honest static); NO zoom/pulse/kenburns-
dominant, NO manim. Sparse sound. Narrated beats carry the text; silent cinematic
INTERLUDES (no narration → held for their planned duration, carried by the music
bed + atmosphere) give breathing room and push the runtime to ~8-9 min without
slowing the read.
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

S = []
def add(visual, narration, animator, transition="fade", atmosphere="", ost="",
        hint="", tone="", sfx=None, secs=0.0):
    S.append(dict(visual=visual, narration=narration, animator=animator,
                  transition=transition, atmosphere=atmosphere, ost=ost,
                  hint=hint, tone=tone, sfx=sfx or [], secs=secs))

def interlude(visual, animator, hint, atmosphere="", secs=11.0, transition="fade", sfx=None):
    # silent held beat (no narration). Carried by the music bed + atmosphere.
    add(visual, "", animator, transition=transition, atmosphere=atmosphere,
        hint=hint, sfx=sfx, secs=secs)

# ---------------- BEFORE THE LAW ----------------
add("an immense black iron gate filling a fortress wall, a thin seam of warm yellow light "
    "leaking from the crack, fog, a tiny silhouette far below to the left",
    "Before the Law.", "kinetic", transition="cut", atmosphere="fog",
    ost="BEFORE THE LAW", hint="title looms", secs=5.0,
    sfx=[("low hollow wind drone, cold", 0.0, 4, -10)])

interlude("a wide bleak plain at dawn under an enormous sky of slow grey clouds, the black "
          "gate a distant monolith on the right horizon, a thin yellow thread at its base",
          "parallax", "clouds drift across the wide sky, gate fixed far right",
          atmosphere="wind", secs=12.0)

add("a gaunt doorkeeper in a heavy fur coat standing before a towering gate, big sharp nose, "
    "long thin black Tartar beard, severe, lit from one side, yellow lamp behind him",
    "Before the Law stands a doorkeeper.", "static", hint="severe portrait, still")

add("a weary man from the country in worn travelling clothes approaching a colossal gateway "
    "from the left across a bare plain, vast clouded sky, the man small and bent",
    "To this doorkeeper there comes a man from the country, and prays for admittance to the Law.",
    "parallax", atmosphere="wind", hint="clouds drift, figure small at left")

add("the fur-coated doorkeeper raising one flat hand to bar the way, cold and indifferent, "
    "harsh shadow across his face, wide empty hall behind",
    "But the doorkeeper says that he cannot grant admittance at the moment.", "static")

add("the man from the country pausing, head tilted, weighing it, hand to his chin, the great "
    "door beside him dwarfing him on the right",
    "The man thinks it over, and then asks if he will be allowed in later.",
    "motion-driftright", hint="slow lateral drift")

add("a sliver of warm yellow light through the half-open gate, the doorkeeper's silhouette to "
    "one side, darkness spreading wide",
    "'It is possible,' says the doorkeeper, 'but not at the moment.'", "kinetic",
    ost="NOT YET", hint="line lands over the glowing seam")

add("the man stooping low to peer through the open gateway, a long corridor receding into "
    "dim golden haze beyond, his shadow stretched long across the threshold",
    "Since the gate stands open, as usual, and the doorkeeper steps aside, the man stoops to "
    "peer through the gateway into the interior.",
    "slice", transition="cut", hint="diagonal reveal of the glowing interior")

interlude("the deep interior corridor of the Law seen through the gate — receding arches and a "
          "distant warm yellow radiance, dust in the still air, no figures",
          "motion-driftright", "slow lateral glide down the glowing corridor", secs=12.0,
          sfx=[("faint deep resonant hum from a vast hall", 0.3, 4, -12)])

add("the doorkeeper thrown back in a cold mocking laugh, mouth open, teeth and shadow, the "
    "yellow lamp glinting in one eye",
    "Observing that, the doorkeeper laughs and says: 'If you are so drawn to it, just try to "
    "go in despite my veto.'",
    "static")

add("the doorkeeper looming huge on the left, the man tiny at his feet on the right, behind "
    "them a row of ever larger gates fading into the dark",
    "'But take note: I am powerful. And I am only the least of the doorkeepers.'",
    "parallax", hint="keeper looms near-left, gates recede far-right",
    sfx=[("distant heavy footstep echo in stone hall", 0.5, 2, -11)])

add("an endless corridor of identical iron gates stretching to the right, a doorkeeper at "
    "each, each one larger and darker than the last, vanishing into blackness",
    "'From hall to hall there is one doorkeeper after another, each more powerful than the last.'",
    "motion-driftright", hint="lateral pan down the receding corridor")

add("a vast formless darkness with one monstrous shadowed silhouette far off, too terrible to "
    "see clearly, a faint cold glow behind it",
    "'The third doorkeeper is already so terrible that even I cannot bear to look at him.'",
    "static", transition="fadeblack")

interlude("the wide grey sky above the gate darkening, heavy clouds rolling sideways, the gate "
          "small and black beneath, the yellow seam barely visible",
          "motion-driftright", "storm clouds roll sideways across the wide sky",
          atmosphere="wind", secs=12.0)

add("the man from the country recoiling a half-step, uncertainty on his face, the cold plain "
    "and clouded sky stretching behind him",
    "These are difficulties the man from the country has not expected.",
    "motion-driftleft", hint="small backward drift")

add("the small man standing under an enormous indifferent sky of moving grey clouds, the gate "
    "a black monolith on the horizon, a thread of yellow at its base",
    "The Law, he thinks, should surely be accessible at all times and to everyone.",
    "parallax", hint="huge wide sky, clouds, man tiny")

add("a tight portrait of the doorkeeper's face — fur collar, big sharp nose, long thin black "
    "Tartar beard, deep-set eyes, every hair etched, a single warm highlight",
    "But taking a closer look at the doorkeeper in his fur coat, with his big sharp nose and "
    "long thin black Tartar beard, he decides it is better to wait for permission.",
    "static")

add("the man seated on a low wooden stool at the side of the great door on the right, hunched "
    "and small, the yellow lamp above him, long shadow across the wide flagstones",
    "The doorkeeper gives him a stool, and lets him sit down at one side of the door.",
    "parallax", hint="figure fixed on stool right, lamp and door behind")

interlude("a wide dusk view of the great door, the lone seated man tiny at its base, a warm "
          "yellow lamp glowing, long blue shadows stretching across the empty courtyard",
          "motion-driftleft", "slow lateral glide across the silent courtyard", secs=11.0)

add("a single stool beside the immense door as the sky behind streaks with racing clouds and "
    "wheeling stars, seasons blurring, the man aging in place",
    "There he sits — for days, and years.", "kinetic", atmosphere="wind",
    ost="DAYS AND YEARS", hint="time rushes past the unmoving man",
    sfx=[("a single slow distant bell toll", 0.6, 3, -9)])

interlude("the night sky above the gate wheeling with cold stars and a pale thin moon, clouds "
          "sliding sideways, the seated man a tiny dark shape below, the yellow lamp a single point",
          "parallax", "stars and clouds wheel across the wide night sky, figure fixed below",
          atmosphere="wind", secs=13.0)

add("the man half-rising from his stool with a pleading gesture toward the unmoved doorkeeper, "
    "warm lamplight between them, deep shadows wide across the hall",
    "He makes many attempts to be admitted, and wearies the doorkeeper by his importunity.",
    "motion-driftleft")

add("the doorkeeper and the seated man in a pool of lamplight, the keeper questioning him with "
    "cold lordly indifference, the rest of the wide frame swallowed in black",
    "The doorkeeper often questions him about his home and many other things, but indifferently, "
    "as great lords do, always finishing that he cannot be let in yet.",
    "parallax", hint="two figures in lamplight, dark width behind")

add("the man offering up his possessions — a watch, coins, a ring — laid in the doorkeeper's "
    "open palm, the small valuables catching the only warm glint",
    "The man, who furnished himself with many things for his journey, sacrifices all he has, "
    "however valuable, to bribe the doorkeeper.",
    "motion-driftright", hint="offering drifts across")

add("the doorkeeper's cupped hand closing over the small bright coins, his face impassive in "
    "shadow above, wide darkness around",
    "The doorkeeper accepts everything, but always remarks: 'I am only taking it to keep you "
    "from thinking you have omitted anything.'",
    "static")

interlude("a still life in the dark — the man's surrendered belongings heaped at the foot of "
          "the great door, dust-covered, one coin catching a faint warm gleam",
          "motion-driftleft", "slow lateral drift across the abandoned possessions", secs=9.0)

add("the man's gaunt face turned fixedly upward, eyes locked on the doorkeeper, nothing else "
    "in the world, harsh single light",
    "Through these many years the man fixes his attention almost continuously on the doorkeeper.",
    "static")

interlude("an extreme wide close-up of the doorkeeper's impassive face filling the frame, "
          "unmoving, every etched line and shadow, a single cold warm glint in one eye",
          "motion-driftright", "imperceptible slow drift across the unmoving face", secs=10.0)

add("the doorkeeper filling the whole wide frame as a black mountain of fur and shadow, the "
    "tiny glowing gate reduced to a pinpoint far behind him",
    "He forgets the other doorkeepers; this first one seems to him the sole obstacle preventing "
    "access to the Law.",
    "parallax", hint="keeper fills frame, gate a distant point")

add("the man aged and stooped, fist half-raised in a bitter mutter, snow settling on his "
    "shoulders, the lamp guttering, wide cold hall",
    "He curses his bad luck — in his early years boldly and loudly; later, growing old, he only "
    "grumbles to himself.",
    "motion-driftleft", atmosphere="snow")

interlude("snow drifting sideways across the wide cold courtyard, settling on the stool and the "
          "shoulders of the aged man, the gate a pale ghost behind the falling snow",
          "motion-driftleft", "snow drifts sideways across the wide frame",
          atmosphere="snow", secs=10.0)

add("extreme close on the doorkeeper's fur collar, tiny fleas glinting in the warm light, the "
    "old man's withered hand reaching toward them, pitiful",
    "He becomes childish, and having come to know even the fleas in the fur collar, he begs the "
    "fleas too to help him and change the doorkeeper's mind.",
    "motion-driftright", hint="slow drift across the collar")

interlude("rain falling across the wide black face of the great gate, the yellow seam blurred "
          "and weeping, the small hunched figure barely visible at its foot",
          "parallax", "rain streams down, clouds drift behind the gate",
          atmosphere="rain", secs=11.0,
          sfx=[("soft steady rain on stone", 0.2, 6, -12)])

add("the world dimming to near-black around the seated old man, fog swallowing the wide edges, "
    "only faint shapes, his clouded eyes",
    "At length his eyesight begins to fail, and he does not know whether the world is really "
    "darker, or his eyes only deceive him.",
    "static", atmosphere="fog", transition="fadeblack",
    sfx=[("very slow faint heartbeat", 0.5, 4, -11)])

add("out of the surrounding blackness a brilliant inextinguishable column of warm YELLOW "
    "radiance streaming from the gateway of the Law, the old man's silhouette small before it",
    "Yet in his darkness he is now aware of a radiance that streams inextinguishably from the "
    "gateway of the Law.",
    "motion-driftup", tone="mystical", hint="rise gently toward the glow")

interlude("the warm yellow radiance of the Law filling the gateway, pouring out into the dark, "
          "the frail silhouette of the old man dissolving at the edge of the light",
          "motion-driftup", "a slow reverent rise into the radiance", secs=9.0)

add("the old man collapsed small on the stool, barely a shape, the great door towering above "
    "him on the right, his life almost spent, faint warm light",
    "Now he has not very long to live.", "parallax", hint="tiny figure left, door looms right")

add("a tight portrait of the dying man's face, eyes inward, a lifetime of waiting gathering to "
    "a single point behind his brow",
    "Before he dies, all his experiences gather in his head to one point — a question he has not "
    "yet asked the doorkeeper.",
    "static")

add("the old man's trembling hand beckoning weakly, unable to lift his stiffening body from the "
    "stool, the keeper a tall shadow leaning in",
    "He waves him nearer, since he can no longer raise his stiffening body.",
    "motion-driftleft")

add("the towering doorkeeper bending all the way down to the shrunken old man, the enormous "
    "difference in their heights, lamp between them, wide black hall",
    "The doorkeeper has to bend low toward him, for the difference in height between them has "
    "altered much to the man's disadvantage.",
    "parallax", hint="tall keeper bends over tiny man")

interlude("a held wide two-shot in deep shadow: the immense bent doorkeeper and the dying tiny "
          "man at the door, the warm lamp between them, utter stillness",
          "motion-driftright", "a slow drift across the breathless final stillness", secs=9.0)

add("the doorkeeper's face close, brow raised, cold and weary, asking, a hard glint of warm "
    "light in his eye",
    "'What do you want to know now?' asks the doorkeeper. 'You are insatiable.'",
    "motion-driftleft")

add("the withered old man whispering his last question upward, lips barely parted, the gate's "
    "faint warm glow on his face",
    "'Everyone strives to reach the Law,' says the man. 'How does it happen that in all these "
    "years no one but me has ever begged for admittance?'",
    "static")

add("extreme close — the doorkeeper's mouth at the dying man's ear, roaring, the old man's "
    "failing eyes, harsh shadow",
    "The doorkeeper sees that the man has reached his end, and to reach his failing ears, roars:",
    "motion-driftright", hint="a slow push toward the dying man's ear",
    sfx=[("low rising ominous swell", 0.2, 3, -8)])

add("the colossal gate flooded with warm yellow light, the words of revelation hanging over it, "
    "the tiny man dying beneath, wide composition",
    "'No one else could ever be admitted here, since this gate was made only for you.'",
    "kinetic", ost="ONLY FOR YOU", hint="the revelation over the glowing gate")

add("the immense iron gate slamming shut, the column of yellow light snuffed to black, a final "
    "thin line of glow vanishing across the wide frame",
    "'I am now going to shut it.'", "slice", transition="cut",
    hint="horizontal slam, the light is extinguished",
    sfx=[("enormous heavy iron door slam and bolt lock, echoing", 0.1, 3, -3)])

interlude("total black across the wide frame, then a single small warm point of yellow light at "
          "the center, fading slowly to nothing, fine grain",
          "static", "a single point of light, then dark", secs=6.0, transition="fadeblack")

add("a black frame with the author's name in small ash-grey letters, a faint warm-yellow "
    "underline, silence",
    "Franz Kafka.", "kinetic", transition="fade", ost="FRANZ KAFKA",
    hint="closing card", secs=5.0)

# ---------------- assemble + tile timing ----------------
def dur_for(sc):
    if sc["secs"]:
        # silent interludes (no narration) are the dominant pauses — halve them for
        # tighter pacing. Narrated cards keep their planned secs (narrate overrides
        # with the real spoken length anyway).
        return float(sc["secs"]) / 2 if not sc["narration"] else float(sc["secs"])
    w = len(sc["narration"].split())
    if sc["animator"] == "kinetic" and w <= 5:
        return 5.0
    return max(6.0, min(15.0, round(w / 2.3, 1)))

scenes = []
t = 0.0
for i, sc in enumerate(S, start=1):
    d = dur_for(sc)
    scene = {
        "id": i,
        "start_s": round(t, 2),
        "end_s": round(t + d, 2),
        "visual_prompt": f"{STYLE}, {sc['visual']}",
        "narration": sc["narration"],
        "on_screen_text": sc["ost"],
        "motion_hint": sc["hint"],
        "image_role": "hero" if sc["animator"] in ("parallax", "slice") else "",
        "animator": sc["animator"],
        "transition": sc["transition"],
        "transition_dur": 0.5,
    }
    if sc["atmosphere"]:
        scene["atmosphere"] = sc["atmosphere"]
    if sc["tone"]:
        scene["tone"] = sc["tone"]
    if sc["sfx"]:
        scene["sfx"] = [
            {"prompt": p, "at": a, "dur": dd, "gain_db": g} for (p, a, dd, g) in sc["sfx"]
        ]
    scenes.append(scene)
    t += d

doc = {
    "topic": "Before the Law — a parable by Franz Kafka",
    "duration_s": int(round(t)),
    "aspect": "16:9",
    "voice": True,
    "voice_name": "narrator",
    "tone": "serious",
    "style": "Kafkaesque noir, B/W ink-woodcut with one warm-yellow accent; grave, literary",
    "character": STYLE,
    "music": MUSIC,
    "scenes": scenes,
    "title": "Before the Law — Franz Kafka | A Noir Reading",
    "description": (
        "Franz Kafka's parable 'Before the Law', read in full over hand-built black-and-"
        "white noir illustration. On the door that stands open, the keeper who will not let "
        "you pass, and the gate that was made only for you.\n\nText: public domain (Muir "
        "translation)."
    ),
    "hashtags": ["#kafka", "#beforethelaw", "#literature", "#noir", "#shortfilm", "#audiobook"],
}

n_narr = sum(1 for s in scenes if s["narration"])
n_intr = len(scenes) - n_narr
out = Path("runs/before-the-law/01_script.json")
out.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
print(f"wrote {out}  scenes={len(scenes)} ({n_narr} narrated + {n_intr} interludes)  "
      f"planned={t:.1f}s (~{t/60:.1f} min)")
