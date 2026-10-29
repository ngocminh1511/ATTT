"""Tiền xử lý dùng chung: slog1p, đọc features.json/scaler.json, chuẩn hóa nhãn CIC-DDoS2019.

Mọi đặc trưng đều qua slog1p() rồi chuẩn hóa bằng scaler.json (mean/std liên kết).
"""
import json

import numpy as np

from fl_ddos import paths


# ---------------------------------------------------------------- biến đổi chung
def slog1p(x):
    """log1p có dấu: an toàn với giá trị âm (vd. Init_Win_bytes = -1 trong CIC)."""
    x = np.asarray(x, dtype=np.float64)
    return np.sign(x) * np.log1p(np.abs(x))


def load_meta(path=None):
    """features.json: {"features": [...]}; chấp nhận cả dạng list cũ."""
    meta = json.load(open(path or paths.FEATURES_JSON, encoding="utf-8"))
    if isinstance(meta, list):
        meta = {"features": meta}
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
