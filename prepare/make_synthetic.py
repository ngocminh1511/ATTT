"""Sinh dữ liệu GIẢ để kiểm tra pipeline khi chưa tải CIC-DDoS2019.

  data/raw/synthetic/01-12/*.csv, 03-11/*.csv  -> CSV có tên cột như CIC-DDoS2019 (Nhánh A)
  data/raw/synthetic_eve/day{1,2}/eve.json + attack_log.csv -> log Suricata giả (Nhánh B)

Kết quả huấn luyện trên dữ liệu này KHÔNG dùng cho báo cáo.
"""
import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
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


# ---------------------------------------------------------------- eve.json giả
def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")


def flow_event(rng, t_end, src, sport, dst, dport, proto, kind):
    if kind == "benign":
        dur = rng.lognormal(0, 1.2); ps = int(rng.integers(3, 40)); pc = int(ps * rng.uniform(0.5, 1.5))
        bs, bc = ps * int(rng.integers(60, 600)), pc * int(rng.integers(60, 1400))
        tcp = {"syn": True, "ack": True, "fin": True, "psh": True} if proto == "TCP" else None
        state, app = "closed" if proto == "TCP" else "established", "http" if dport == 80 else "dns" if dport == 53 else "tls"
    elif kind == "syn":
        dur, ps, pc, bs, bc = rng.uniform(0, 0.01), 1, int(rng.random() < 0.3), 60, 0
        tcp, state, app = {"syn": True}, "new", None
    elif kind == "udp":
        dur, ps, pc = rng.uniform(0, 0.05), int(rng.integers(1, 4)), 0
        bs, bc, tcp, state, app = ps * int(rng.integers(64, 512)), 0, None, "new", None
    elif kind == "icmp":
        dur, ps, pc, bs, bc, tcp, state, app = rng.uniform(0, 0.02), 1, 1, 84, 84, None, "established", None
    else:  # reflection (dns/ldap...): nguồn là reflector, gói lớn đổ về nạn nhân
        dur, ps, pc = rng.uniform(0, 0.1), int(rng.integers(1, 6)), 0
        bs, bc, tcp, state, app = ps * int(rng.integers(900, 1500)), 0, None, "new", "failed"
    ev = {"timestamp": iso(t_end), "event_type": "flow", "src_ip": src, "src_port": sport,
          "dest_ip": dst, "dest_port": dport, "proto": proto, "app_proto": app,
          "flow": {"pkts_toserver": ps, "pkts_toclient": pc, "bytes_toserver": bs,
                   "bytes_toclient": bc, "start": iso(t_end - dur), "end": iso(t_end),
                   "age": int(dur), "state": state, "reason": "timeout", "alerted": False}}
    if tcp:
        ev["tcp"] = tcp
    return ev


def write_eve_day(rng, out: Path, t0: float, attacks, seconds=240, victim="192.168.50.4"):
    out.mkdir(parents=True, exist_ok=True)
    events, log = [], []
    servers = [victim, "192.168.50.5", "192.168.50.6"]
    for s in range(seconds):  # nền: ~20 flow/s
        for _ in range(int(rng.poisson(20))):
            t = t0 + s + rng.random()
            proto, dport = ("UDP", 53) if rng.random() < 0.2 else ("TCP", int(rng.choice([80, 443])))
            events.append(flow_event(rng, t, f"10.0.0.{rng.integers(2, 60)}", int(rng.integers(1024, 65535)),
                                     str(rng.choice(servers)), dport, proto, "benign"))
    for k, (label, kind, dport, rate) in enumerate(attacks):
        a0 = t0 + 30 + k * 60; a1 = a0 + 40
        log.append({"label": label, "start": iso(a0), "end": iso(a1), "dest_ip": victim, "src_ip": ""})
        for s in range(40):
            for _ in range(int(rng.poisson(rate))):
                t = a0 + s + rng.random()
                src = f"172.16.{rng.integers(0, 255)}.{rng.integers(1, 255)}"
                sport = dport if kind == "refl" else int(rng.integers(1024, 65535))
                proto = {"syn": "TCP", "icmp": "ICMP"}.get(kind, "UDP")
                events.append(flow_event(rng, t, src, sport, victim,
                                         80 if kind == "syn" else int(rng.integers(1024, 65535)) if kind == "refl" else dport,
                                         proto, kind))
    events.sort(key=lambda e: e["timestamp"])
    with open(out / "eve.json", "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    with open(out / "attack_log.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["label", "start", "end", "dest_ip", "src_ip"])
        w.writeheader(); w.writerows(log)
    print(f"[eve] {out}: {len(events)} flow, {len(log)} đợt tấn công")


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
    t1 = datetime(2019, 1, 12, 10, tzinfo=timezone.utc).timestamp()
    t2 = datetime(2019, 3, 11, 10, tzinfo=timezone.utc).timestamp()
    write_eve_day(rng, raw / "synthetic_eve" / "day1", t1,
                  [("SYN", "syn", 80, 300), ("DNS", "refl", 53, 200), ("UDP", "udp", 53, 250)])
    write_eve_day(rng, raw / "synthetic_eve" / "day2", t2,
                  [("SYN", "syn", 80, 250), ("LDAP", "refl", 389, 200), ("ICMP", "icmp", 0, 200)])


if __name__ == "__main__":
    main()
