#!/usr/bin/env bash
#
# Make each article a true single copy-paste into dev.to.
#
# dev.to can't see local files, so relative image paths (./images/x.png) break on paste.
# This script:
#   1. Publishes every articles/<slug>/images/ folder to the gh-pages site (additively —
#      it leaves the effects gallery and other articles intact).
#   2. Generates articles/<slug>/devto.md: a copy of article.md with every ./images/ path
#      (cover_image + inline) rewritten to its absolute GitHub Pages URL.
#
# After running: open articles/<slug>/devto.md, select-all, paste into dev.to's markdown
# editor (frontmatter included), set `published: true`, post. Images + cover just work.
#
# Usage:
#   scripts/build_devto.sh
#   make devto
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="gh-pages"
WT="$ROOT/.ghp-wt"
ARTROOT="$ROOT/articles"
BASE="https://dasein108.github.io/slope-studio/articles"

echo "==> 1/2  Generating devto.md (absolute image URLs)"
for d in "$ARTROOT"/*/; do
    slug="$(basename "$d")"
    src="${d}article.md"
    [ -f "$src" ] || continue
    sed "s@\./images/@$BASE/$slug/images/@g" "$src" > "${d}devto.md"
    echo "    ${slug}/devto.md"
done

echo "==> 2/2  Publishing article images to '$BRANCH' (additive)"
git worktree remove --force "$WT" 2>/dev/null || true
git fetch -q origin "$BRANCH" 2>/dev/null || true
git worktree add -q "$WT" "$BRANCH"
for d in "$ARTROOT"/*/; do
    slug="$(basename "$d")"
    [ -d "${d}images" ] || continue
    mkdir -p "$WT/articles/$slug/images"
    cp "${d}images/"*.png "$WT/articles/$slug/images/" 2>/dev/null || true
    cp "${d}images/"*.jpg "$WT/articles/$slug/images/" 2>/dev/null || true
done
git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then
    echo "    no image changes."
else
    git -C "$WT" commit -q -m "Publish article images for dev.to ($(date +%F))"
    git -C "$WT" push -q origin "$BRANCH"
    echo "    pushed."
fi
git worktree remove --force "$WT"

echo "==> Done. Images at $BASE/<slug>/images/  (Pages rebuild ~1 min)"
echo "    Paste articles/<slug>/devto.md into dev.to — frontmatter + images render as-is."
