#!/usr/bin/env bash
# Daily marketing autopilot driver (headless, unattended).
# Drains the loop: each run keeps ticking the due action (measure|learn|ideate|
# produce) until the engine reports `idle`. The engine's own cadence gates
# (min_hours_between_produces, daily_produce_cap) cap how much it publishes per
# day — this wrapper just stops looping once nothing is due.
#
# Wire to cron once a day, e.g.:  0 9 * * *  /Users/dasein/dev/slope-studio/scripts/daily_autopilot.sh
set -euo pipefail

# cron runs with a minimal PATH — ensure homebrew (ffmpeg/ffprobe) is reachable.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

CHANNEL="${1:-pilot-channel}"
ROOT="/Users/dasein/dev/slope-studio"
STUDIO="$ROOT/.venv/bin/studio"
LOG="$ROOT/runs/_marketing/$CHANNEL/autopilot.log"
MAX_TICKS=8   # safety guard: at most this many actions per daily run

cd "$ROOT"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') autopilot run (channel=$CHANNEL) =====" >>"$LOG"

for i in $(seq 1 "$MAX_TICKS"); do
  NEXT="$("$STUDIO" marketing tick --channel "$CHANNEL" --json 2>>"$LOG" \
          | sed -n 's/.*"next": *"\([a-z]*\)".*/\1/p' | head -1)"
  echo "[$i] next=$NEXT" >>"$LOG"
  if [ "$NEXT" = "idle" ] || [ -z "$NEXT" ]; then
    break
  fi
  # --produce gates spend/publish; balanced tier sizes to the channel budget.
  "$STUDIO" marketing autopilot --channel "$CHANNEL" --produce --tier balanced >>"$LOG" 2>&1 || {
    echo "[$i] autopilot tick failed (continuing next day)" >>"$LOG"
    break
  }
done

echo "----- $(date '+%Y-%m-%d %H:%M:%S') run complete -----" >>"$LOG"
