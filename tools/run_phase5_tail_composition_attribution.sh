#!/usr/bin/env bash
set -Eeuo pipefail

BASE_SHA="${BASE_SHA:-e7ba18b31870577110b591104ef8fa7b4713e43c}"
SCENARIO="${SCENARIO:-chibi-144k-scale-10000}"
EXPECTED_SCENARIO_SHA256="${EXPECTED_SCENARIO_SHA256:-e5bacb41c499fdfb9e91a917a1427515f2be1dae5ca4961692e921c05b816d25}"
SEED="${SEED:-42}"
PHASE_SEED="${PHASE_SEED:-42}"
ROUTE_STEPS="${ROUTE_STEPS:-12}"
DURATION="${DURATION:-20}"
WARMUP="${WARMUP:-5}"
SAMPLE_AFTER="${SAMPLE_AFTER:-19}"
READY_TIMEOUT="${READY_TIMEOUT:-120}"
COMMAND_TIMEOUT="${COMMAND_TIMEOUT:-120}"
COOLDOWN="${COOLDOWN:-5}"
RESULTS_ROOT="${RESULTS_ROOT:-results/phase5-tail-composition}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
SCENARIO_FILE="$REPO_ROOT/rotk_env/maps/${SCENARIO}.json"
SNAPSHOT="$REPO_ROOT/tools/phase5_tail_composition_snapshot.py"
CONTRACT="$REPO_ROOT/tools/test_phase5_tail_composition_snapshot.py"
ANALYZER="$REPO_ROOT/tools/phase5_tail_composition_analyze.py"
for file in "$SCENARIO_FILE" "$SNAPSHOT" "$CONTRACT" "$ANALYZER"; do
  [[ -f "$file" ]] || { echo "ERROR: missing $file"; exit 2; }
done

scenario_sha="$(shasum -a 256 "$SCENARIO_FILE" | awk '{print $1}')"
[[ "$scenario_sha" == "$EXPECTED_SCENARIO_SHA256" ]] || { echo "ERROR: scenario SHA mismatch"; exit 2; }
git cat-file -e "${BASE_SHA}^{commit}" 2>/dev/null || { echo "ERROR: missing $BASE_SHA; git fetch origin"; exit 2; }
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "ERROR: tracked working tree dirty"; git status --short; exit 2
fi

RUN_DIR="$REPO_ROOT/$RESULTS_ROOT/$SCENARIO/$RUN_ID"
mkdir -p "$RUN_DIR/fixtures"
cp "$SCENARIO_FILE" "$RUN_DIR/fixtures/${SCENARIO}.json"
(
  cd "$RUN_DIR" && shasum -a 256 "fixtures/${SCENARIO}.json" > fixtures/SHA256SUMS
)

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/star-phase5-tail-e7.XXXXXX")"
WT="$TMP_ROOT/runtime"
ENV_PID=""
CURRENT_SOCKET=""

pid_alive() { kill -0 "$1" 2>/dev/null; }
collect_descendants() {
  local parent="$1" child
  while IFS= read -r child; do
    [[ -n "$child" ]] || continue
    collect_descendants "$child"
    printf '%s\n' "$child"
  done < <(pgrep -P "$parent" 2>/dev/null || true)
}
cleanup_env() {
  local root="${ENV_PID:-}" descendants="" pid any_alive cleanup_failed=0
  if [[ -n "$root" ]] && pid_alive "$root"; then
    descendants="$(collect_descendants "$root")"
    for pid in $descendants; do kill -TERM "$pid" 2>/dev/null || true; done
    kill -TERM "$root" 2>/dev/null || true
    for _ in {1..30}; do
      any_alive=0
      for pid in $descendants $root; do
        if [[ -n "$pid" ]] && pid_alive "$pid"; then any_alive=1; break; fi
      done
      [[ "$any_alive" -eq 0 ]] && break
      sleep 0.2
    done
    for pid in $descendants $root; do
      if [[ -n "$pid" ]] && pid_alive "$pid"; then kill -KILL "$pid" 2>/dev/null || true; fi
    done
    wait "$root" 2>/dev/null || true
    for pid in $descendants $root; do
      if [[ -n "$pid" ]] && pid_alive "$pid"; then cleanup_failed=1; fi
    done
  fi
  [[ -n "${CURRENT_SOCKET:-}" ]] && rm -f "$CURRENT_SOCKET"
  ENV_PID=""; CURRENT_SOCKET=""
  return "$cleanup_failed"
}
cleanup_all() {
  cleanup_env || true
  git -C "$REPO_ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || true
  rm -rf "$TMP_ROOT"
}
trap cleanup_all EXIT INT TERM

