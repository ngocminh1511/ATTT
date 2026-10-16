"""Nhánh A (mục 4.2): tiền xử lý CSV/Parquet CIC-DDoS2019.

Output (trong --out, mặc định data/):
  train_pool.parquet  ngày 12/01, dùng để chia cho các client (split_clients.py)
  test_day2.parquet   ngày 11/03, test toàn cục
  features.json       {"branch": "A", "features": [...]}

Ví dụ:
  python prepare/preprocess_csv.py --train-glob "data/raw/01-12/*.csv" --test-glob "data/raw/03-11/*.csv"
  # Bản Kaggle dhoogla/cicddos2019 (parquet):
  python prepare/preprocess_csv.py --train-glob "data/raw/cicddos2019/*-testing.parquet" --test-glob "data/raw/cicddos2019/*-training.parquet"
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paths  # noqa: E402
from fl_ddos.features import normalize_label, slog1p  # noqa: E402

# Cột định danh dễ gây "học vẹt" (sau khi chuẩn hóa tên cột)
DROP = {"flow_id", "source_ip", "destination_ip", "src_ip", "dst_ip", "timestamp",
        "unnamed_0", "simillarhttp", "source_port", "src_port", "class"}


def snake(c: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", c.strip().lower()).strip("_")


def iter_frames(path: str, chunksize: int):
    if path.endswith(".parquet"):
        yield pd.read_parquet(path)
    else:
        yield from pd.read_csv(path, chunksize=chunksize, low_memory=False, encoding_errors="ignore")


def load_day(pattern: str, cap: int, keep_all_benign: bool, seed: int, chunksize: int) -> pd.DataFrame:
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"Không tìm thấy file nào khớp: {pattern}")
    rng = np.random.default_rng(seed)
    parts = {}
    for f in files:
        for df in iter_frames(f, chunksize):
            df.columns = [snake(c) for c in df.columns]
            df = df.drop(columns=[c for c in df.columns if c in DROP])
            df["label"] = df["label"].astype(str).map(normalize_label)
            for lab, g in df.groupby("label"):
                if not (lab == "BENIGN" and keep_all_benign) and len(g) > cap:
                    g = g.sample(cap, random_state=int(rng.integers(1 << 31)))
                parts.setdefault(lab, []).append(g)
        print(f"  đọc {Path(f).name}")
    out = []
    for lab, gs in parts.items():
        g = pd.concat(gs)
        if not (lab == "BENIGN" and keep_all_benign) and len(g) > cap:
            g = g.sample(cap, random_state=seed)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def clean(df: pd.DataFrame, cols=None) -> pd.DataFrame:
    num = df.drop(columns=["label"]).apply(pd.to_numeric, errors="coerce") if cols is None \
        else df[cols].apply(pd.to_numeric, errors="coerce")
    num = num.replace([np.inf, -np.inf], np.nan)
    df = pd.concat([num, df["label"]], axis=1).dropna().drop_duplicates()
    return df


def select_features(df: pd.DataFrame, n: int, corr_thr: float, seed: int) -> list:
    cols = [c for c in df.columns if c != "label" and df[c].nunique() > 1]  # bỏ cột hằng
    x = df[cols].astype(np.float64)
    corr = x.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
    drop = [c for c in upper.columns if (upper[c] > corr_thr).any()]  # Pearson > 0,95
    cols = [c for c in cols if c not in drop]
    sample = df.sample(min(len(df), 100_000), random_state=seed)
    rf = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=seed, class_weight="balanced")
    rf.fit(sample[cols], (sample["label"] != "BENIGN").astype(int))
    rank = pd.Series(rf.feature_importances_, index=cols).sort_values(ascending=False)
    print("  Top đặc trưng (RF importance):\n" + rank.head(n).round(4).to_string())
    print(f"  Bỏ {len(drop)} cột tương quan > {corr_thr}: {drop}")
    return list(rank.head(n).index)


def finalize(df: pd.DataFrame, feats: list) -> pd.DataFrame:
    out = pd.DataFrame(slog1p(df[feats].values), columns=feats, index=df.index).astype(np.float32)
    out["label"] = df["label"].values
    out["binary"] = (df["label"] != "BENIGN").astype(np.int64).values
    return out.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-glob", default=str(paths.DATA / "raw" / "01-12" / "*.csv"))
    ap.add_argument("--test-glob", default=str(paths.DATA / "raw" / "03-11" / "*.csv"))
    ap.add_argument("--max-per-attack", type=int, default=30_000)
    ap.add_argument("--max-test-per-label", type=int, default=30_000)
    ap.add_argument("--n-features", type=int, default=25)
    ap.add_argument("--corr", type=float, default=0.95)
    ap.add_argument("--chunksize", type=int, default=500_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(paths.DATA))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    print("[1/4] Đọc ngày train (12/01)")
    train = clean(load_day(a.train_glob, a.max_per_attack, True, a.seed, a.chunksize))
    print("[2/4] Đọc ngày test (11/03)")
    test = load_day(a.test_glob, a.max_test_per_label, False, a.seed, a.chunksize)
    print("[3/4] Chọn đặc trưng")
    feats = select_features(train, a.n_features, a.corr, a.seed)
    test = clean(test, [c for c in feats if c in test.columns])
    missing = [c for c in feats if c not in test.columns]
    if missing:
        sys.exit(f"Tập test thiếu cột: {missing}")

    print("[4/4] Ghi kết quả")
    finalize(train, feats).to_parquet(out / "train_pool.parquet", index=False)
    finalize(test, feats).to_parquet(out / "test_day2.parquet", index=False)
    json.dump({"branch": "A", "features": feats}, open(out / "features.json", "w", encoding="utf-8"), indent=2)
    print("  train:", train["label"].value_counts().to_dict())
    print("  test :", test["label"].value_counts().to_dict())


if __name__ == "__main__":
    main()
