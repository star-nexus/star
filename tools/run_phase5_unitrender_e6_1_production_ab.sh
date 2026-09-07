#!/usr/bin/env bash
set -Eeuo pipefail

# Phase 5 UnitRender E6-1 — bounded derived world-geometry ownership.
# Control is exact retained production. Treatment is the frozen production-source
# candidate. Counterbalanced order: A50 -> B50 -> B100 -> A100.

BASE_SHA="${BASE_SHA:-17ced8d2ba1725b4d0c1a5458e6c61c06c1e206a}"
CANDIDATE_SHA="${CANDIDATE_SHA:-e7ba18b31870577110b591104ef8fa7b4713e43c}"
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
RESULTS_ROOT="${RESULTS_ROOT:-results/phase5-unitrender-e6-1}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
SCENARIO_FILE="$REPO_ROOT/rotk_env/maps/${SCENARIO}.json"
ANALYZER="$REPO_ROOT/tools/phase5_unitrender_e6_1_analyze.py"

for file in "$SCENARIO_FILE" "$ANALYZER"; do
    [[ -f "$file" ]] || { echo "ERROR: required file missing: $file"; exit 2; }
done

scenario_sha="$(shasum -a 256 "$SCENARIO_FILE" | awk '{print $1}')"
[[ "$scenario_sha" == "$EXPECTED_SCENARIO_SHA256" ]] || {
    echo "ERROR: scenario SHA256 mismatch"
    echo " expected: $EXPECTED_SCENARIO_SHA256"
    echo " actual:   $scenario_sha"
    exit 2
}
for sha in "$BASE_SHA" "$CANDIDATE_SHA"; do
    git cat-file -e "${sha}^{commit}" 2>/dev/null || {
        echo "ERROR: missing commit $sha; run git fetch origin"
        exit 2
    }
done
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "ERROR: tracked working tree is dirty"
    git status --short
    exit 2
fi

runtime_diff="$(git diff --name-only "$BASE_SHA" "$CANDIDATE_SHA" -- rotk_env | grep -v '^rotk_env/tests/' || true)"
[[ "$runtime_diff" == "rotk_env/utils/unit_spatial_index.py" ]] || {
    echo "ERROR: E6-1 runtime source guard failed"
    echo "expected only: rotk_env/utils/unit_spatial_index.py"
    echo "actual:"
    printf '%s\n' "$runtime_diff"
    exit 2
}

RUN_DIR="$REPO_ROOT/$RESULTS_ROOT/$SCENARIO/$RUN_ID"
mkdir -p "$RUN_DIR/control" "$RUN_DIR/treatment" "$RUN_DIR/fixtures"
cp "$SCENARIO_FILE" "$RUN_DIR/fixtures/${SCENARIO}.json"
(
    cd "$RUN_DIR"
    shasum -a 256 "fixtures/${SCENARIO}.json" > "fixtures/SHA256SUMS"
)
cat > "$RUN_DIR/source-guards.json" <<EOF
{
  "control_sha": "$BASE_SHA",
  "treatment_sha": "$CANDIDATE_SHA",
  "runtime_diff": ["rotk_env/utils/unit_spatial_index.py"],
  "pass": true
}
EOF

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/star-phase5-unitrender-e6-1.XXXXXX")"
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
    ENV_PID=""
    CURRENT_SOCKET=""
    return "$cleanup_failed"
}
cleanup_all() {
    cleanup_env || true
    git -C "$REPO_ROOT" worktree remove --force "$A_WT" >/dev/null 2>&1 || true
    git -C "$REPO_ROOT" worktree remove --force "$B_WT" >/dev/null 2>&1 || true
    rm -rf "$TMP_ROOT"
}
trap cleanup_all EXIT INT TERM