echo "Creating exact retained-production E7 worktree..."
git worktree add --detach "$WT" "$BASE_SHA" >/dev/null
mkdir -p "$WT/rotk_env/maps" "$WT/tools"
cp "$SCENARIO_FILE" "$WT/rotk_env/maps/${SCENARIO}.json"
cp "$SNAPSHOT" "$WT/tools/phase5_tail_composition_snapshot.py"
cp "$CONTRACT" "$WT/tools/test_phase5_tail_composition_snapshot.py"

profiler_blob="$(git -C "$WT" hash-object performance_profiler.py)"
python3 - "$RUN_DIR/source-guards.json" "$BASE_SHA" "$profiler_blob" "$scenario_sha" <<'PY'
import json, sys
path, sha, profiler_blob, scenario_sha = sys.argv[1:]
expected_profiler = "005ebafce310b6015c0971b54dc060b82bdf6351"
expected_scenario = "e5bacb41c499fdfb9e91a917a1427515f2be1dae5ca4961692e921c05b816d25"
payload = {
  "runtime_sha": sha,
  "expected_runtime_sha": "e7ba18b31870577110b591104ef8fa7b4713e43c",
  "performance_profiler_blob": profiler_blob,
  "expected_performance_profiler_blob": expected_profiler,
  "scenario_sha256": scenario_sha,
  "expected_scenario_sha256": expected_scenario,
}
payload["pass"] = (
  payload["runtime_sha"] == payload["expected_runtime_sha"]
  and profiler_blob == expected_profiler
  and scenario_sha == expected_scenario
)
open(path, "w", encoding="utf-8").write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
if not payload["pass"]:
  raise SystemExit(2)
PY

{
  echo "experiment=Phase 5 E7 100% moving P99 tail composition attribution"
  echo "run_id=$RUN_ID"
  echo "created_at_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "caller_branch=$(git branch --show-current)"
  echo "caller_sha=$(git rev-parse HEAD)"
  echo "runtime_sha=$BASE_SHA"
  echo "scenario=$SCENARIO"
  echo "scenario_sha256=$scenario_sha"
  echo "repeats=3"
  echo "density=1.0"
  echo "seed=$SEED"
  echo "phase_seed=$PHASE_SEED"
  echo "route_steps=$ROUTE_STEPS"
  echo "duration_seconds=$DURATION"
  echo "warmup_seconds=$WARMUP"
  echo "sample_after_seconds=$SAMPLE_AFTER"
  echo "profiler_window_seconds=10.0"
  echo "tail_set=controlled_work>=p95"
  echo "reference_set=p25-p75"
  echo "contribution_basis=section_self_time"
  echo "stable_top3_repeats_required=2"
  echo "actionable_median_tail_uplift_ms=0.15"
  echo "canonical_gate_ms=33.33"
  echo "frontier_update_authorized=false"
  uname -a | sed 's/^/uname=/'
  if command -v sw_vers >/dev/null 2>&1; then
    sw_vers -productName | sed 's/^/macos_product=/'
    sw_vers -productVersion | sed 's/^/macos_version=/'
    sw_vers -buildVersion | sed 's/^/macos_build=/'
  fi
} > "$RUN_DIR/manifest.txt"

(cd "$WT" && uv run --frozen python -c 'import pygame, performance_profiler, rotk_env.main' >/dev/null)
set +e
(cd "$WT" && uv run --frozen pytest tools/test_phase5_tail_composition_snapshot.py -q) > "$RUN_DIR/tail-contract-test.log" 2>&1
CONTRACT_RC=$?
set -e
cat "$RUN_DIR/tail-contract-test.log"
[[ "$CONTRACT_RC" -eq 0 ]] || { echo "ERROR: E7 tail contract failed"; exit "$CONTRACT_RC"; }

