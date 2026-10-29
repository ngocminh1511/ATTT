"""Baseline cận trên (mục 6.7): gộp dữ liệu của mọi client, train cùng mô hình.

Số epoch nên bằng số vòng × epoch cục bộ của FL để so sánh công bằng (paper: 30 × 5 = 150).
  python baselines/centralized.py --scenario paper --epochs 150 --seed 0          # FL_DDOS_DATA=data_paper
  python baselines/centralized.py --scenario S1 --arch mlp --epochs 60 --batch-size 256   # pipeline cũ
"""
import argparse

import pandas as pd
import torch

from common import add_args, append_row, fit_and_test, method_name, paths
from fl_ddos.task import device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="paper")
    add_args(ap, epochs=150)
    a = ap.parse_args()
    dev = device()
    files = sorted((paths.DATA / a.scenario).glob("client_*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    print(f"Centralized: {len(df)} mẫu từ {len(files)} client, {a.arch}, {a.epochs} epoch trên {dev}")
    model, m, rec, pc = fit_and_test(df, a, dev, a.seed)
    print({k: round(v, 4) for k, v in m.items()})
    key = {"method": method_name("Centralized", a.arch), "scenario": a.scenario, "client": "all", "seed": a.seed}
    append_row(paths.RESULTS / "baselines.csv", {**key, **m})
    append_row(paths.RESULTS / "per_attack.csv", {**key, **rec})
    if pc:
        append_row(paths.RESULTS / "per_class.csv", {**key, **pc})
    torch.save({"arch": a.arch, "dropout": a.dropout, "state_dict": model.state_dict()},
               paths.RESULTS / f"centralized_{a.scenario}_{a.arch}_seed{a.seed}.pt")


if __name__ == "__main__":
    main()
