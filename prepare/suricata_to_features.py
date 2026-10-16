"""Nhánh B (mục 4.3): eve.json của Suricata -> đặc trưng + nhãn.

Bước trước đó (chạy trong WSL/Docker):
  suricata -c lab/sensor/suricata.yaml -r <file>.pcap -l out/ -k none

Gán nhãn bằng file CSV các khoảng tấn công (cùng định dạng attack_log.csv của lab):
  label,start,end,dest_ip,src_ip
  SYN,2019-01-12T13:29:00.000000+0000,2019-01-12T13:34:00.000000+0000,192.168.50.1,
  (dest_ip / src_ip để trống = khớp mọi IP; src_ip có thể là danh sách phân cách bằng dấu ;)
Flow nằm trong khoảng [start, end] và khớp IP -> nhãn đó, ngược lại BENIGN.

Ví dụ:
  python prepare/suricata_to_features.py \
      --train-eve out/day1/eve.json --train-labels day1_attacks.csv \
      --test-eve out/day2/eve.json --test-labels day2_attacks.csv
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paths  # noqa: E402
from fl_ddos.features import EVE_FEATURES, FlowFeaturizer, parse_ts, slog1p  # noqa: E402


def read_flows(eve_files):
    evs = []
    for f in eve_files:
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if '"event_type":"flow"' not in line.replace(" ", ""):
                    continue
                try:
                    evs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    evs.sort(key=lambda e: parse_ts(e["flow"]["end"]))  # thứ tự giống lúc realtime
    return evs


def load_intervals(path):
    if not path:
        return []
    df = pd.read_csv(path, dtype=str).fillna("")
    return [(r["label"], parse_ts(r["start"]), parse_ts(r["end"]),
             set(filter(None, r.get("dest_ip", "").split(";"))),
             set(filter(None, r.get("src_ip", "").split(";")))) for _, r in df.iterrows()]


def label_of(ev, intervals):
    t = parse_ts(ev["flow"]["start"])
    for lab, s, e, dsts, srcs in intervals:
        if s <= t <= e and (not dsts or ev.get("dest_ip") in dsts) and (not srcs or ev.get("src_ip") in srcs):
            return lab
    return "BENIGN"


def build(eve_files, label_file, cap, seed):
    evs = read_flows(eve_files)
    intervals = load_intervals(label_file)
    fz = FlowFeaturizer()
    rows, labels = [], []
    for ev in evs:
        rows.append(fz.vector(ev, EVE_FEATURES))
        labels.append(label_of(ev, intervals))
    df = pd.DataFrame(np.vstack(rows), columns=EVE_FEATURES).astype(np.float32)
    df["label"] = labels
    df["binary"] = (df["label"] != "BENIGN").astype(np.int64)
    if cap:  # lấy tối đa `cap` flow mỗi loại tấn công, giữ toàn bộ BENIGN
        keep = [g.index if lab == "BENIGN" or len(g) <= cap else g.sample(cap, random_state=seed).index
                for lab, g in df.groupby("label")]
        df = df.loc[np.sort(np.concatenate(keep))]
    print(f"  {len(evs)} flow -> {df['label'].value_counts().to_dict()}")
    return df.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-eve", nargs="+", required=True)
    ap.add_argument("--train-labels")
    ap.add_argument("--test-eve", nargs="+", required=True)
    ap.add_argument("--test-labels")
    ap.add_argument("--max-per-attack", type=int, default=30_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(paths.DATA))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    print("[train]"); build(a.train_eve, a.train_labels, a.max_per_attack, a.seed).to_parquet(out / "train_pool.parquet", index=False)
    print("[test]"); build(a.test_eve, a.test_labels, a.max_per_attack, a.seed).to_parquet(out / "test_day2.parquet", index=False)
    json.dump({"branch": "B", "features": EVE_FEATURES}, open(out / "features.json", "w", encoding="utf-8"), indent=2)
    print(f"Đã ghi {out}/train_pool.parquet, test_day2.parquet, features.json ({len(EVE_FEATURES)} đặc trưng)")


if __name__ == "__main__":
    main()
