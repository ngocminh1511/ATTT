"""Fixture nhỏ mô phỏng định dạng gốc của ba nguồn (chỉ để kiểm thử logic, không phải kết quả học)."""
import copy
import io
import json
import tarfile
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
                         "attack_cat": cats, "label": (np.char.strip(cats.astype(str)) != "Normal").astype(int)})


IOT_FIELDS = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "service", "duration",
              "orig_bytes", "resp_bytes", "conn_state", "local_orig", "local_resp", "missed_bytes", "history",
              "orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes", "tunnel_parents", "label", "detailed-label"]
IOT_LABELS = [("Benign", "-"), ("Malicious", "DDoS"), ("Malicious", "PartOfAHorizontalPortScan"),
              ("Malicious", "C&C-HeartBeat"), ("Malicious", "Okiru")]


def zeek_log(rng, n, merged: bool, extra_labels=()) -> bytes:
    lines = ["#separator \\x09", "#set_separator\t,", "#empty_field\t(empty)", "#unset_field\t-",
             "#path\tconn", "#open\t2019-01-01-00-00-00", "#fields\t" + "\t".join(IOT_FIELDS[:-3]) +
             "\ttunnel_parents   label   detailed-label",
             "#types\t" + "\t".join(["time"] + ["string"] * 19) + "\tset[string]   string   string"]
    pool = IOT_LABELS + list(extra_labels)
    for i in range(n):
        lab, det = pool[i % len(pool)]
        dur = "-" if i % 7 == 0 else f"{rng.random() * 10:.6f}"
        row = [f"{1.5e9 + i:.6f}", f"C{i:08d}", "192.168.1.1", "1234", "10.0.0.1", "80",
               rng.choice(["tcp", "udp", "icmp"]), "-", dur, "0", "0", "S0", "-", "-", "0", "S",
               str(int(rng.integers(1, 20))), "100", str(int(rng.integers(0, 20))), "0"]
        tail = ["(empty)", lab, det]
        lines.append("\t".join(row) + ("\t" + "   ".join(tail) if merged else "\t" + "\t".join(tail)))
    lines.append("#close\t2019-01-01-01-00-00")
    return ("\n".join(lines) + "\n").encode()


def build(root: Path, seed: int = 0, n_captures: int = 6, rows_per_capture: int = 300,
          iot_extra_labels=(), cic_labels_train=("Benign", "DrDoS_DNS", "Syn"),
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
    iot = root / "data/raw/iot23"
    iot.mkdir(parents=True, exist_ok=True)
    with tarfile.open(iot / cfg["sources"]["iot23"]["archive"], "w:gz") as tar:
        tar.addfile(tarfile.TarInfo("opt/README.md"), io.BytesIO(b""))
        for k in range(n_captures):
            data = zeek_log(rng, rows_per_capture + 17 * k, merged=k % 2 == 0, extra_labels=iot_extra_labels)
            ti = tarfile.TarInfo(f"opt/Malware-Project/BigDataset/IoTScenarios/CTU-IoT-Malware-Capture-{k}-1/bro/"
                                 "conn.log.labeled")
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
    cfg["split"]["iot_reservoir_per_capture_class"] = 50
    cfg["split"]["iot_batch_rows"] = 64
    cfg["profiles"]["tiny"] = {"train": 200, "val": 80, "test": 120}
    return cfg