echo "Creating detached E6-1 production A/B worktrees..."
git worktree add --detach "$A_WT" "$BASE_SHA" >/dev/null
git worktree add --detach "$B_WT" "$CANDIDATE_SHA" >/dev/null
mkdir -p "$A_WT/rotk_env/maps" "$B_WT/rotk_env/maps"
cp "$SCENARIO_FILE" "$A_WT/rotk_env/maps/${SCENARIO}.json"
cp "$SCENARIO_FILE" "$B_WT/rotk_env/maps/${SCENARIO}.json"

{
    echo "experiment=Phase 5 UnitRender E6-1 bounded derived world-geometry ownership"
    echo "run_id=$RUN_ID"
    echo "created_at_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "caller_branch=$(git branch --show-current)"
    echo "caller_sha=$(git rev-parse HEAD)"
    echo "control_runtime_sha=$BASE_SHA"
    echo "treatment_runtime_sha=$CANDIDATE_SHA"
    echo "runtime_diff=rotk_env/utils/unit_spatial_index.py"
    echo "treatment=board_bounded_lazy_per_hex_derived_geometry_reuse"
    echo "fresh_unit_spatial_record_each_refresh=true"
    echo "record_layout_unchanged=true"
    echo "cull_algorithm_unchanged=true"
    echo "spatial_containers_unchanged=true"
    echo "cache_owner=UnitSpatialIndex"
    echo "cache_bound=current_board_hexes"
    echo "unbounded_world_cache=disabled"
    echo "execution_order=A50,B50,B100,A100"
    echo "scenario=$SCENARIO"
    echo "scenario_sha256=$scenario_sha"
    echo "seed=$SEED"
    echo "phase_seed=$PHASE_SEED"
    echo "route_steps=$ROUTE_STEPS"
    echo "duration_seconds=$DURATION"
    echo "warmup_seconds=$WARMUP"
    echo "sample_after_seconds=$SAMPLE_AFTER"
    echo "steady_reuse_window=true"
    echo "gc_policy=realtime_defer"
    echo "fog=ON (driver guard)"
    echo "minimap_dynamic_units=OFF"
    echo "render=uncapped"
    echo "hub=offline"
    echo "min_cull_saving_ms_50=0.10"
    echo "min_cull_saving_ms_100=0.20"
    echo "rate_tolerance_pct=2.0"
    echo "max_animation_avg_regression_pct=2.0"
    echo "max_controlled_avg_regression_pct=2.0"
    echo "canonical_30hz_p99_ms=33.33"
    echo "keep_gate_separate_from_frontier_gate=true"
    echo "env_cleanup=exec-launcher+captured-process-tree"
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
    uv run --frozen pytest rotk_env/tests/test_unit_spatial_index_geometry_reuse.py -q
) > "$RUN_DIR/treatment-contract-test.log" 2>&1
CONTRACT_RC=$?
set -e
echo "$CONTRACT_RC" > "$RUN_DIR/treatment-contract-test-exit-code.txt"
cat "$RUN_DIR/treatment-contract-test.log"
[[ "$CONTRACT_RC" -eq 0 ]] || { echo "ERROR: candidate geometry contract failed"; exit "$CONTRACT_RC"; }

CONTROL_TESTS=(
  rotk_env/tests/test_unit_spatial_index_movement.py
  rotk_env/tests/test_window_indexed_state.py
  rotk_env/tests/test_window_unit_render_spatial_cull.py
  rotk_env/tests/test_window_render_fast_paths.py
  rotk_env/tests/test_vision_incremental_index.py
)
TREATMENT_TESTS=(
  rotk_env/tests/test_unit_spatial_index_geometry_reuse.py
  "${CONTROL_TESTS[@]}"
)

set +e
(cd "$A_WT" && uv run --frozen pytest "${CONTROL_TESTS[@]}" -q) > "$RUN_DIR/control-targeted-regressions.log" 2>&1
CONTROL_RC=$?
set -e
echo "$CONTROL_RC" > "$RUN_DIR/control-targeted-regressions-exit-code.txt"
cat "$RUN_DIR/control-targeted-regressions.log"
[[ "$CONTROL_RC" -eq 0 ]] || { echo "ERROR: control targeted regressions failed"; exit "$CONTROL_RC"; }

