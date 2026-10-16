"""Baseline cận dưới (mục 6.7): mỗi client chỉ học dữ liệu của mình.

Mỗi client được test trên test_day2; ghi từng client và trung bình. Recall theo
loại tấn công của từng client dùng để vẽ heatmap (client × loại tấn công).
  python baselines/local_only.py --scenario S3 --epochs 60 --seed 0
"""
import argparse

import numpy as np
import pandas as pd

from common import append_row, fit_and_test, paths
from fl_ddos.task import device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="S3")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=0.001)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    dev = device()
    files = sorted((paths.DATA / a.scenario).glob("client_*.parquet"))
    all_m = []
    for i, f in enumerate(files):
        _, m, rec = fit_and_test(pd.read_parquet(f), a.epochs, a.lr, a.batch_size, dev, a.seed + i)
        print(f"client_{i + 1}: " + str({k: round(v, 4) for k, v in m.items()}))
        all_m.append(m)
        append_row(paths.RESULTS / "baselines.csv",
                   {"method": "Local-only", "scenario": a.scenario, "client": i + 1, "seed": a.seed, **m})
        append_row(paths.RESULTS / "per_attack.csv",
                   {"method": "Local-only", "scenario": a.scenario, "client": i + 1, "seed": a.seed, **rec})
    avg = {k: float(np.mean([m[k] for m in all_m])) for k in all_m[0]}
    print("Trung bình:", {k: round(v, 4) for k, v in avg.items()})
    append_row(paths.RESULTS / "baselines.csv",
               {"method": "Local-only", "scenario": a.scenario, "client": "mean", "seed": a.seed, **avg})


if __name__ == "__main__":
    main()
