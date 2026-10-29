"""Sinh dữ liệu GIẢ để kiểm tra pipeline khi chưa tải CIC-DDoS2019.

  data/raw/synthetic/01-12/*.csv, 03-11/*.csv  -> CSV có tên cột như CIC-DDoS2019

Kết quả huấn luyện trên dữ liệu này KHÔNG dùng cho báo cáo.
"""
import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

# loại -> (proto, dst_port | None=ngẫu nhiên, số gói fwd, kích thước gói, thời lượng µs, syn, ack)
PROFILES = {
    "BENIGN":      (None, None, 12, 400, 2e6, 0.3, 0.8),
    "DrDoS_DNS":   (17, 53, 4, 1300, 3e3, 0, 0),
    "DrDoS_LDAP":  (17, 389, 4, 1100, 3e3, 0, 0),
    "DrDoS_NTP":   (17, 123, 6, 460, 2e3, 0, 0),
    "DrDoS_MSSQL": (17, 1434, 4, 380, 2e3, 0, 0),
    "DrDoS_NetBIOS": (17, 137, 3, 260, 2e3, 0, 0),
    "DrDoS_SNMP":  (17, 161, 4, 1200, 3e3, 0, 0),
    "DrDoS_SSDP":  (17, 1900, 5, 300, 2e3, 0, 0),
    "DrDoS_UDP":   (17, None, 3, 380, 1e3, 0, 0),
    "UDP-lag":     (17, None, 3, 320, 8e4, 0, 0),
    "Syn":         (6, 80, 2, 0, 5e4, 1, 0),
    "TFTP":        (17, 69, 3, 500, 2e3, 0, 0),
    "WebDDoS":     (6, 80, 5, 120, 1e6, 1, 1),
    "Portmap":     (6, None, 1, 0, 50, 1, 0),
}
DAY1 = ["DrDoS_DNS", "DrDoS_LDAP", "DrDoS_MSSQL", "DrDoS_NetBIOS", "DrDoS_NTP", "DrDoS_SNMP",
        "DrDoS_SSDP", "DrDoS_UDP", "Syn", "TFTP", "UDP-lag", "WebDDoS"]
DAY2 = ["Portmap", "NetBIOS", "LDAP", "MSSQL", "UDP", "UDPLag", "Syn"]  # tên file ngày 2 trong CIC
DAY2_PROFILE = {"NetBIOS": "DrDoS_NetBIOS", "LDAP": "DrDoS_LDAP", "MSSQL": "DrDoS_MSSQL",
                "UDP": "DrDoS_UDP", "UDPLag": "UDP-lag", "Syn": "Syn", "Portmap": "Portmap"}

COLUMNS = ["Unnamed: 0", "Flow ID", " Source IP", " Source Port", " Destination IP",
           " Destination Port", " Protocol", " Timestamp", " Flow Duration", " Total Fwd Packets",
           " Total Backward Packets", "Total Length of Fwd Packets", " Total Length of Bwd Packets",
           " Fwd Packet Length Max", " Fwd Packet Length Mean", " Average Packet Size",
           "Flow Bytes/s", " Flow Packets/s", " Flow IAT Mean", " SYN Flag Count",
           " ACK Flag Count", " Bwd PSH Flags", "Init_Win_bytes_forward", " Inbound",
           "SimillarHTTP", " Label"]


def gen_rows(rng, label, profile, n, victim, start):
    proto, dport, pk, size, dur, syn, ack = PROFILES[profile]
    rows = []
    for i in range(n):
        p = proto if proto is not None else rng.choice([6, 17], p=[0.7, 0.3])
        port = dport if dport is not None else int(rng.choice([80, 443, 53, 8080, int(rng.integers(1, 65535))]))
        fwd = max(1, int(rng.lognormal(np.log(pk), 0.6)))
        bwd = int(rng.poisson(fwd * 0.8)) if profile in ("BENIGN", "WebDDoS") else int(rng.random() < 0.1)
        plen = max(0.0, rng.lognormal(np.log(size + 1), 0.5) - 1)
        d = max(1.0, rng.lognormal(np.log(dur), 1.0))
        tot_f, tot_b = fwd * plen, bwd * plen * 1.5
        bps = (tot_f + tot_b) / (d / 1e6) if rng.random() > 0.01 else float("inf")  # giống CIC: có inf
        ts = start + timedelta(milliseconds=int(i * 5))
        src = f"172.16.{rng.integers(0, 255)}.{rng.integers(1, 255)}"
        rows.append([i, f"{src}-{victim}-{p}", src, int(rng.integers(1024, 65535)), victim, port, p,
                     ts.strftime("%Y-%m-%d %H:%M:%S.%f"), d, fwd, bwd, tot_f, tot_b, plen * 1.2,
                     plen, plen * 0.98 + rng.normal(0, 1), bps, (fwd + bwd) / (d / 1e6),
                     d / max(fwd + bwd - 1, 1), int(rng.random() < syn), int(rng.random() < ack),
                     0, int(rng.choice([-1, 0, 8192, 65535])), int(rng.random() < 0.5), 0, label])
    return rows


def write_csv_day(rng, out: Path, files, n_attack, n_benign, victim, day):
    out.mkdir(parents=True, exist_ok=True)
    start = datetime(2019, 1 if day == 1 else 3, 12 if day == 1 else 11, 10, 0)
    for name in files:
        profile = DAY2_PROFILE.get(name, name) if day == 2 else name
        rows = gen_rows(rng, name, profile, n_attack, victim, start)
        rows += gen_rows(rng, "BENIGN", "BENIGN", n_benign // len(files), victim, start)
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLUMNS)
            w.writerows(rows)
    print(f"[csv] {out}: {len(files)} file")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-attack", type=int, default=3000)
    ap.add_argument("--n-benign", type=int, default=12000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    raw = ROOT / "data" / "raw"
    write_csv_day(rng, raw / "synthetic" / "01-12", DAY1, a.n_attack, a.n_benign, "192.168.50.1", 1)
    write_csv_day(rng, raw / "synthetic" / "03-11", DAY2, a.n_attack * 2 // 3, a.n_benign, "192.168.50.4", 2)


if __name__ == "__main__":
    main()
