#!/usr/bin/env bash
set -Eeuo pipefail

# Phase 5 UnitRender E6-2 — slotted-record composition attribution.
# Both control and treatment run exact retained E6-1 production. Treatment
# installs only the slotted UnitSpatialRecord representation before world build.
# Counterbalanced order: A50 -> B50 -> B100 -> A100.

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
RESULTS_ROOT="${RESULTS_ROOT:-results/phase5-unitrender-e6-2}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
SCENARIO_FILE="$REPO_ROOT/rotk_env/maps/${SCENARIO}.json"
PROBE="$REPO_ROOT/tools/phase5_unitrender_e6_2_slotted_composition.py"
CONTRACT_TEST="$REPO_ROOT/tools/test_phase5_unitrender_e6_2_slotted_composition.py"
ANALYZER="$REPO_ROOT/tools/phase5_unitrender_e6_2_analyze.py"

for file in "$SCENARIO_FILE" "$PROBE" "$CONTRACT_TEST" "$ANALYZER"; do
    [[ -f "$file" ]] || { echo "ERROR: required file missing: $file"; exit 2; }
done

scenario_sha="$(shasum -a 256 "$SCENARIO_FILE" | awk '{print $1}')"
[[ "$scenario_sha" == "$EXPECTED_SCENARIO_SHA256" ]] || {
    echo "ERROR: scenario SHA256 mismatch"
    echo " expected: $EXPECTED_SCENARIO_SHA256"
    echo " actual:   $scenario_sha"
    exit 2
}
git cat-file -e "${BASE_SHA}^{commit}" 2>/dev/null || {
    echo "ERROR: missing retained E6-1 base commit $BASE_SHA; run git fetch origin"
    exit 2
}
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "ERROR: tracked working tree is dirty"
    git status --short
    exit 2
fi

RUN_DIR="$REPO_ROOT/$RESULTS_ROOT/$SCENARIO/$RUN_ID"
mkdir -p "$RUN_DIR/control" "$RUN_DIR/treatment" "$RUN_DIR/fixtures"
cp "$SCENARIO_FILE" "$RUN_DIR/fixtures/${SCENARIO}.json"
(
    cd "$RUN_DIR"
    shasum -a 256 "fixtures/${SCENARIO}.json" > "fixtures/SHA256SUMS"
)

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/star-phase5-unitrender-e6-2.XXXXXX")"
A_WT="$TMP_ROOT/control"
B_WT="$TMP_ROOT/treatment"
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
    git -C "$REPO_ROOT" worktree remove --force "$A_WT" >/dev/null 2>&1 || true
    git -C "$REPO_ROOT" worktree remove --force "$B_WT" >/dev/null 2>&1 || true
    rm -rf "$TMP_ROOT"
}
trap cleanup_all EXIT INT TERM

echo "Creating detached E6-2 control/treatment worktrees from retained E6-1 production..."
git worktree add --detach "$A_WT" "$BASE_SHA" >/dev/null
git worktree add --detach "$B_WT" "$BASE_SHA" >/dev/null
mkdir -p "$A_WT/rotk_env/maps" "$B_WT/rotk_env/maps" "$B_WT/tools"
cp "$SCENARIO_FILE" "$A_WT/rotk_env/maps/${SCENARIO}.json"
cp "$SCENARIO_FILE" "$B_WT/rotk_env/maps/${SCENARIO}.json"
cp "$PROBE" "$B_WT/tools/phase5_unitrender_e6_2_slotted_composition.py"
cp "$CONTRACT_TEST" "$B_WT/tools/test_phase5_unitrender_e6_2_slotted_composition.py"

