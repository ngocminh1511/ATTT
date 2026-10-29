#!/usr/bin/env bash
# Ma trận thí nghiệm E1–E5 (mục 6.6 + 8.2), mỗi cấu hình 3 seed. Chạy từ thư mục gốc dự án (Linux/WSL).
#   ROUNDS=3 SEEDS="0" EPOCHS=2 ./scripts/run_all.sh     # chạy thử nhanh
set -euo pipefail
ROUNDS=${ROUNDS:-30}; SEEDS=${SEEDS:-"0 1 2"}; EPOCHS=${EPOCHS:-60}
mkdir -p results
export CLIENTS=5 DATA_DIR=data RESULTS_DIR=results
for seed in $SEEDS; do
  for sc in S1 S2a S2b S3 S4; do
    for mu in 0.0 0.01 0.1; do
      echo "=== FL scenario=$sc mu=$mu seed=$seed ==="
      ./scripts/fl_run.sh "num-server-rounds=$ROUNDS scenario='$sc' proximal-mu=$mu seed=$seed arch='mlp' local-epochs=2 batch-size=256 dropout=0.2"
    done
  done
  python baselines/centralized.py --scenario S1 --epochs "$EPOCHS" --seed "$seed" --arch mlp --batch-size 256 --dropout 0.2
  for sc in S1 S3; do python baselines/local_only.py --scenario "$sc" --epochs "$EPOCHS" --seed "$seed" --arch mlp --batch-size 256 --dropout 0.2; done
done
# E7: ./scripts/fl_run.sh "scenario='S1' poison-clients='0' strategy='trimmed'"
python analysis/plots.py