set +e
(cd "$B_WT" && uv run --frozen pytest "${TREATMENT_TESTS[@]}" -q) > "$RUN_DIR/treatment-targeted-regressions.log" 2>&1
TREATMENT_RC=$?
set -e
echo "$TREATMENT_RC" > "$RUN_DIR/treatment-targeted-regressions-exit-code.txt"
cat "$RUN_DIR/treatment-targeted-regressions.log"
[[ "$TREATMENT_RC" -eq 0 ]] || { echo "ERROR: treatment targeted regressions failed"; exit "$TREATMENT_RC"; }

sleep "$COOLDOWN"

run_point() {
    local variant="$1"
    local wt="$2"
    local density="$3"
    local density_label="$4"
    local point_dir
    local cleanup_rc
    point_dir="$RUN_DIR/$variant/${density_label}pct-moving"

    [[ -z "${ENV_PID:-}" ]] || { echo "ERROR: previous ENV still registered"; exit 2; }
    mkdir -p "$point_dir"
    CURRENT_SOCKET="/tmp/star-phase5-unitrender-e6-1-${$}-${variant}-${density_label}.sock"
    rm -f "$CURRENT_SOCKET"

    echo
    echo "============================================================"
    echo "UnitRender E6-1 production A/B: ${variant} ${density_label}% moving"
    echo "worktree SHA: $(git -C "$wt" rev-parse HEAD)"
    echo "============================================================"
    {
        echo "variant=$variant"
        echo "density=$density"
        echo "git_sha=$(git -C "$wt" rev-parse HEAD)"
        echo "scenario=$SCENARIO"
        echo "socket=$CURRENT_SOCKET"
    } > "$point_dir/config.txt"

    (
        cd "$wt"
        exec env STAR_SCALE_MINIMAP_UNITS=off \
          uv run --frozen python -m rotk_env.main \
            --skip-start --mode real_time --scenario "$SCENARIO" \
            --players human_vs_two_ai --no-hub --seed "$SEED" --uncapped \
            --scale-harness-socket "$CURRENT_SOCKET"
    ) > "$point_dir/env.log" 2>&1 &
    ENV_PID=$!
    echo "ENV launcher PID: $ENV_PID" | tee "$point_dir/env-pid.txt"

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
    cleanup_env
    cleanup_rc=$?
    set -e
    echo "$DRIVER_RC" > "$point_dir/driver-exit-code.txt"
    echo "$cleanup_rc" > "$point_dir/env-cleanup-exit-code.txt"
    [[ "$cleanup_rc" -eq 0 ]] || { echo "ERROR: cleanup failed"; exit 2; }
    [[ "$DRIVER_RC" -eq 0 ]] || { echo "ERROR: driver failed rc=$DRIVER_RC"; exit "$DRIVER_RC"; }
    [[ -f "$point_dir/point.json" && -f "$point_dir/profile.json" ]] || { echo "ERROR: missing artifacts"; exit 2; }
    sleep "$COOLDOWN"
}

run_point control "$A_WT" 0.5 50
run_point treatment "$B_WT" 0.5 50
run_point treatment "$B_WT" 1.0 100
run_point control "$A_WT" 1.0 100

python3 "$ANALYZER" "$RUN_DIR"

ZIP_PATH="$RUN_DIR.zip"
python3 - "$RUN_DIR" "$ZIP_PATH" <<'PY'
from pathlib import Path
import sys
import zipfile

src = Path(sys.argv[1]).resolve()
dst = Path(sys.argv[2]).resolve()
with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(src.rglob("*")):
        if path.is_file():
            archive.write(path, Path(src.name) / path.relative_to(src))
print(dst)
PY
shasum -a 256 "$ZIP_PATH" | tee "$RUN_DIR/zip-sha256.txt"

echo
echo "============================================================"
echo "UnitRender E6-1 production A/B completed"
echo "Results: $RUN_DIR"
echo "Raw staging ZIP: $ZIP_PATH"
echo "============================================================"
