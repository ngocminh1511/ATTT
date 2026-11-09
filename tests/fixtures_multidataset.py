"""Fixture nhỏ mô phỏng định dạng gốc của hai nguồn (chỉ để kiểm thử logic, không phải kết quả học)."""
import copy
from pathlib import Path

import numpy as np
import pandas as pd

from fl_ddos.multidataset_prep import read_json

ROOT = Path(__file__).resolve().parent.parent
CIC_EXTRA = ["Fwd Packets Length Total", "Bwd Packets Length Total"]


def base_config() -> dict:
    return read_json(ROOT / "configs" / "multidataset.json")


def cic_frame(rng, n, labels):
    lab = rng.choice(labels, n)
    dur = rng.integers(1, 5_000_000, n).astype(np.int32)
    f, b = rng.integers(1, 50, n).astype(np.int16), rng.integers(0, 50, n).astype(np.int16)
    proto = rng.choice(np.array([6, 17, 0], dtype=np.int8), n)
    df = pd.DataFrame({"Protocol": proto, "Flow Duration": dur, "Total Fwd Packets": f, "Total Backward Packets": b,
                       "Fwd Packets Length Total": rng.integers(0, 9000, n).astype(float),
                       "Bwd Packets Length Total": rng.integers(0, 9000, n).astype(float),
                       "Fwd IAT Mean": rng.integers(0, 100_000, n).astype(float),
                       "Bwd IAT Mean": rng.integers(0, 100_000, n).astype(float),
                       "Flow Packets/s": (f.astype(float) + b) / dur * 1e6, "Label": lab})
    df["Label"] = df["Label"].astype("category")
    return df


def unsw_frame(rng, n, start_id):
    cats = rng.choice(["Normal", "DoS", "Exploits", "Generic", " Fuzzers "], n, p=[.4, .2, .2, .1, .1])
    s, d = rng.integers(1, 40, n), rng.integers(0, 40, n)
    dur = np.round(rng.random(n) * 3, 6)
    dur[:3] = 0.0
    return pd.DataFrame({"id": np.arange(start_id, start_id + n), "dur": dur,
                         "proto": rng.choice(["tcp", "udp", "arp", "icmp"], n), "service": "-", "state": "FIN",
                         "spkts": s, "dpkts": d, "sbytes": s * 60, "dbytes": d * 60,
                         "rate": np.where(dur > 0, (s + d - 1) / np.where(dur > 0, dur, 1), 0),
                         "sinpkt": np.round(rng.random(n) * 100, 3), "dinpkt": np.round(rng.random(n) * 100, 3),
                         "attack_cat": cats, "label": (np.char.strip(cats.astype(str)) != "Normal").astype(int)})


def build(root: Path, seed: int = 0, cic_labels_train=("Benign", "DrDoS_DNS", "Syn"),
          cic_labels_test=("Benign", "LDAP", "Syn")) -> dict:
    rng = np.random.default_rng(seed)
    cfg = copy.deepcopy(base_config())
    cic = root / "data/raw/cicddos2019"
    cic.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(["DNS-testing", "Syn-testing", "LDAP-training"]):
        labs = cic_labels_test if name.endswith("training") else cic_labels_train
        cic_frame(rng, 400, list(labs)).to_parquet(cic / f"{name}.parquet", index=False)
    cfg["sources"]["cicddos2019"]["expected_files"] = 3
    un = root / "data/raw/unsw_nb15"
    un.mkdir(parents=True, exist_ok=True)
    tr, te = unsw_frame(rng, 600, 1), unsw_frame(rng, 300, 1)
    for df, name in ((tr, "UNSW_NB15_training-set.csv"), (te, "UNSW_NB15_testing-set.csv")):
        df.to_csv(un / name, index=False, encoding="utf-8-sig")
    cfg["sources"]["unsw_nb15"]["files"]["train"]["rows"] = len(tr)
    cfg["sources"]["unsw_nb15"]["files"]["test"]["rows"] = len(te)
    cfg["profiles"]["tiny"] = {"train": 200, "val": 80, "test": 120, "train_min_per_class": 10,
                                "eval_min_per_class": {"val": 5, "test": 5},
                                "eval_max_samples": {"val": 120, "test": 180}}
    return cfg
