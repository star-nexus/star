#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
SCENARIO="${SCENARIO:-chibi-144k-scale-10000}"
RESULTS_ROOT="${RESULTS_ROOT:-results/phase5-tail-composition}"
export RUN_ID SCENARIO RESULTS_ROOT

bash tools/run_phase5_tail_composition_attribution.sh

RUN_DIR="$REPO_ROOT/$RESULTS_ROOT/$SCENARIO/$RUN_ID"
LEGACY_ZIP="$RUN_DIR.zip"
RAW_ZIP="${RUN_DIR}-raw.zip"
COMPACT_ZIP="${RUN_DIR}-compact.zip"
[[ -d "$RUN_DIR" && -f "$LEGACY_ZIP" ]] || { echo "ERROR: missing E7 artifacts"; exit 2; }

mv "$LEGACY_ZIP" "$RAW_ZIP"
python3 tools/build_compact_evidence_package.py \
  "$RUN_DIR" --raw-zip "$RAW_ZIP" --output "$COMPACT_ZIP"

RAW_SHA="$(shasum -a 256 "$RAW_ZIP" | awk '{print $1}')"
COMPACT_SHA="$(shasum -a 256 "$COMPACT_ZIP" | awk '{print $1}')"
cat > "$RUN_DIR/artifact-index.json" <<EOF
{
  "schema": "star-two-tier-artifacts-v1",
  "compact": {"path": "$COMPACT_ZIP", "sha256": "$COMPACT_SHA", "role": "default decision-grade review artifact"},
  "raw": {"path": "$RAW_ZIP", "sha256": "$RAW_SHA", "role": "authoritative forensic audit substrate"},
  "rule": "Raw artifact is never replaced by compact evidence."
}
EOF

echo
echo "================================================================================================"
echo "STAR E7 two-tier evidence packages"
echo "================================================================================================"
echo "Compact Evidence Package: $COMPACT_ZIP"
echo "Compact SHA256:          $COMPACT_SHA"
echo "Raw Forensic Package:    $RAW_ZIP"
echo "Raw SHA256:              $RAW_SHA"
echo "Artifact index:           $RUN_DIR/artifact-index.json"
echo "================================================================================================"
