"""Tiền xử lý DÙNG CHUNG cho huấn luyện và phát hiện thời gian thực.

Lỗi phổ biến nhất khi demo (mục 9.3) là đặc trưng lúc train khác lúc chạy. Vì vậy:
  - prepare/suricata_to_features.py (Nhánh B) và detector/realtime.py cùng gọi FlowFeaturizer;
  - mọi đặc trưng đều qua slog1p() rồi chuẩn hóa bằng scaler.json (mean/std liên kết).
"""
import json
import math
from collections import Counter
from datetime import datetime

import numpy as np

from fl_ddos import paths


# ---------------------------------------------------------------- biến đổi chung
def slog1p(x):
    """log1p có dấu: an toàn với giá trị âm (vd. Init_Win_bytes = -1 trong CIC)."""
    x = np.asarray(x, dtype=np.float64)
    return np.sign(x) * np.log1p(np.abs(x))


def load_meta(path=None):
    """features.json: {"branch": "A"|"B", "features": [...]}; chấp nhận cả dạng list cũ."""
    meta = json.load(open(path or paths.FEATURES_JSON, encoding="utf-8"))
    if isinstance(meta, list):
        meta = {"branch": "A", "features": meta}
    return meta


def load_scaler(path=None):
    s = json.load(open(path or paths.SCALER_JSON, encoding="utf-8"))
    return np.array(s["mean"], dtype=np.float64), np.array(s["std"], dtype=np.float64)


def standardize(x, mean, std):
    return (x - mean) / (std + 1e-8)


# ---------------------------------------------------------------- nhãn CIC-DDoS2019
# Tên nhãn trong CSV gốc / bản Kaggle khác nhau giữa hai ngày -> quy về tên chuẩn.
_LABEL_MAP = {
    "benign": "BENIGN",
    "drdos_dns": "DNS", "dns": "DNS",
    "drdos_ldap": "LDAP", "ldap": "LDAP",
    "drdos_mssql": "MSSQL", "mssql": "MSSQL",
    "drdos_netbios": "NetBIOS", "netbios": "NetBIOS",
    "drdos_ntp": "NTP", "ntp": "NTP",
    "drdos_snmp": "SNMP", "snmp": "SNMP",
    "drdos_ssdp": "SSDP", "ssdp": "SSDP",
    "drdos_udp": "UDP", "udp": "UDP", "udpflood": "UDP",
    "syn": "SYN", "synflood": "SYN",
    "tftp": "TFTP",
    "udp-lag": "UDP-Lag", "udplag": "UDP-Lag", "udp_lag": "UDP-Lag",
    "webddos": "WebDDoS",
    "portmap": "PortScan", "portscan": "PortScan",
    "icmp": "ICMP", "icmpflood": "ICMP",
}


def normalize_label(s: str) -> str:
    key = str(s).strip().lower().replace(" ", "")
    return _LABEL_MAP.get(key, str(s).strip())


# ---------------------------------------------------------------- Nhánh B: eve.json
FLOW_FEATURES = [
    "is_tcp", "is_udp", "is_icmp", "dest_port", "has_app_proto",
    "pkts_toserver", "pkts_toclient", "bytes_toserver", "bytes_toclient",
    "duration", "age", "state_established", "state_closed", "alerted",
    "syn", "ack", "fin", "rst", "psh",
    "bpp_s", "bpp_c", "ratio_pkts", "pps", "bps",
]
WINDOW_FEATURES = ["win_flows", "win_srcs", "win_sport_entropy", "win_syn_only_ratio"]
EVE_FEATURES = FLOW_FEATURES + WINDOW_FEATURES


def parse_ts(s: str) -> float:
    """'2019-01-12T10:00:00.123456+0000' -> epoch giây."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def flow_row(ev: dict) -> dict:
    """Đặc trưng của một sự kiện flow đơn lẻ (chưa log1p)."""
    f, t = ev["flow"], ev.get("tcp", {}) or {}
    start, end = parse_ts(f["start"]), parse_ts(f["end"])
    dur = max(end - start, 1e-3)
    p_s, p_c = f.get("pkts_toserver", 0), f.get("pkts_toclient", 0)
    b_s, b_c = f.get("bytes_toserver", 0), f.get("bytes_toclient", 0)
    proto = str(ev.get("proto", "")).upper()
    state = f.get("state", "")
    return {
        "is_tcp": int(proto == "TCP"), "is_udp": int(proto == "UDP"),
        "is_icmp": int(proto.startswith("ICMP") or proto == "IPV6-ICMP"),
        "dest_port": ev.get("dest_port", 0) or 0,
        "has_app_proto": int(ev.get("app_proto") not in (None, "", "failed")),
        "pkts_toserver": p_s, "pkts_toclient": p_c,
        "bytes_toserver": b_s, "bytes_toclient": b_c,
        "duration": dur, "age": f.get("age", 0),
        "state_established": int(state == "established"), "state_closed": int(state == "closed"),
        "alerted": int(bool(f.get("alerted", False))),
        "syn": int(bool(t.get("syn"))), "ack": int(bool(t.get("ack"))),
        "fin": int(bool(t.get("fin"))), "rst": int(bool(t.get("rst"))),
        "psh": int(bool(t.get("psh"))),
        "bpp_s": b_s / max(p_s, 1), "bpp_c": b_c / max(p_c, 1),
        "ratio_pkts": p_c / max(p_s, 1),
        "pps": (p_s + p_c) / dur, "bps": (b_s + b_c) / dur,
    }


class FlowFeaturizer:
    """Biến sự kiện flow thành vector, kèm thống kê cửa sổ 1 giây theo dest_ip.

    Cửa sổ là *nhân quả*: chỉ dùng các flow đã thấy trước đó (và flow hiện tại) trong
    cùng giây, nên chạy offline (Nhánh B) hay realtime đều cho cùng kết quả nếu
    sự kiện đến theo thứ tự thời gian kết thúc flow.
    """

    def __init__(self, window_s: float = 1.0):
        self.window_s = window_s
        self.win = {}

    def _window(self, ev: dict, row: dict, t_end: float) -> dict:
        dst = ev.get("dest_ip", "?")
        bucket = math.floor(t_end / self.window_s)
        w = self.win.get(dst)
        if w is None or w["bucket"] != bucket:
            w = {"bucket": bucket, "n": 0, "srcs": set(), "sports": Counter(), "syn_only": 0}
            self.win[dst] = w
            if len(self.win) > 50_000:  # dọn các đích cũ
                self.win = {k: v for k, v in self.win.items() if v["bucket"] >= bucket - 2}
                self.win[dst] = w
        w["n"] += 1
        w["srcs"].add(ev.get("src_ip"))
        w["sports"][ev.get("src_port", 0)] += 1
        w["syn_only"] += int(row["syn"] == 1 and row["ack"] == 0)
        n = w["n"]
        ent = -sum((c / n) * math.log2(c / n) for c in w["sports"].values()) if n > 1 else 0.0
        return {"win_flows": n, "win_srcs": len(w["srcs"]),
                "win_sport_entropy": ent, "win_syn_only_ratio": w["syn_only"] / n}

    def row(self, ev: dict) -> dict:
        r = flow_row(ev)
        r.update(self._window(ev, r, parse_ts(ev["flow"]["end"])))
        return r

    def vector(self, ev: dict, features: list) -> np.ndarray:
        """Vector đã slog1p (chưa chuẩn hóa) theo đúng thứ tự trong features.json."""
        r = self.row(ev)
        return slog1p([r[k] for k in features])
