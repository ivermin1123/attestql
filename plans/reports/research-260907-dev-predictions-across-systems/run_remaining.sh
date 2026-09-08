#!/usr/bin/env bash
# Run the remaining measurement stages with a ten-minute heartbeat beside them.
set -euo pipefail
here="$(cd "$(dirname "$BASH_SOURCE[0]}")" && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK}"
export MEASURE_WORK
export ATTESTQL="$MEASURE_WORK/venv/bin/attestql"
cd "$MEASURE_WORK"

phase_file="$MEASURE_WORK/out/run-remaining.phase"
mkdir -p "$(dirname "$phase_file")"
echo "starting remaining measurement stages" > "$phase_file"

heartbeat() {
  while :; do
    sleep 600
    orca orchestration send \
      --from term_6fc9e66f-77c4-4efc-96da-33e676a8b2a5 \
      --dispatch-capability dcap_KWFhqbrZUauXK6TpyBk7OxTbqP2Fidok7bcFarck6ww \
      --type heartbeat --subject "alive" \
      --task-id task_4c1921eaaf8b --dispatch-id ctx_856974940f53 \
      --phase "$(cat "$phase_file")" > /dev/null
  done
}
heartbeat &
heartbeat_loop="$!"
trap 'kill "$heartbeat_loop" 2>/dev/null || true' EXIT

echo "serial timeout reruns" > "$phase_file"
bash "$here/rerun_timeouts.sh"
echo "BIRD official scoring" > "$phase_file"
bash "$here/run_official.sh"
echo "merging prediction measurements" > "$phase_file"
python3 "$here/measure_predictions.py"
echo "computing moved credits" > "$phase_file"
python3 "$here/credits_moved.py"
echo "extracting hand sample" > "$phase_file"
python3 "$here/sample_rows.py"
echo "done" > "$phase_file"
echo REMAINING_DONE