{
    echo "experiment=Phase 5 UnitRender E6-2 slotted-record composition attribution"
    echo "run_id=$RUN_ID"
    echo "created_at_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "caller_branch=$(git branch --show-current)"
    echo "caller_sha=$(git rev-parse HEAD)"
    echo "retained_e6_1_base_sha=$BASE_SHA"
    echo "control_runtime_sha=$BASE_SHA"
    echo "treatment_runtime_sha=$BASE_SHA"
    echo "treatment=slotted_unit_spatial_record_monkeypatch"
    echo "e6_1_bounded_geometry_ownership_preserved=true"
    echo "fresh_unit_spatial_record_each_refresh=true"
    echo "record_fields_unchanged=true"
    echo "cull_algorithm_unchanged=true"
    echo "spatial_containers_unchanged=true"
    echo "execution_order=A50,B50,B100,A100"
    echo "scenario=$SCENARIO"
    echo "scenario_sha256=$scenario_sha"
    echo "seed=$SEED"
    echo "phase_seed=$PHASE_SEED"
    echo "route_steps=$ROUTE_STEPS"
    echo "duration_seconds=$DURATION"
    echo "warmup_seconds=$WARMUP"
    echo "sample_after_seconds=$SAMPLE_AFTER"
    echo "gc_policy=realtime_defer"
    echo "fog=ON (driver guard)"
    echo "minimap_dynamic_units=OFF"
    echo "render=uncapped"
    echo "hub=offline"
    echo "mock_ai=off"
    echo "prior_e5_1_cull_saving_ms_50=0.090"
    echo "prior_e5_1_cull_saving_ms_100=0.113"
    echo "min_cull_saving_ms_50=0.05"
    echo "min_cull_saving_ms_100=0.07"
    echo "rate_tolerance_pct=2.0"
    echo "max_unitrender_avg_regression_pct=1.0"
    echo "max_controlled_avg_regression_pct=1.0"
    echo "max_animation_avg_regression_pct=2.0"
    echo "positive_decision_is_not_production_keep=true"
    echo "canonical_30hz_gate_ms=33.33"
    uname -a | sed 's/^/uname=/'
    if command -v sw_vers >/dev/null 2>&1; then
        sw_vers -productName | sed 's/^/macos_product=/'
        sw_vers -productVersion | sed 's/^/macos_version=/'
        sw_vers -buildVersion | sed 's/^/macos_build=/'
    fi
} > "$RUN_DIR/manifest.txt"
git status --short > "$RUN_DIR/caller-git-status.txt"

for wt in "$A_WT" "$B_WT"; do
    (cd "$wt" && uv run --frozen python -c 'import pygame, rotk_env.main' >/dev/null)
done

set +e
(
    cd "$B_WT"
    uv run --frozen pytest tools/test_phase5_unitrender_e6_2_slotted_composition.py -q
) > "$RUN_DIR/treatment-contract-test.log" 2>&1
CONTRACT_RC=$?
set -e
echo "$CONTRACT_RC" > "$RUN_DIR/treatment-contract-test-exit-code.txt"
cat "$RUN_DIR/treatment-contract-test.log"
[[ "$CONTRACT_RC" -eq 0 ]] || { echo "ERROR: treatment contract test failed"; exit "$CONTRACT_RC"; }

TARGETED_TESTS=(
  rotk_env/tests/test_unit_spatial_index_geometry_reuse.py
  rotk_env/tests/test_unit_spatial_index_movement.py
  rotk_env/tests/test_window_indexed_state.py
  rotk_env/tests/test_window_unit_render_spatial_cull.py
  rotk_env/tests/test_window_render_fast_paths.py
  rotk_env/tests/test_vision_incremental_index.py
)

set +e
(
    cd "$A_WT"
    uv run --frozen pytest "${TARGETED_TESTS[@]}" -q
) > "$RUN_DIR/control-targeted-regressions.log" 2>&1
CONTROL_REGRESSION_RC=$?
set -e
echo "$CONTROL_REGRESSION_RC" > "$RUN_DIR/control-targeted-regressions-exit-code.txt"
cat "$RUN_DIR/control-targeted-regressions.log"
[[ "$CONTROL_REGRESSION_RC" -eq 0 ]] || { echo "ERROR: control targeted regressions failed"; exit "$CONTROL_REGRESSION_RC"; }

