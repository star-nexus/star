#!/usr/bin/env bash
set -Eeuo pipefail

# STAR Phase 5.1 — Core Runtime Attribution
#
# Attribution only:
#   - 10K resident / 50% moving
#   - 10K resident / 100% moving
#
# Uses the existing Phase-3/4 scale harness and profiler, but launches the ENV
# through tools/phase5_core_attribution.py so measurement-only probes are
# installed around Animation / Movement / Vision internals.
#
# Production runtime files are not modified by the attribution launcher.

SCENARIO="${SCENARIO:-chibi-144k-scale-10000}"
SEED="${SEED:-42}"
PHASE_SEED="${PHASE_SEED:-42}"
ROUTE_STEPS="${ROUTE_STEPS:-12}"

DURATION="${DURATION:-20}"
WARMUP="${WARMUP:-5}"
SAMPLE_AFTER="${SAMPLE_AFTER:-7}"
READY_TIMEOUT="${READY_TIMEOUT:-120}"
COMMAND_TIMEOUT="${COMMAND_TIMEOUT:-120}"

ATTR_SAMPLE_EVERY="${ATTR_SAMPLE_EVERY:-16}"
RESULTS_ROOT="${RESULTS_ROOT:-results/phase5-10k-attribution}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

SCENARIO_FILE="rotk_env/maps/${SCENARIO}.json"
if [[ ! -f "$SCENARIO_FILE" ]]; then
    echo "ERROR: scenario not found: $SCENARIO_FILE"
    exit 2
fi

RUN_DIR="${RESULTS_ROOT}/${SCENARIO}/${RUN_ID}"
mkdir -p "$RUN_DIR"

GIT_SHA="$(git rev-parse HEAD)"
GIT_BRANCH="$(git branch --show-current)"

{
    echo "experiment=Phase 5.1 — 10K Core Runtime Attribution"
    echo "run_id=$RUN_ID"
    echo "created_at_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "git_branch=$GIT_BRANCH"
    echo "git_sha=$GIT_SHA"
    echo "scenario=$SCENARIO"
    echo "scenario_file=$SCENARIO_FILE"
    echo "scenario_sha256=$(shasum -a 256 "$SCENARIO_FILE" | awk '{print $1}')"
    echo "seed=$SEED"
    echo "phase_seed=$PHASE_SEED"
    echo "route_steps=$ROUTE_STEPS"
    echo "motion_phase=staggered"
    echo "gc_policy=realtime_defer"
    echo "duration_seconds=$DURATION"
    echo "warmup_seconds=$WARMUP"
    echo "sample_after_seconds=$SAMPLE_AFTER"
    echo "attribution_sample_every=$ATTR_SAMPLE_EVERY"
    echo "fog=ON (driver guard)"
    echo "minimap_dynamic_units=OFF"
    echo "render=uncapped"
    echo "hub=offline"
    echo "mock_ai=off"
} > "$RUN_DIR/manifest.txt"

git status --short > "$RUN_DIR/git-status.txt"
git diff --stat > "$RUN_DIR/git-diff-stat.txt"

ENV_PID=""
CURRENT_SOCKET=""

cleanup_env() {
    if [[ -n "${ENV_PID:-}" ]] && kill -0 "$ENV_PID" 2>/dev/null; then
        kill -TERM "$ENV_PID" 2>/dev/null || true
        for _ in {1..25}; do
            if ! kill -0 "$ENV_PID" 2>/dev/null; then
                break
            fi
            sleep 0.2
        done
        if kill -0 "$ENV_PID" 2>/dev/null; then
            kill -KILL "$ENV_PID" 2>/dev/null || true
        fi
        wait "$ENV_PID" 2>/dev/null || true
    fi
    if [[ -n "${CURRENT_SOCKET:-}" ]]; then
        rm -f "$CURRENT_SOCKET"
    fi
    ENV_PID=""
    CURRENT_SOCKET=""
}

trap cleanup_env EXIT INT TERM

