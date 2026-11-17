#!/usr/bin/env bash
# Full benchmark run (PROTOCOL §6): for each profile, serve it, run C1 on all 1,000 questions, then C2 (reuses
# C1's first answers; asks only the retries), then C3 where the model has a reasoning mode; stop the server.
# Runs resume (runner.py skips answered questions), so re-running this script after an interruption continues.
# Takes the same GPU lock as loadcheck.sh, so the two never serve at once.
#
#   bash run_all.sh qwen3.5-9b granite-4.2-8b ...
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
source .venv/bin/activate
LOGS="$HERE/logs"
LOCK="$HERE/results/.gpu.lock"
mkdir -p "$HERE/results"

for p in "$@"; do
  exec 9>"$LOCK"; flock 9
  echo "=== $p start $(date -Is)"
  python3 "$HERE/serve.py" "$p" > "$LOGS/serve-$p.log" 2>&1 &
  pid=$!
  ready=0
  for _ in $(seq 1 360); do
    if grep -q "Application startup complete" "$LOGS/serve-$p.log"; then ready=1; break; fi
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    sleep 5
  done
  if [ "$ready" -ne 1 ]; then
    echo "SERVE FAILED $p"; grep -E "Error|Traceback" "$LOGS/serve-$p.log" | tail -3
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; flock -u 9; continue
  fi
  for s in C1 C2 C3; do
    echo "  $s start $(date -Is)"
    python3 "$HERE/runner.py" "$p" "$s" > "$LOGS/run-$p-$s.log" 2>&1
    grep -E "^accuracy|n/a|Traceback|Error" "$LOGS/run-$p-$s.log" | tail -2 | cut -c1-200 | sed "s/^/  $s /"
  done
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  sleep 10
  echo "=== $p done $(date -Is)"
  flock -u 9
done
echo "=== all done $(date -Is)"
