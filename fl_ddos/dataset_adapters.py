"""Adapter cho ba nguồn dữ liệu của pipeline multidataset_v1 (kế hoạch mục 3–5).

Mỗi adapter đọc định dạng gốc của một nguồn và trả về các batch ở **schema chuẩn**:

  metadata (không đưa vào mô hình): dataset_id, capture_id, row_id, original_label, timestamp,
                                     fingerprint, sel_hash, y
  4 trường cơ sở:                    duration_s, fwd_packets, bwd_packets, protocol_group

  CIC-DDoS2019  Parquet  Flow Duration (µs) / 1e6, Total Fwd/Backward Packets, Protocol (số)
  UNSW-NB15     CSV      dur (s), spkts, dpkts, proto (chuỗi); nhãn attack_cat + label nhị phân
  IoT-23        tar.gz   conn.log.labeled (Zeek): duration, orig_pkts, resp_pkts, proto; label + detailed-label

Nhãn được ánh xạ bằng bảng tường minh trong configs/multidataset.json, không dùng substring tùy ý.
Nhãn lạ/mâu thuẫn -> y = -1 và một mục trong `issues`; pipeline không xuất artifact khi còn mục này.
"""
from __future__ import annotations

import io
import re
import tarfile
from collections import Counter
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

CLASSES = ["BENIGN", "DOS_DDOS", "OTHER_ATTACK"]
BASE = ["duration_s", "fwd_packets", "bwd_packets", "protocol_group"]
META = ["dataset_id", "capture_id", "row_id", "original_label", "timestamp", "fingerprint", "sel_hash", "y"]
PROTO_GROUPS = ["tcp", "udp", "icmp", "other"]
UNKNOWN = -1

_PROTO_NUM = {6: "tcp", 17: "udp", 1: "icmp", 58: "icmp"}
_PROTO_STR = {"tcp": "tcp", "udp": "udp", "icmp": "icmp", "ipv6-icmp": "icmp", "icmpv6": "icmp", "icmp6": "icmp",
              "6": "tcp", "17": "udp", "1": "icmp", "58": "icmp"}


# ---------------------------------------------------------------- tiện ích chung
def hash_key(seed: int) -> str:
    """Khóa 16 ký tự cho pd.util.hash_array: cùng seed -> cùng hash trên mọi máy."""
    return f"multids{seed:09d}"[:16]


def stable_hash(values, seed: int) -> np.ndarray:
    return pd.util.hash_array(np.asarray(values, dtype=object), hash_key=hash_key(seed)).astype(np.uint64)


def row_fingerprint(frame: pd.DataFrame) -> np.ndarray:
    """Hash của vector phép đo flow gốc (không index, không ID/nhãn) để gom các dòng trùng vector."""
    return pd.util.hash_pandas_object(frame.reset_index(drop=True), index=False).values.astype(np.uint64)


def protocol_group(values) -> np.ndarray:
    s = pd.Series(values)
    if pd.api.types.is_numeric_dtype(s):
        return s.map(lambda v: _PROTO_NUM.get(int(v), "other") if pd.notna(v) else "other").values.astype(object)
    return s.astype(str).str.strip().str.lower().map(lambda v: _PROTO_STR.get(v, "other")).values.astype(object)


def _norm_key(s) -> str:
    return re.sub(r"\s+", "", str(s).strip().lower())


def build_label_lookup(label_map: dict, dataset_id: str) -> dict:
    """{nhãn gốc đã chuẩn hóa: chỉ số lớp} cho CIC/UNSW; kiểm tra một nhãn không thuộc hai lớp."""
    out = {}
    for cls, names in label_map[dataset_id].items():
        for n in names:
            k = _norm_key(n)
            if k in out and out[k] != CLASSES.index(cls):
                raise ValueError(f"{dataset_id}: nhãn '{n}' được gán cho hai lớp")
            out[k] = CLASSES.index(cls)
    return out


