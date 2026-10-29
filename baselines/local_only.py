"""Baseline cận dưới (mục 6.7): mỗi client chỉ học dữ liệu của mình.

Mỗi client được test trên test_day2; ghi từng client và trung bình. Recall theo
loại tấn công của từng client dùng để vẽ heatmap (client × loại tấn công).
  python baselines/local_only.py --scenario paper --epochs 150 --seed 0
  python baselines/local_only.py --scenario S3 --arch mlp --epochs 60 --batch-size 256
"""
import argparse

import numpy as np
import pandas as pd

from common import add_args, append_row, fit_and_test, method_name, paths
from fl_ddos.task import device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="paper")
    add_args(ap, epochs=150)
    a = ap.parse_args()
    dev = device()
    name = method_name("Local-only", a.arch)
    files = sorted((paths.DATA / a.scenario).glob("client_*.parquet"))
    all_m = []
    for i, f in enumerate(files):
        _, m, rec, pc = fit_and_test(pd.read_parquet(f), a, dev, a.seed + i)
        print(f"client_{i + 1}: " + str({k: round(v, 4) for k, v in m.items()}))
        all_m.append(m)
        key = {"method": name, "scenario": a.scenario, "client": i + 1, "seed": a.seed}
        append_row(paths.RESULTS / "baselines.csv", {**key, **m})
        append_row(paths.RESULTS / "per_attack.csv", {**key, **rec})
        if pc:
            append_row(paths.RESULTS / "per_class.csv", {**key, **pc})
    avg = {k: float(np.mean([m[k] for m in all_m])) for k in all_m[0]}
    print("Trung bình:", {k: round(v, 4) for k, v in avg.items()})
    append_row(paths.RESULTS / "baselines.csv",
               {"method": name, "scenario": a.scenario, "client": "mean", "seed": a.seed, **avg})


if __name__ == "__main__":
    main()
