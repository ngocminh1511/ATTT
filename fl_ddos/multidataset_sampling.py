"""Lấy mẫu tái lập theo quota lớp, chỉ dựa trên nhãn/counts, không dùng điểm mô hình."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

SPLITS = ("train", "val", "test")
POLICY_VERSION = "class_quota_v3"


class PrepError(RuntimeError):
    """Dữ liệu/cấu hình không đáp ứng yêu cầu chuẩn bị dữ liệu."""


def allocate_quota(full: dict, avail: dict, cap: int, minimum: int = 1) -> dict:
    """Train: đặt sàn cho lớp có mặt, chia phần còn lại theo counts gốc; không nhân bản."""
    avail = {c: int(n) for c, n in avail.items()}
    if any(n > 0 and avail.get(c, 0) <= 0 for c, n in full.items()):
        raise PrepError("Lớp có trong counts gốc nhưng không có ứng viên thật để lấy subset.")
    classes = sorted(c for c, n in full.items() if n > 0 and avail.get(c, 0) > 0)
    if cap <= 0 or minimum < 0 or not classes:
        raise PrepError("Quota cần ngân sách dương, minimum không âm và ít nhất một lớp.")
    q = {c: min(minimum, int(avail[c])) for c in classes}
    if sum(q.values()) > cap:
        raise PrepError(f"Ngân sách {cap} nhỏ hơn tổng mức tối thiểu {q}.")
    budget = min(cap, sum(avail[c] for c in classes)) - sum(q.values())
    open_ = [c for c in classes if avail[c] > q[c]]
    while budget and open_:
        shares = {c: budget * full[c] / sum(full[k] for k in open_) for c in open_}
        add = {c: min(int(shares[c]), avail[c] - q[c]) for c in open_}
        if not sum(add.values()):
            for c in sorted(open_, key=lambda k: (-(shares[k] % 1), k))[:budget]:
                add[c] = 1
        for c, n in add.items():
            q[c] += int(n)
        budget -= sum(add.values())
        open_ = [c for c in open_ if avail[c] > q[c]]
    return q


def natural_quota(counts: dict, size: int) -> dict:
    """Làm tròn theo phần dư lớn nhất, không chuyển quota lớp thiếu sang lớp khác."""
    counts = {c: int(n) for c, n in sorted(counts.items()) if n > 0}
    total = sum(counts.values())
    if not total or not 0 < size <= total:
        raise PrepError(f"Natural quota: size={size}, tổng số dòng={total} không hợp lệ.")
    q = {c: size * n // total for c, n in counts.items()}
    for c in sorted(counts, key=lambda k: (-(size * counts[k] % total), k))[:size - sum(q.values())]:
        q[c] += 1
    return q


def evaluation_plan(full: dict, avail: dict, base: int, maximum: int, minimum: int) -> tuple[dict, dict]:
    """Tăng ngân sách val/test để đủ support, vẫn giữ tỷ lệ lớp tự nhiên; thiếu mẫu thật thì báo lỗi."""
    counts = {c: int(n) for c, n in full.items() if n > 0}
    total = sum(counts.values())
    if not total or minimum < 1 or not 0 < base <= maximum:
        raise PrepError("Ngân sách đánh giá/mức support không hợp lệ.")
    required = max(math.ceil(minimum * total / n) for n in counts.values())
    size = min(total, max(base, required))
    if size > maximum:
        raise PrepError(f"Cần khoảng {size:,} mẫu để mỗi lớp đạt {minimum}; giới hạn {maximum:,}.")
    q = natural_quota(counts, size)
    if any(q[c] < minimum or q[c] > avail.get(c, 0) for c in counts):
        raise PrepError(f"Đánh giá thiếu mẫu thật: yêu cầu {q}, available={avail}, minimum={minimum}.")
    return q, {"base_budget": base, "effective_budget": size, "maximum_budget": maximum,
               "minimum_per_class": minimum, "expanded": size > base,
               "distribution": "natural_class", "quota": q}


def select_subset(df: pd.DataFrame, quota: dict) -> np.ndarray:
    """Hash bottom-k trong từng lớp: mẫu ngẫu nhiên đều, tái lập theo sel_hash."""
    keep = []
    for c, size in sorted(quota.items()):
        part = df[df["y"] == c]
        if size > len(part):
            raise PrepError(f"Lớp {c}: quota {size} > ứng viên {len(part)}.")
        keep.extend(part.nsmallest(size, "sel_hash").index.tolist())
    return np.sort(np.asarray(keep, dtype=np.int64))
