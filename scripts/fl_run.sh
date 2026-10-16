#!/usr/bin/env bash
# Bọc `flwr run` (Linux/WSL), tương đương scripts/fl_run.ps1.
#   ./scripts/fl_run.sh "num-server-rounds=3 scenario='S3' proximal-mu=0.1"   [CLIENTS=5]
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CLIENTS=${CLIENTS:-5}; ACTORS=${ACTORS:-3}; DATA_DIR=${DATA_DIR:-data}; RESULTS_DIR=${RESULTS_DIR:-results}   # số ClientApp song song (RAM)
export PATH="$ROOT/.venv/bin:$PATH" FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION=1
cd "$ROOT"
flwr run . --stream --federation-config "num-supernodes=$CLIENTS client-resources-num-cpus=2 init-args-num-cpus=$((2 * ACTORS))" \
  --run-config "data-dir='$ROOT/$DATA_DIR' results-dir='$ROOT/$RESULTS_DIR' num-clients=$CLIENTS ${1:-}"
