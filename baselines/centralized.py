"""Baseline cận trên (mục 6.7): gộp dữ liệu của mọi client, train cùng DDoSNet.

Số epoch mặc định = 30 vòng × 2 epoch = 60 để so sánh công bằng với FL.
  python baselines/centralized.py --scenario S1 --epochs 60 --seed 0
"""
import argparse

import pandas as pd
import torch

from common import append_row, fit_and_test, paths
from fl_ddos.task import device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="S1")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=0.001)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    dev = device()
    files = sorted((paths.DATA / a.scenario).glob("client_*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    print(f"Centralized: {len(df)} mẫu từ {len(files)} client, {a.epochs} epoch trên {dev}")
    model, m, rec = fit_and_test(df, a.epochs, a.lr, a.batch_size, dev, a.seed)
    print({k: round(v, 4) for k, v in m.items()})
    append_row(paths.RESULTS / "baselines.csv",
               {"method": "Centralized", "scenario": a.scenario, "client": "all", "seed": a.seed, **m})
    append_row(paths.RESULTS / "per_attack.csv",
               {"method": "Centralized", "scenario": a.scenario, "client": "all", "seed": a.seed, **rec})
    torch.save(model.state_dict(), paths.RESULTS / f"centralized_{a.scenario}_seed{a.seed}.pt")


if __name__ == "__main__":
    main()