TARGETED_TESTS=(
  framework/tests/test_performance_profiler.py
  framework/tests/test_performance_measurement_contract.py
  rotk_env/tests/test_unit_spatial_index_geometry_reuse.py
)
set +e
(cd "$WT" && uv run --frozen pytest "${TARGETED_TESTS[@]}" -q) > "$RUN_DIR/targeted-regressions.log" 2>&1
REG_RC=$?
set -e
cat "$RUN_DIR/targeted-regressions.log"
[[ "$REG_RC" -eq 0 ]] || { echo "ERROR: targeted regressions failed"; exit "$REG_RC"; }
sleep "$COOLDOWN"

run_repeat() {
  local repeat="$1" point_dir="$RUN_DIR/repeat-${repeat}" cleanup_rc
  mkdir -p "$point_dir"
  CURRENT_SOCKET="/tmp/star-phase5-tail-e7-${$}-${repeat}.sock"
  rm -f "$CURRENT_SOCKET"
  echo
  echo "============================================================"
  echo "E7 tail attribution repeat-${repeat} — 100% moving"
  echo "============================================================"
  (
    cd "$WT"
    exec env STAR_SCALE_MINIMAP_UNITS=off \
      uv run --frozen python tools/phase5_tail_composition_snapshot.py \
        --skip-start --mode real_time --scenario "$SCENARIO" \
        --players human_vs_two_ai --no-hub --seed "$SEED" --uncapped \
        --scale-harness-socket "$CURRENT_SOCKET"
  ) > "$point_dir/env.log" 2>&1 &
  ENV_PID=$!

  set +e
  (
    cd "$WT"
    uv run --frozen python tools/scale_driver.py \
      --socket "$CURRENT_SOCKET" --command-timeout "$COMMAND_TIMEOUT" \
      density-point --density 1.0 --phase staggered \
      --seed "$SEED" --phase-seed "$PHASE_SEED" --route-steps "$ROUTE_STEPS" \
      --duration "$DURATION" --warmup "$WARMUP" --sample-after "$SAMPLE_AFTER" \
      --ready-timeout "$READY_TIMEOUT" --gc-policy realtime_defer \
      --profile "$point_dir/profile.json" --output "$point_dir/point.json"
  ) 2>&1 | tee "$point_dir/driver.log"
  DRIVER_RC="${PIPESTATUS[0]}"
  cleanup_env; cleanup_rc=$?; set -e
  echo "$DRIVER_RC" > "$point_dir/driver-exit-code.txt"
  echo "$cleanup_rc" > "$point_dir/env-cleanup-exit-code.txt"
  [[ "$cleanup_rc" -eq 0 ]] || { echo "ERROR: cleanup failed"; exit 2; }
  [[ "$DRIVER_RC" -eq 0 ]] || { echo "ERROR: repeat-${repeat} driver failed"; exit "$DRIVER_RC"; }
  python3 - "$point_dir/profile.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
t = p.get("tail_attribution")
if not isinstance(t, dict) or t.get("ok") is not True:
    raise SystemExit("missing valid tail_attribution")
if t.get("sample_count", 0) < 250:
    raise SystemExit(f"insufficient aligned tail samples: {t.get('sample_count')}")
PY
  sleep "$COOLDOWN"
}

run_repeat 1
run_repeat 2
run_repeat 3

python3 "$ANALYZER" "$RUN_DIR"

ZIP_PATH="$RUN_DIR.zip"
python3 - "$RUN_DIR" "$ZIP_PATH" <<'PY'
from pathlib import Path
import sys, zipfile
src = Path(sys.argv[1]).resolve(); dst = Path(sys.argv[2]).resolve()
with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(src.rglob("*")):
        if path.is_file(): zf.write(path, Path(src.name) / path.relative_to(src))
print(dst)
PY
shasum -a 256 "$ZIP_PATH" | tee "$RUN_DIR/zip-sha256.txt"

echo
echo "============================================================"
echo "Phase 5 E7 tail composition attribution completed"
echo "Results: $RUN_DIR"
echo "Raw staging ZIP: $ZIP_PATH"
echo "============================================================"
