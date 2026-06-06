# builds/ — per-video build scripts

One-off generators that author a single video's `runs/<id>/01_script.json` **by hand** (scene
list, prompts, animators, sfx, timing). They are the authored back-catalogue — **not** part of the
reusable `studio` package.

## The rule

**Every `build_*.py` lives here, never at repo root.** Name them `build_<slug>.py`. If one shows
up at root, it's a mistake — move it into `builds/`.

## Running

Run from the **repo root** so the relative `runs/<id>/` output path resolves:

```bash
python builds/build_<slug>.py        # writes runs/<id>/01_script.json
studio run --run-id <id> ...         # or: studio clips/visuals/... to produce it
```

A build script only writes the scenario JSON; the `studio` pipeline (film-maker skill) renders it.

## Current back-catalogue

Literary / brand one-offs — e.g. `build_before_the_law.py`, `build_first_sorrow.py`,
`build_imperial_message.py`, `build_dream_of_ridiculous_man.py`, `build_rubaiyat.py`,
`build_brand_starship_pilot.py`. (List drifts as videos are added — `ls builds/` for the truth.)

Authoring guidance + the scenario schema: [`../docs/30-animation/scenario-schema.md`](../docs/30-animation/scenario-schema.md)
and the **film-maker** skill.