set +e
(
    cd "$B_WT"
    uv run --frozen python - "${TARGETED_TESTS[@]}" <<'PY'
import sys
import pytest
from tools.phase5_unitrender_e6_2_slotted_composition import (
    _install_slotted_record_patch,
    _verify_source_contract,
)
_verify_source_contract()
_install_slotted_record_patch()
raise SystemExit(pytest.main([*sys.argv[1:], "-q"]))
PY
) > "$RUN_DIR/treatment-targeted-regressions.log" 2>&1
TREATMENT_REGRESSION_RC=$?
set -e
echo "$TREATMENT_REGRESSION_RC" > "$RUN_DIR/treatment-targeted-regressions-exit-code.txt"
cat "$RUN_DIR/treatment-targeted-regressions.log"
[[ "$TREATMENT_REGRESSION_RC" -eq 0 ]] || { echo "ERROR: treatment targeted regressions failed"; exit "$TREATMENT_REGRESSION_RC"; }

sleep "$COOLDOWN"

run_point() {
    local variant="$1" wt="$2" density="$3" density_label="$4" launcher="$5"
    local point_dir="$RUN_DIR/$variant/${density_label}pct-moving" cleanup_rc
    [[ -z "${ENV_PID:-}" ]] || { echo "ERROR: previous ENV still registered"; exit 2; }
    mkdir -p "$point_dir"
    CURRENT_SOCKET="/tmp/star-phase5-unitrender-e6-2-${$}-${variant}-${density_label}.sock"
    rm -f "$CURRENT_SOCKET"

    echo
    echo "============================================================"
    echo "UnitRender E6-2: ${variant} ${density_label}% moving"
    echo "============================================================"
    {
        echo "variant=$variant"
        echo "density=$density"
        echo "git_sha=$(git -C "$wt" rev-parse HEAD)"
        echo "launcher=$launcher"
        echo "scenario=$SCENARIO"
        echo "socket=$CURRENT_SOCKET"
    } > "$point_dir/config.txt"

    (
        cd "$wt"
        if [[ "$launcher" == "treatment" ]]; then
            exec env STAR_SCALE_MINIMAP_UNITS=off \
              uv run --frozen python tools/phase5_unitrender_e6_2_slotted_composition.py \
                --skip-start --mode real_time --scenario "$SCENARIO" \
                --players human_vs_two_ai --no-hub --seed "$SEED" --uncapped \
                --scale-harness-socket "$CURRENT_SOCKET"
        else
            exec env STAR_SCALE_MINIMAP_UNITS=off \
              uv run --frozen python -m rotk_env.main \
                --skip-start --mode real_time --scenario "$SCENARIO" \
                --players human_vs_two_ai --no-hub --seed "$SEED" --uncapped \
                --scale-harness-socket "$CURRENT_SOCKET"
        fi
    ) > "$point_dir/env.log" 2>&1 &
    ENV_PID=$!

    set +e
    (
        cd "$wt"
        uv run --frozen python tools/scale_driver.py \
          --socket "$CURRENT_SOCKET" --command-timeout "$COMMAND_TIMEOUT" \
          density-point --density "$density" --phase staggered \
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
    [[ "$DRIVER_RC" -eq 0 ]] || { echo "ERROR: driver failed rc=$DRIVER_RC"; exit "$DRIVER_RC"; }
    [[ -f "$point_dir/point.json" && -f "$point_dir/profile.json" ]] || { echo "ERROR: missing artifacts"; exit 2; }
    sleep "$COOLDOWN"
}

run_point control "$A_WT" 0.5 50 control
run_point treatment "$B_WT" 0.5 50 treatment
run_point treatment "$B_WT" 1.0 100 treatment
run_point control "$A_WT" 1.0 100 control

python3 "$ANALYZER" "$RUN_DIR"

ZIP_PATH="$RUN_DIR.zip"
python3 - "$RUN_DIR" "$ZIP_PATH" <<'PY'
from pathlib import Path
import sys
import zipfile
src = Path(sys.argv[1]).resolve()
dst = Path(sys.argv[2]).resolve()
with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(src.rglob("*")):
        if path.is_file():
            zf.write(path, Path(src.name) / path.relative_to(src))
print(dst)
PY
shasum -a 256 "$ZIP_PATH" | tee "$RUN_DIR/zip-sha256.txt"

echo
echo "============================================================"
echo "UnitRender E6-2 composition attribution completed"
echo "Results: $RUN_DIR"
echo "Raw staging ZIP: $ZIP_PATH"
echo "============================================================"
