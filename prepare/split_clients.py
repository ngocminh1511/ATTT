"""Mục 4.4: chia train_pool.parquet cho K client theo các kịch bản Non-IID.

  S1  IID           xáo trộn, chia đều
  S2a Dirichlet α=0,5 (theo nhãn multiclass)
  S2b Dirichlet α=0,1
  S3  theo loại tấn công (mỗi chi nhánh gặp kiểu DDoS khác nhau), mọi client đều có BENIGN
  S4  lệch số lượng (client lớn nhất 50%, bé nhất 5%)

Output: data/{S}/client_1..K.parquet và data/{S}/summary.csv
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paths  # noqa: E402

# Kịch bản S3 cho 5 client (theo tài liệu). Client 5: chỉ BENIGN + một ít UDP.
S3_GROUPS = [["SYN", "UDP", "UDP-Lag"], ["DNS", "LDAP", "NTP"], ["MSSQL", "NetBIOS", "SNMP"],
             ["SSDP", "TFTP", "WebDDoS"], []]
S3_LAST_UDP_FRAC = 0.1
S4_SIZES = [0.50, 0.20, 0.15, 0.10, 0.05]


def dirichlet_split(labels, n_clients=5, alpha=0.5, seed=42):
    rng = np.random.default_rng(seed)
    idx_per_client = [[] for _ in range(n_clients)]
    for c in np.unique(labels):
        idx = np.where(labels == c)[0]
        rng.shuffle(idx)
        p = rng.dirichlet([alpha] * n_clients)
        cuts = (np.cumsum(p) * len(idx)).astype(int)[:-1]
        for k, part in enumerate(np.split(idx, cuts)):
            idx_per_client[k].extend(part.tolist())
    return [np.array(i) for i in idx_per_client]


def iid_split(n, k, seed):
    idx = np.random.default_rng(seed).permutation(n)
    return np.array_split(idx, k)


def by_attack_split(labels, k, seed):
    rng = np.random.default_rng(seed)
    groups = S3_GROUPS if k == 5 else [[] for _ in range(k)]
    owner = {lab: i for i, g in enumerate(groups) for lab in g}
    attacks = sorted(set(labels) - {"BENIGN"})
    free = [a for a in attacks if a not in owner]
    for j, a in enumerate(free):  # loại không có trong bảng -> chia vòng tròn (bỏ client cuối khi k=5)
        owner[a] = j % (k - 1 if k == 5 else k)
    out = [[] for _ in range(k)]
    benign = rng.permutation(np.where(labels == "BENIGN")[0])
    for i, part in enumerate(np.array_split(benign, k)):
        out[i].extend(part.tolist())
    for a in attacks:
        idx = rng.permutation(np.where(labels == a)[0])
        if k == 5 and a == "UDP":
            cut = int(len(idx) * S3_LAST_UDP_FRAC)
            out[4].extend(idx[:cut].tolist()); idx = idx[cut:]
        out[owner[a]].extend(idx.tolist())
    return [np.array(i) for i in out]


def size_skew_split(n, k, seed):
    sizes = np.array(S4_SIZES if k == 5 else np.linspace(k, 1, k))
    sizes = sizes / sizes.sum()
    idx = np.random.default_rng(seed).permutation(n)
    cuts = (np.cumsum(sizes) * n).astype(int)[:-1]
    return np.split(idx, cuts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-clients", type=int, default=5)
    ap.add_argument("--scenarios", nargs="+", default=["S1", "S2a", "S2b", "S3", "S4"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", help="tên thư mục output thay cho tên kịch bản (vd. lab), chỉ dùng với 1 kịch bản")
    a = ap.parse_args()
    if a.tag and len(a.scenarios) != 1:
        sys.exit("--tag chỉ dùng với đúng một kịch bản")
    df = pd.read_parquet(paths.TRAIN_POOL)
    labels = df["label"].values
    k = a.n_clients
    for sc in a.scenarios:
        parts = {
            "S1": lambda: iid_split(len(df), k, a.seed),
            "S2a": lambda: dirichlet_split(labels, k, 0.5, a.seed),
            "S2b": lambda: dirichlet_split(labels, k, 0.1, a.seed),
            "S3": lambda: by_attack_split(labels, k, a.seed),
            "S4": lambda: size_skew_split(len(df), k, a.seed),
        }[sc]()
        d = paths.DATA / (a.tag or sc)
        d.mkdir(parents=True, exist_ok=True)
        summary = {}
        for i, idx in enumerate(parts):
            part = df.iloc[np.sort(idx)].reset_index(drop=True)
            part.to_parquet(d / f"client_{i + 1}.parquet", index=False)
            summary[f"client_{i + 1}"] = part["label"].value_counts()
        s = pd.DataFrame(summary).fillna(0).astype(int)
        s.loc["TOTAL"] = s.sum()
        s.to_csv(d / "summary.csv")
        print(f"[{sc}]\n{s.to_string()}\n")


if __name__ == "__main__":
    main()
