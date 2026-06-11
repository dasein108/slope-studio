"""Build a single-page HTML gallery (index.html at the repo ROOT) with an inline video
player for every rendered effect demo in examples/out/.

    python examples/make_examples.py        # render the clips first
    python examples/build_index.py          # → ./index.html

Open index.html in a browser to see every effect/variant playing in one place. Re-run
after adding an effect (and its demo variant in make_examples.py). The clips live in
examples/out/ (gitignored media); index.html references them relatively.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from examples.make_examples import EFFECTS  # noqa: E402
from examples.make_music_examples import MUSIC_DEMOS  # noqa: E402

OUT = ROOT / "examples" / "out"
INDEX = ROOT / "index.html"

# one-line blurb per effect (shown under the heading).
DESCRIPTIONS = {
    "puppet": "Free cutout animation — the figure moves itself: idle bob/sway, hop, "
              "shake/nod head, and per-limb raise/wave (rembg cutout, $0).",
    "parallax": "TRUE parallax — static sharp subject, the REAL background drifts behind it. "
                "The subject is inpainted out of the bg, so there's no ghost twin.",
    "blurred-parallax": "Soft-backdrop parallax — static subject over a blurred panning "
                        "background (2-plane sky/ground, or single). For busy backgrounds.",
    "atmosphere": "Weather/particle overlay post-pass that composites onto ANY clip "
                  "(rain · snow · embers · fog · blood · petals · leaves · wind).",
    "fx": "Free 'look' post-passes (Scene.fx, applied on any clip): grain · vignette · "
          "chroma aberration · glitch · sunrise grade · god-rays · flash (impact colour "
          "punch — white/yellow/red/black — that fades back to normal).",
    "transitions": "Scene-to-scene xfade transitions (50+ available) — two stills joined "
                   "with each named transition.",
    "slice": "Cut / reveal — the still splits into halves that slide together "
             "(diagonal, or horizontal with a red flash).",
    "motion": "zoompan presets — gentle drift / zoom on a still (the only motion-* the "
              "operator keeps; lateral drift over twitchy zoom).",
    "kinetic": "Typographic headline animated over the still (Pillow text overlay).",
    "static": "A deliberately held still — better than a twitchy zoom for a calm beat.",
    "manim": "Vector animation (sun rises, shapes, morphs, kinetic type) — for "
             "educational/diagram scenes.",
    "talkinghead": "2D lip-sync — static face, the mouth moves with the narration "
                   "(Rhubarb visemes → mouth-sprite swap). Mouth position + size via mouth_xy "
                   "(or LLM auto-detected). Best on a clear closed-mouth portrait.",
}

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.5 -apple-system, system-ui, sans-serif;
       background: #0d0f14; color: #e6e8ee; padding: 28px clamp(16px, 4vw, 56px); }
h1 { margin: 0 0 4px; font-size: 26px; }
.sub { color: #8b93a7; margin: 0 0 28px; }
.toc { margin: 0 0 28px; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px; }
.toc a { color: #cdd3e0; text-decoration: none; background: #1a1e28; padding: 5px 11px;
         border-radius: 999px; font-size: 13px; border: 1px solid #232838; }
.toc a:hover { background: #232a3a; }
section { margin: 0 0 40px; scroll-margin-top: 16px; }
h2 { margin: 0 0 4px; font-size: 19px; }
h2 code { background: #1a1e28; padding: 2px 8px; border-radius: 6px; font-size: 16px; color: #7fd1ff; }
.desc { color: #9aa3b8; margin: 0 0 16px; max-width: 70ch; }
.grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
figure { margin: 0; background: #141823; border: 1px solid #222838; border-radius: 12px;
         overflow: hidden; }
video { display: block; width: 100%; aspect-ratio: 9/16; background: #000; object-fit: contain; }
audio { display: block; width: 100%; }
figcaption { padding: 9px 12px; font-size: 13px; color: #cdd3e0; font-weight: 600; }
.music-card { padding: 14px; display: grid; gap: 10px; }
.music-card figcaption { padding: 0; }
.music-card p { margin: 0; color: #9aa3b8; font-size: 13px; min-height: 3.1em; }
.missing { padding: 20px; color: #ff8a8a; font-size: 13px; }
"""


def main() -> None:
    if not OUT.exists():
        sys.exit("no examples/out/ — run `python examples/make_examples.py` first")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards_total = 0
    toc, sections = [], []
    for effect, variants in EFFECTS.items():
        items = []
        for v in variants:
            label = v[0]
            mp4 = OUT / f"{effect}_{label}.mp4"
            if not mp4.exists():
                continue
            rel = mp4.relative_to(ROOT).as_posix()
            items.append(
                f'      <figure><video src="{rel}" controls loop muted autoplay playsinline></video>'
                f'<figcaption>{label}</figcaption></figure>')
            cards_total += 1
        if not items:
            continue
        toc.append(f'<a href="#{effect}">{effect}</a>')
        desc = DESCRIPTIONS.get(effect, "")
        sections.append(
            f'  <section id="{effect}">\n'
            f'    <h2><code>{effect}</code></h2>\n'
            f'    <p class="desc">{desc}</p>\n'
            f'    <div class="grid">\n' + "\n".join(items) + "\n    </div>\n  </section>")

    music_items = []
    for label, _prompt, desc in MUSIC_DEMOS:
        mp3 = OUT / f"music_synth_{label}.mp3"
        if not mp3.exists():
            continue
        rel = mp3.relative_to(ROOT).as_posix()
        music_items.append(
            f'      <figure class="music-card"><figcaption>{label}</figcaption>'
            f'<p>{desc}</p><audio src="{rel}" controls preload="metadata"></audio></figure>')
        cards_total += 1
    if music_items:
        toc.append('<a href="#music">music</a>')
        sections.append(
            '  <section id="music">\n'
            '    <h2><code>music</code></h2>\n'
            '    <p class="desc">Free 5-second music-bed samples from the built-in '
            '<code>synth</code> provider. These are generated locally with ffmpeg and cost $0. '
            'The other free music paths are <code>local</code> commercial-safe files in '
            '<code>assets/audio/music/</code> and <code>freesound</code> CC0 search when a '
            '<code>FREESOUND_API_KEY</code> is configured.</p>\n'
            '    <div class="grid">\n' + "\n".join(music_items) + "\n    </div>\n  </section>")

    html = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Slope Studio — Effects Gallery</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        "<h1>Slope Studio — Effects Gallery</h1>\n"
        f'<p class="sub">{cards_total} demos · generated {stamp} · '
        "rebuild: <code>python examples/make_examples.py &amp;&amp; python examples/build_index.py</code></p>\n"
        f'<nav><ul class="toc">{"".join(toc)}</ul></nav>\n'
        + "\n".join(sections)
        + "\n</body>\n</html>\n")
    INDEX.write_text(html)
    print(f"wrote {INDEX}  ({cards_total} demos across {len(sections)} sections)")


if __name__ == "__main__":
    main()