def finalize(df: pd.DataFrame, drops: Counter) -> pd.DataFrame:
    """Kiểm tra chất lượng 4 trường cơ sở; loại dòng packet không hợp lệ và ghi lý do theo nhãn gốc."""
    for c in ("duration_s", "fwd_packets", "bwd_packets"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(np.float64)
    fwd, bwd = df["fwd_packets"].values, df["bwd_packets"].values
    bad_cnt = ~np.isfinite(fwd) | ~np.isfinite(bwd) | (fwd < 0) | (bwd < 0)
    bad_tot = ~bad_cnt & ((fwd + bwd) <= 0)
    for mask, reason in ((bad_cnt, "packet_count_invalid"), (bad_tot, "total_packets_not_positive")):
        if mask.any():
            for lab, n in df.loc[mask, "original_label"].value_counts().items():
                drops[(reason, str(lab))] += int(n)
    dur = df["duration_s"].values
    df.loc[~np.isfinite(dur) | (dur < 0), "duration_s"] = np.nan  # âm / sentinel -> missing, không đổi thành 0
    return df.loc[~(bad_cnt | bad_tot)].reset_index(drop=True)


# ---------------------------------------------------------------- CIC-DDoS2019
CIC_FIELDS = {"duration_s": "Flow Duration", "fwd_packets": "Total Fwd Packets",
              "bwd_packets": "Total Backward Packets", "protocol_group": "Protocol"}


def cic_frame(raw: pd.DataFrame, source_file: str, start: int, cfg: dict, issues: Counter,
              drops: Counter) -> pd.DataFrame:
    lookup = build_label_lookup(cfg["label_map"], "cicddos2019")
    missing = [c for c in [*CIC_FIELDS.values(), "Label"] if c not in raw.columns]
    if missing:
        raise ValueError(f"CIC {source_file}: thiếu cột {missing}")
    labels = raw["Label"].astype(str).str.strip()
    y = labels.map(lambda s: lookup.get(_norm_key(s), UNKNOWN)).astype(np.int64).values
    for lab in labels[y == UNKNOWN].unique():
        issues[("cicddos2019", f"unknown_label:{lab}")] += int((labels == lab).sum())
    measure = raw.drop(columns=["Label"])
    rid = [f"{source_file}:{i}" for i in range(start, start + len(raw))]
    df = pd.DataFrame({
        "dataset_id": "cicddos2019", "capture_id": source_file, "row_id": rid,
        "original_label": labels.values, "timestamp": np.nan,
        "fingerprint": row_fingerprint(measure), "sel_hash": stable_hash(rid, cfg["prep_seed"]), "y": y,
        "duration_s": pd.to_numeric(raw["Flow Duration"], errors="coerce").astype(np.float64).values / 1e6,
        "fwd_packets": raw["Total Fwd Packets"].values, "bwd_packets": raw["Total Backward Packets"].values,
        "protocol_group": protocol_group(raw["Protocol"].values),
    })
    return finalize(df, drops)


def cic_unit_check(raw: pd.DataFrame) -> dict:
    """Flow Duration là µs nếu (fwd+bwd)/duration·1e6 ≈ Flow Packets/s (phân vị 1/50/99% của tỷ lệ ≈ 1)."""
    d = pd.to_numeric(raw["Flow Duration"], errors="coerce").values.astype(float)
    pk = (raw["Total Fwd Packets"].values + raw["Total Backward Packets"].values).astype(float)
    rate = pd.to_numeric(raw.get("Flow Packets/s", pd.Series(np.nan, index=raw.index)), errors="coerce").values
    ok = (d > 0) & np.isfinite(rate) & (rate > 0)
    if ok.sum() < 10:
        return {"check": "cic_duration_microseconds", "passed": None, "n": int(ok.sum())}
    ratio = pk[ok] / d[ok] * 1e6 / rate[ok]
    q = np.quantile(ratio, [0.01, 0.5, 0.99])
    return {"check": "cic_duration_microseconds", "passed": bool(0.9 < q[1] < 1.1), "n": int(ok.sum()),
            "ratio_q01_q50_q99": [float(v) for v in q]}


# ---------------------------------------------------------------- UNSW-NB15
UNSW_REQUIRED = ["id", "dur", "proto", "spkts", "dpkts", "attack_cat", "label"]


def looks_like_html(head: bytes) -> bool:
    h = head.lstrip(b"\xef\xbb\xbf").lstrip().lower()
    return h.startswith(b"<!doctype") or h.startswith(b"<html") or b"<head" in h[:512]


def read_unsw_csv(path) -> pd.DataFrame:
    with open(path, "rb") as fh:
        if looks_like_html(fh.read(2048)):
            raise ValueError(f"{path}: nội dung là HTML (trang đăng nhập/lỗi), không phải CSV UNSW-NB15")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [c.strip().lstrip("﻿") for c in df.columns]
    missing = [c for c in UNSW_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: thiếu cột {missing}; header = {list(df.columns)[:12]}...")
    return df


def unsw_frame(raw: pd.DataFrame, split: str, cfg: dict, issues: Counter, drops: Counter) -> pd.DataFrame:
    lookup = build_label_lookup(cfg["label_map"], "unsw_nb15")
    cat = raw["attack_cat"].fillna("").astype(str).str.strip()
    cat = cat.where(cat != "", "Normal")  # một số bản để trống attack_cat của flow normal
    y = cat.map(lambda s: lookup.get(_norm_key(s), UNKNOWN)).astype(np.int64).values
    for lab in cat[y == UNKNOWN].unique():
        issues[("unsw_nb15", f"unknown_label:{lab}")] += int((cat == lab).sum())
    binary = pd.to_numeric(raw["label"], errors="coerce").values
    conflict = (y != UNKNOWN) & (((y == 0) & (binary != 0)) | ((y > 0) & (binary != 1)))
    if conflict.any():
        for lab in cat[conflict].unique():
            issues[("unsw_nb15", f"label_binary_conflict:{lab}")] += int((cat[conflict] == lab).sum())
        y = np.where(conflict, UNKNOWN, y)
    dup = raw["id"].duplicated(keep=False)
    if dup.any():
        issues[("unsw_nb15", f"duplicate_id:{split}")] += int(dup.sum())
    measure = raw.drop(columns=["id", "attack_cat", "label"])
    rid = [f"{split}:{v}" for v in raw["id"].values]
    df = pd.DataFrame({
        "dataset_id": "unsw_nb15", "capture_id": f"unsw_{split}", "row_id": rid,
        "original_label": cat.values, "timestamp": np.nan,
        "fingerprint": row_fingerprint(measure), "sel_hash": stable_hash(rid, cfg["prep_seed"]), "y": y,
        "duration_s": raw["dur"].values, "fwd_packets": raw["spkts"].values, "bwd_packets": raw["dpkts"].values,
        "protocol_group": protocol_group(raw["proto"].values),
    })
    return finalize(df, drops)


# ---------------------------------------------------------------- IoT-23 (Zeek conn.log.labeled)
IOT_NEEDED = ["ts", "uid", "proto", "duration", "orig_pkts", "resp_pkts"]


def capture_id_from_member(name: str) -> str | None:
    """.../CTU-IoT-Malware-Capture-34-1/bro/conn.log.labeled -> CTU-IoT-Malware-Capture-34-1."""
    p = Path(name)
    if p.name != "conn.log.labeled":
        return None
    parts = p.parts
    return parts[-3] if len(parts) >= 3 and parts[-2] == "bro" else p.parent.name


class _Prepend(io.RawIOBase):
    """Luồng = phần đã đọc trước + phần còn lại của file (để pandas đọc tiếp sau khi tự đọc header)."""

    def __init__(self, head: bytes, rest):
        self.head, self.rest = head, rest

    def readable(self):
        return True

    def readinto(self, b):
        if self.head:
            n = min(len(b), len(self.head))
            b[:n], self.head = self.head[:n], self.head[n:]
            return n
        data = self.rest.read(len(b))
        b[:len(data)] = data
        return len(data)


def read_zeek_header(fh) -> tuple[dict, bytes]:
    """Đọc các dòng '#...' đầu file; trả (header, dòng dữ liệu đầu tiên)."""
    header = {}
    while True:
        line = fh.readline()
        if not line:
            return header, b""
        if not line.startswith(b"#"):
            return header, line
        txt = line.decode("utf-8", "replace").rstrip("\r\n")
        if txt.startswith("#separator"):
            header["separator"] = txt.split(" ", 1)[1].encode().decode("unicode_escape")
        else:
            key, _, val = txt[1:].partition(header.get("separator", "\t"))
            header[key] = val


def zeek_layout(header: dict, first_line: bytes) -> dict:
    """Xác định cột: bản IoT-23 có dòng dữ liệu mà 3 trường cuối (tunnel_parents, label, detailed-label)
    cách nhau bằng khoảng trắng thay vì tab. Trả về chỉ số cột cần đọc và cách tách nhãn."""
    sep = header.get("separator", "\t")
    fields = header.get("fields", "").split(sep)
    fields = [f for part in fields for f in (part.split() if " " in part.strip() else [part])]
    if not fields or "label" not in fields:
        raise ValueError(f"conn.log.labeled thiếu '#fields' có label: {fields}")
    n_cols = first_line.decode("utf-8", "replace").rstrip("\r\n").count(sep) + 1 if first_line else len(fields)
    idx = {f: i for i, f in enumerate(fields)}
    missing = [f for f in IOT_NEEDED if f not in idx]
    if missing:
        raise ValueError(f"conn.log.labeled thiếu trường {missing}")
    tail = fields[idx["label"] - 1:] if "tunnel_parents" in idx else fields[idx["label"]:]
    if n_cols == len(fields):
        merged = False
    elif n_cols == len(fields) - (len(tail) - 1):
        merged = True  # tunnel_parents/label/detailed-label gộp thành một cột, tách bằng khoảng trắng
    else:
        raise ValueError(f"conn.log.labeled: {n_cols} cột dữ liệu nhưng header có {len(fields)} trường")
    return {"sep": sep, "fields": fields, "n_cols": n_cols, "merged": merged, "tail": tail,
            "idx": idx, "tail_col": n_cols - 1 if merged else None}


def map_iot_labels(label: pd.Series, detailed: pd.Series, cfg: dict, issues: Counter) -> np.ndarray:
    m = cfg["label_map"]["iot23"]
    benign, malicious = set(m["benign_labels"]), set(m["malicious_labels"])
    dos, other = set(m["dos_tokens"]), set(m["other_tokens"])
    pairs = pd.DataFrame({"l": label.str.strip().str.lower(), "d": detailed.str.strip()})
    out = np.full(len(pairs), UNKNOWN, dtype=np.int64)
    for (l, d), g in pairs.groupby(["l", "d"], sort=False).groups.items():
        dl = d.lower()
        empty = dl in ("-", "", "(empty)")
        if l in benign:
            c = 0 if empty else None
            reason = None if empty else f"benign_with_detailed:{d}"
        elif l in malicious:
            toks = [t for t in dl.split("-") if t]
            if empty:
                c, reason = None, "malicious_without_detailed"
            elif any(t in dos for t in toks):
                c, reason = 1, None
            elif all(t in other for t in toks):
                c, reason = 2, None
            else:
                c, reason = None, f"unknown_detailed:{d}"
        else:
            c, reason = None, f"unknown_label:{l}"
        if c is None:
            issues[("iot23", reason)] += len(g)
        else:
            out[pairs.index.get_indexer(g)] = c
    return out


def iot_frame(chunk: pd.DataFrame, layout: dict, capture: str, start: int, cfg: dict, issues: Counter,
              drops: Counter) -> pd.DataFrame:
    idx = layout["idx"]
    if layout["merged"]:
        parts = chunk[layout["tail_col"]].astype(str).str.split(r"\s+", n=len(layout["tail"]) - 1, expand=True)
        parts = parts.reindex(columns=range(len(layout["tail"])), fill_value="-")
        tail = {f: parts[i] for i, f in enumerate(layout["tail"])}
        label, detailed = tail["label"], tail.get("detailed-label", pd.Series("-", index=chunk.index))
    else:
        label = chunk[idx["label"]].astype(str)
        detailed = chunk[idx["detailed-label"]].astype(str) if "detailed-label" in idx else \
            pd.Series("-", index=chunk.index)
    y = map_iot_labels(label, detailed, cfg, issues)
    orig = (label.str.strip() + "|" + detailed.str.strip()).values
    rid = [f"{capture}:{i}" for i in range(start, start + len(chunk))]

    def num(f):
        return pd.to_numeric(chunk[idx[f]].replace("-", np.nan), errors="coerce").values

    df = pd.DataFrame({
        "dataset_id": "iot23", "capture_id": capture, "row_id": rid, "original_label": orig,
        "timestamp": num("ts"), "fingerprint": np.uint64(0), "sel_hash": stable_hash(rid, cfg["prep_seed"]), "y": y,
        "duration_s": num("duration"), "fwd_packets": num("orig_pkts"), "bwd_packets": num("resp_pkts"),
        "protocol_group": protocol_group(chunk[idx["proto"]].astype(str).values),
        "flow_uid": chunk[idx["uid"]].astype(str).values,
    })
    return finalize(df, drops)


def iter_zeek_file(fh, capture: str, cfg: dict, issues: Counter, drops: Counter,
                   chunksize: int = 100_000) -> Iterator[pd.DataFrame]:
    header, first = read_zeek_header(fh)
    if not first:
        return
    layout = zeek_layout(header, first)
    want = sorted({layout["idx"][f] for f in IOT_NEEDED} |
                  ({layout["tail_col"]} if layout["merged"] else
                   {layout["idx"][f] for f in ("label", "detailed-label") if f in layout["idx"]}))
    reader = pd.read_csv(io.BufferedReader(_Prepend(first, fh), 1 << 20), sep=layout["sep"], header=None,
                         usecols=want, dtype=str, na_filter=False, chunksize=chunksize, quoting=3,
                         engine="c", on_bad_lines="error")
    start = 0
    for chunk in reader:
        chunk = chunk[~chunk[want[0]].str.startswith("#")]  # dòng '#close' cuối file
        if len(chunk):
            yield iot_frame(chunk, layout, capture, start, cfg, issues, drops)
            start += len(chunk)


def iter_iot_archive(archive, cfg: dict, issues: Counter, drops: Counter, skip=frozenset(),
                     chunksize: int = 100_000, on_capture_start=None) -> Iterator[tuple[str, pd.DataFrame]]:
    """Đọc tar.gz theo luồng ('r|gz'), không giải nén ra đĩa; chỉ xử lý conn.log.labeled."""
    with tarfile.open(archive, mode="r|gz") as tar:
        for member in tar:
            cap = capture_id_from_member(member.name) if member.isfile() else None
            if cap is None or cap in skip:
                continue
            if on_capture_start:
                on_capture_start(cap, member)
            fh = tar.extractfile(member)
            for frame in iter_zeek_file(fh, cap, cfg, issues, drops, chunksize):
                yield cap, frame
            yield cap, None  # đánh dấu capture đã đọc hết


# ---------------------------------------------------------------- giao diện chung
def iter_canonical_batches(dataset_id: str, source, chunksize: int, cfg: dict, issues: Counter | None = None,
                           drops: Counter | None = None, split: str = "train") -> Iterator[pd.DataFrame]:
    """Trả batch ở schema chuẩn cho một file nguồn (CIC parquet, UNSW csv, IoT conn.log.labeled hoặc tar.gz)."""
    issues = Counter() if issues is None else issues
    drops = Counter() if drops is None else drops
    source = Path(source)
    if dataset_id == "cicddos2019":
        raw = pd.read_parquet(source)
        for s in range(0, len(raw), chunksize):
            yield cic_frame(raw.iloc[s:s + chunksize], source.stem, s, cfg, issues, drops)
    elif dataset_id == "unsw_nb15":
        raw = read_unsw_csv(source)
        for s in range(0, len(raw), chunksize):
            yield unsw_frame(raw.iloc[s:s + chunksize], split, cfg, issues, drops)
    elif dataset_id == "iot23":
        if source.name.endswith(".tar.gz") or source.suffix == ".tgz":
            for _, frame in iter_iot_archive(source, cfg, issues, drops, chunksize=chunksize):
                if frame is not None:
                    yield frame
        else:
            with open(source, "rb") as fh:
                yield from iter_zeek_file(fh, capture_id_from_member(str(source)) or source.parent.name,
                                          cfg, issues, drops, chunksize)
    else:
        raise ValueError(f"dataset_id lạ: {dataset_id}")
