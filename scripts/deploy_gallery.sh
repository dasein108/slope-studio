#!/usr/bin/env bash
#
# Deploy the effects gallery to GitHub Pages (https://dasein108.github.io/slope-studio/).
#
# What it does:
#   1. Rebuilds index.html from examples/out/ (build_index.py).
#   2. Stages the gallery into .ghp-build/, recompressing any clip larger than
#      $THRESH_BYTES (default 4 MB) to a web-friendly 720p H.264 so the gh-pages
#      branch stays light. Small clips are copied as-is.
#   3. Publishes index.html + examples/out/*.mp4 to the orphan `gh-pages` branch
#      via a throwaway git worktree, so your working tree / `main` is never touched.
#
# Prereqs: the demo clips must already be rendered into examples/out/. Regenerate
# them first if effects changed:
#     python examples/make_examples.py            # all effects
#     python examples/make_examples.py <effect> --frames   # one effect
#
# Usage:
#     scripts/deploy_gallery.sh
#     make gallery          # same thing
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# pick a python: project venv → python3 → python
if [ -x "$ROOT/.venv/bin/python" ]; then PYTHON="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null; then PYTHON="$(command -v python3)"
else PYTHON="$(command -v python)"; fi

BRANCH="gh-pages"
OUT="examples/out"
BUILD="$ROOT/.ghp-build"
WT="$ROOT/.ghp-wt"
THRESH_BYTES="${THRESH_BYTES:-4194304}"   # 4 MB
PAGES_URL="https://dasein108.github.io/slope-studio/"

filesize() { stat -f%z "$1" 2>/dev/null || stat -c%s "$1"; }

[ -d "$OUT" ] || { echo "ERROR: $OUT not found — run examples/make_examples.py first." >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg not on PATH." >&2; exit 1; }

echo "==> 1/3  Rebuilding gallery index.html"
if [ "${RENDER:-0}" = "1" ]; then
    echo "    RENDER=1 — re-rendering ALL effects (slow)…"
    "$PYTHON" examples/make_examples.py
fi
"$PYTHON" examples/build_index.py   # scans $OUT, regenerates index.html

echo "==> 2/3  Staging into $BUILD (recompressing clips > $((THRESH_BYTES/1024/1024)) MB)"
rm -rf "$BUILD"
mkdir -p "$BUILD/$OUT"
cp index.html "$BUILD/index.html"
shrunk=0
for f in "$OUT"/*.mp4; do
    b="$(basename "$f")"
    if [ "$(filesize "$f")" -gt "$THRESH_BYTES" ]; then
        ffmpeg -y -loglevel error -i "$f" -vf "scale=-2:1280" \
            -c:v libx264 -crf 30 -preset slow -pix_fmt yuv420p \
            -movflags +faststart -an "$BUILD/$OUT/$b"
        shrunk=$((shrunk+1))
    else
        cp "$f" "$BUILD/$OUT/$b"
    fi
done
echo "    staged $(ls "$BUILD/$OUT"/*.mp4 | wc -l | tr -d ' ') clips ($shrunk recompressed), $(du -sh "$BUILD" | cut -f1) total"

echo "==> 3/3  Publishing to '$BRANCH' via temp worktree"
git worktree remove --force "$WT" 2>/dev/null || true
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    git fetch -q origin "$BRANCH"
    git worktree add -q "$WT" "$BRANCH"
else
    git worktree add -q --detach "$WT"
    git -C "$WT" checkout -q --orphan "$BRANCH"
fi
git -C "$WT" rm -rqf index.html "$OUT" >/dev/null 2>&1 || true   # only gallery files; keep articles/ images
cp "$BUILD/index.html" "$WT/index.html"
mkdir -p "$WT/$OUT"
cp "$BUILD/$OUT"/*.mp4 "$WT/$OUT/"
touch "$WT/.nojekyll"          # serve raw files; skip Jekyll processing
git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then
    echo "    no changes to deploy."
else
    git -C "$WT" commit -q -m "Deploy effects gallery ($(date +%F))"
    git -C "$WT" push -q origin "$BRANCH"
    echo "    pushed."
fi
git worktree remove --force "$WT"
rm -rf "$BUILD"

echo "==> Done. Live (after Pages rebuild, ~1 min): $PAGES_URL"