run_point() {
    local density="$1"
    local label="$2"
    local point_dir="${RUN_DIR}/${label}"

    mkdir -p "$point_dir"
    CURRENT_SOCKET="/tmp/star-phase51-${$}-${label}.sock"
    rm -f "$CURRENT_SOCKET"

    echo
    echo "============================================================"
    echo "Phase 5.1 attribution: $label"
    echo "execution density: $density"
    echo "============================================================"

    {
        echo "density=$density"
        echo "label=$label"
        echo "git_sha=$GIT_SHA"
        echo "scenario=$SCENARIO"
        echo "socket=$CURRENT_SOCKET"
        echo "attribution_sample_every=$ATTR_SAMPLE_EVERY"
    } > "$point_dir/config.txt"

    STAR_SCALE_MINIMAP_UNITS=off \
    STAR_PHASE5_ATTR_SAMPLE_EVERY="$ATTR_SAMPLE_EVERY" \
    uv run python tools/phase5_core_attribution.py \
        --skip-start \
        --mode real_time \
        --scenario "$SCENARIO" \
        --players human_vs_two_ai \
        --no-hub \
        --seed "$SEED" \
        --uncapped \
        --scale-harness-socket "$CURRENT_SOCKET" \
        > "$point_dir/env.log" 2>&1 &

    ENV_PID=$!
    echo "STAR ENV PID: $ENV_PID"

    set +e
    uv run python tools/scale_driver.py \
        --socket "$CURRENT_SOCKET" \
        --command-timeout "$COMMAND_TIMEOUT" \
        density-point \
        --density "$density" \
        --phase staggered \
        --seed "$SEED" \
        --phase-seed "$PHASE_SEED" \
        --route-steps "$ROUTE_STEPS" \
        --duration "$DURATION" \
        --warmup "$WARMUP" \
        --sample-after "$SAMPLE_AFTER" \
        --ready-timeout "$READY_TIMEOUT" \
        --gc-policy realtime_defer \
        --profile "$point_dir/profile.json" \
        --output "$point_dir/point.json" \
        2>&1 | tee "$point_dir/driver.log"

    DRIVER_RC="${PIPESTATUS[0]}"
    set -e

    echo "$DRIVER_RC" > "$point_dir/driver-exit-code.txt"
    cleanup_env

    if [[ ! -f "$point_dir/profile.json" ]]; then
        echo "WARNING: profile.json missing for $label; inspect env.log / driver.log"
        return
    fi

    uv run python - "$point_dir/profile.json" "$point_dir/attribution-summary.json" <<'PY'
import json
import sys
from pathlib import Path

profile_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
profile = json.loads(profile_path.read_text())

sections = profile.get("sections", {})
metrics = profile.get("frame_metrics", {})

section_names = [
    "AnimationSystem",
    "animation_movement_update",
    "animation_movement_query",
    "animation_movement_loop",
    "animation_attack_update",
    "animation_projectile_update",
    "animation_effect_update",
    "animation_damage_update",
    "VisionSystem",
    "vision_prepare",
    "vision_audit_scan",
    "vision_dirty_snapshot",
    "vision_dirty_batch",
    "vision_fog_delta_publish",
    "vision_metrics_publish",
]

metric_prefixes = (
    "phase5_attr_",
    "vision_",
    "effect_position_index_changes",
    "scale_",
    "fog_enabled",
)

summary = {
    "metadata": profile.get("metadata", {}),
    "controlled_work_frame_ms": profile.get("controlled_work_frame_ms"),
    "sections": {
        name: sections[name]
        for name in section_names
        if name in sections
    },
    "frame_metrics": {
        name: value
        for name, value in metrics.items()
        if name.startswith(metric_prefixes)
    },
}

output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
PY
}

run_point 0.5 "50pct-moving"
run_point 1.0 "100pct-moving"

echo
echo "============================================================"
echo "Phase 5.1 attribution completed"
echo "Results: $RUN_DIR"
echo "============================================================"
