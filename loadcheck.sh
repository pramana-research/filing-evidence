#!/usr/bin/env bash
# Load check (PROTOCOL §2): serve each profile on the 4090, answer 24 evenly spaced questions in C1 (and C3 when
# the model has a reasoning mode), stop the server. Results: results/main/<profile>/C*-limit24/.
#
#   bash research/benchmarks/filing-evidence/loadcheck.sh qwen3.5-9b granite-4.2-8b ...
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../../.."
source .venv/bin/activate
LOGS="$HERE/logs"

LOCK="$HERE/results/.gpu.lock"                    # one vLLM server at a time (shared with run_all.sh)
mkdir -p "$HERE/results"
for p in "$@"; do
  exec 9>"$LOCK"; flock 9
  echo "=== $p $(date -Is)"
  python3 "$HERE/serve.py" "$p" > "$LOGS/serve-$p.log" 2>&1 &
  pid=$!
  ready=0
  for _ in $(seq 1 360); do                       # up to 30 minutes (first start compiles CUDA graphs)
    if grep -q "Application startup complete" "$LOGS/serve-$p.log"; then ready=1; break; fi
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    sleep 5
  done
  if [ "$ready" -ne 1 ]; then
    echo "SERVE FAILED $p"; grep -E "Error|error|Traceback" "$LOGS/serve-$p.log" | tail -5
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; flock -u 9; continue
  fi
  for s in C1 C3; do
    python3 "$HERE/runner.py" "$p" "$s" --limit 24 2>&1 | grep -E "^accuracy|n/a|Traceback|Error" | sed "s/^/  $s /"
  done
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  sleep 10                                        # let the GPU memory free before the next model
  flock -u 9
done
echo "=== done $(date -Is)"
