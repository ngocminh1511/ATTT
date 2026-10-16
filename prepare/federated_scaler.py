"""Mục 4.5: chuẩn hóa liên kết (vòng 0).

Mỗi client chỉ gửi ba thống kê cho mỗi đặc trưng: n_k, Σx, Σx². Server tính
    mu = Σ_k Σx / Σ_k n_k ,  sigma² = Σ_k Σx² / Σ_k n_k − mu²
rồi gửi lại scaler.json. Không bên nào thấy dữ liệu thô của client khác.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paths  # noqa: E402
from fl_ddos.features import load_meta  # noqa: E402


def client_stats(df: pd.DataFrame, feats: list) -> dict:
    """Chạy TẠI client: chỉ trả về thống kê tổng."""
    x = df[feats].values.astype(np.float64)
    return {"n": len(x), "sum": x.sum(0), "sumsq": (x ** 2).sum(0)}


def aggregate(stats: list) -> dict:
    """Chạy TẠI server."""
    n = sum(s["n"] for s in stats)
    mu = sum(s["sum"] for s in stats) / n
    var = np.maximum(sum(s["sumsq"] for s in stats) / n - mu ** 2, 0.0)
    return {"mean": mu.tolist(), "std": np.sqrt(var).tolist(), "n": int(n)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="S1")
    a = ap.parse_args()
    feats = load_meta()["features"]
    files = sorted((paths.DATA / a.scenario).glob("client_*.parquet"))
    if not files:
        sys.exit(f"Chưa có {paths.DATA / a.scenario}/client_*.parquet - chạy split_clients.py trước")
    stats = [client_stats(pd.read_parquet(f), feats) for f in files]
    for f, s in zip(files, stats):
        print(f"  {f.name}: gửi n={s['n']}, Σx, Σx² ({len(feats)} đặc trưng)")
    scaler = aggregate(stats)
    scaler["features"] = feats
    json.dump(scaler, open(paths.SCALER_JSON, "w", encoding="utf-8"), indent=2)
    print(f"Đã ghi {paths.SCALER_JSON} (n tổng = {scaler['n']})")


if __name__ == "__main__":
    main()
