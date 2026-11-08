"""Pipeline dữ liệu multidataset_v1: 3 client × 3 lớp (docs/ke_hoach_code_fl_3_client.md).

Thứ tự: adapter -> kiểm tra nhãn/chất lượng -> chia train/validation/test theo nhóm -> lấy subset theo
quota lớp (hash seed 42) -> 8 cột liên tục + 6 cột cố định -> log1p -> AFN theo protocol (thống kê
train ba client, hỗ trợ missing) -> DAS (CRA + IDF, pooled) -> class weight -> artifacts.

Không sinh mẫu (CTA/DPCA), không TEC/MTB/NDS/JAA/DRA/LIS trong v1 (kế hoạch mục 2).
Mọi tham số fit chỉ dùng train; validation/test chỉ transform.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from fl_ddos import dataset_adapters as ad

CONTINUOUS = ["duration_s", "fwd_packets", "bwd_packets", "total_packets", "flow_packets_s",
              "fwd_packets_s", "bwd_packets_s", "bwd_packet_fraction"]
FIXED = ["proto_tcp", "proto_udp", "proto_icmp", "proto_other", "duration_missing", "duration_zero"]
KEEP_META = ["dataset_id", "capture_id", "row_id", "original_label", "timestamp"]
EPS = 1e-12
SPLITS = ("train", "val", "test")


class PrepError(RuntimeError):
    """Lỗi dữ liệu làm pipeline dừng mà không xuất artifact chính."""


def log(msg: str):
    print(f"[multidataset {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256_file(path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=_jsonable).encode()).hexdigest()


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, default=_jsonable)


def counter_rows(c: Counter, keys) -> list:
    return [{**dict(zip(keys, k if isinstance(k, tuple) else (k,))), "n": int(v)} for k, v in sorted(c.items())]


# ================================================================ đọc nguồn
def _class_counts(df: pd.DataFrame, by=("y", "original_label")) -> pd.DataFrame:
    return df.groupby(list(by), dropna=False).size().rename("n").reset_index()


def collect_tabular(dataset_id: str, cfg: dict, root: Path) -> dict:
    """CIC/UNSW đủ nhỏ để đọc toàn bộ dòng hợp lệ vào RAM."""
    src = cfg["sources"][dataset_id]
    d = root / src["dir"]
    issues, drops, checks = Counter(), Counter(), []
    if dataset_id == "cicddos2019":
        tr_files, te_files = sorted(d.glob(src["train_glob"])), sorted(d.glob(src["test_glob"]))
        if not tr_files or not te_files:
            raise PrepError(f"CIC: không tìm thấy {d / src['train_glob']} hoặc {d / src['test_glob']}")
        if src.get("expected_files") and len(tr_files) + len(te_files) != src["expected_files"]:
            raise PrepError(f"CIC: có {len(tr_files) + len(te_files)} file, cấu hình chờ {src['expected_files']}")
        cols = ["Flow Duration", "Total Fwd Packets", "Total Backward Packets", "Flow Packets/s"]
        checks.append(ad.cic_unit_check(pd.concat([pd.read_parquet(f, columns=cols) for f in tr_files])))
        if checks[-1]["passed"] is False:
            raise PrepError(f"CIC: Flow Duration không khớp đơn vị µs: {checks[-1]}")
        pools = {}
        for name, files in (("pool", tr_files), ("test", te_files)):
            parts = [b for f in files for b in ad.iter_canonical_batches(dataset_id, f, 1_000_000, cfg, issues, drops)]
            pools[name] = pd.concat(parts, ignore_index=True)
        files = {"pool": [f.name for f in tr_files], "test": [f.name for f in te_files]}
    elif dataset_id == "unsw_nb15":
        fs = src["files"]
        tr, te = d / fs["train"]["name"], d / fs["test"]["name"]
        for f in (tr, te):
            if not f.exists():
                raise PrepError(f"UNSW: thiếu {f}. Chạy prepare/download_datasets.py trước.")
        pools = {}
        for name, f, split, exp in (("pool", tr, "train", fs["train"]["rows"]), ("test", te, "test", fs["test"]["rows"])):
            raw = ad.read_unsw_csv(f)
            checks.append({"check": f"unsw_rows_{split}", "passed": len(raw) == exp, "n": len(raw), "expected": exp})
            if len(raw) != exp:
                raise PrepError(f"UNSW {f.name}: {len(raw)} dòng, mô tả chính thức là {exp}")
            pk = (raw["spkts"] + raw["dpkts"]).astype(float)
            ok = (raw["dur"] > 0) & (raw["rate"] > 0) if "rate" in raw else pd.Series(False, index=raw.index)
            if ok.sum() > 10:
                q = np.quantile(((pk - 1) / raw["dur"] / raw["rate"])[ok], [0.01, 0.5, 0.99])
                checks.append({"check": f"unsw_dur_seconds_{split}", "passed": None, "info":
                               "(spkts+dpkts-1)/dur / rate, chỉ để ghi nhận", "ratio_q01_q50_q99": q.tolist()})
            pools[name] = pd.concat(list(ad.iter_canonical_batches(dataset_id, f, 1_000_000, cfg, issues, drops,
                                                                     split=split)), ignore_index=True)
        files = {"pool": [tr.name], "test": [te.name]}
    else:
        raise ValueError(dataset_id)
    counts = {k: _class_counts(v) for k, v in pools.items()}
    return {"dataset_id": dataset_id, "pools": pools, "counts": counts, "issues": issues, "drops": drops,
            "checks": checks, "files": files}


def _reservoir_add(res: dict, frame: pd.DataFrame, cap: int):
    """Giữ `cap` dòng có sel_hash nhỏ nhất cho mỗi lớp (bottom-k = mẫu ngẫu nhiên đều, tái lập)."""
    for c, g in frame[frame["y"] >= 0].groupby("y"):
        cur = res.get(c)
        if cur is not None and len(cur) >= cap:
            g = g[g["sel_hash"] < cur["sel_hash"].max()]
            if g.empty:
                continue
        merged = g if cur is None else pd.concat([cur, g], ignore_index=True)
        res[c] = merged.nsmallest(cap, "sel_hash") if len(merged) > cap else merged


def collect_iot(cfg: dict, root: Path, archive: Path | None = None) -> dict:
    """Đọc archive IoT-23 theo luồng; cache Parquet reservoir + counts theo từng capture."""
    src = cfg["sources"]["iot23"]
    archive = Path(archive or root / src["dir"] / src["archive"])
    R = int(cfg["split"]["iot_reservoir_per_capture_class"])
    cache = root / cfg["paths"]["cache"] / "iot23" / f"{cfg['parser_version']}_seed{cfg['prep_seed']}_r{R}"
    cache.mkdir(parents=True, exist_ok=True)
    index_file = cache / "_complete.json"

    def capture_ok(cap):
        meta_f, pq = cache / f"{cap}.json", cache / f"{cap}.parquet"
        if not (meta_f.exists() and pq.exists()):
            return None
        m = read_json(meta_f)
        if m.get("parser_version") != cfg["parser_version"] or m.get("sha256") != sha256_file(pq):
            raise PrepError(f"IoT cache {pq} sai checksum/phiên bản parser. Xóa thư mục {cache} rồi chạy lại.")
        return m

    if index_file.exists():
        index = read_json(index_file)
        metas = {c: capture_ok(c) for c in index["captures"]}
        if any(v is None for v in metas.values()):
            raise PrepError(f"IoT cache thiếu capture so với {index_file}. Xóa {cache} rồi chạy lại.")
        log(f"IoT: dùng lại cache {len(metas)} capture tại {cache}")
    else:
        if not archive.exists():
            raise PrepError(f"IoT: thiếu {archive}. Chạy prepare/download_datasets.py trước.")
        done = {p.stem for p in cache.glob("*.json") if not p.name.startswith("_") and capture_ok(p.stem)}
        log(f"IoT: đọc {archive.name} theo luồng ({len(done)} capture đã có cache, vẫn phải giải nén tuần tự)")
        issues, drops, state = Counter(), Counter(), {}

        def on_start(cap, member):
            state.update(cap=cap, res={}, counts=Counter(), n=0, t0=time.time(),
                         issues0=Counter(issues), drops0=Counter(drops), size=member.size)
            log(f"IoT: bắt đầu {cap} ({member.size / 2**20:,.0f} MiB)")

        for cap, frame in ad.iter_iot_archive(archive, cfg, issues, drops, skip=frozenset(done),
                                              chunksize=int(cfg["split"]["iot_batch_rows"]), on_capture_start=on_start):
            if frame is not None:
                _reservoir_add(state["res"], frame, R)
                for (yv, lab), n in frame.groupby(["y", "original_label"]).size().items():
                    state["counts"][(int(yv), lab)] += int(n)
                state["n"] += len(frame)
                continue
            res = [state["res"][c] for c in sorted(state["res"])]
            out = pd.concat(res, ignore_index=True) if res else pd.DataFrame(columns=ad.META + ad.BASE + ["flow_uid"])
            pq = cache / f"{cap}.parquet"
            out.to_parquet(pq, index=False)
            m = {"capture_id": cap, "parser_version": cfg["parser_version"], "n_valid_rows": state["n"],
                 "member_bytes": state["size"], "counts": counter_rows(state["counts"], ("y", "original_label")),
                 "issues": counter_rows(issues - state["issues0"], ("dataset_id", "issue")),
                 "drops": counter_rows(drops - state["drops0"], ("reason", "original_label")),
                 "reservoir_rows": len(out), "sha256": sha256_file(pq)}
            dump_json(m, cache / f"{cap}.json")
            done.add(cap)
            log(f"IoT: xong {cap}: {state['n']:,} dòng hợp lệ, giữ {len(out):,}, {time.time() - state['t0']:.0f}s")
        st = archive.stat()
        dump_json({"captures": sorted(done), "archive": archive.name, "archive_bytes": st.st_size,
                   "parser_version": cfg["parser_version"], "reservoir": R}, index_file)
        metas = {c: capture_ok(c) for c in sorted(done)}
    if not metas:
        raise PrepError("IoT: archive không có conn.log.labeled nào")
    cand = pd.concat([pd.read_parquet(cache / f"{c}.parquet") for c in sorted(metas)], ignore_index=True)
    counts = pd.DataFrame([{"capture_id": c, **r} for c, m in metas.items() for r in m["counts"]])
    issues, drops = Counter(), Counter()
    for m in metas.values():
        for r in m["issues"]:
            issues[(r["dataset_id"], r["issue"])] += r["n"]
        for r in m["drops"]:
            drops[(r["reason"], r["original_label"])] += r["n"]
    return {"dataset_id": "iot23", "candidates": cand, "capture_counts": counts, "issues": issues, "drops": drops,
            "checks": [], "files": {"archive": archive.name, "captures": sorted(metas)}, "cache": str(cache)}


# ================================================================ chia tập
def group_kfold(y, groups, n_folds, seed):
    sgkf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    fold = np.full(len(y), -1, dtype=np.int64)
    for k, (_, te) in enumerate(sgkf.split(np.zeros((len(y), 1)), y, groups)):
        fold[te] = k
    return fold


def split_train_val(pool: pd.DataFrame, n_folds: int, seed: int, dataset_id: str) -> tuple[np.ndarray, dict]:
    """5-fold theo nhóm fingerprint, phân tầng nhãn; chọn fold validation đầu tiên có đủ lớp của nguồn."""
    y, g = pool["y"].values, pool["fingerprint"].values
    fold = group_kfold(y, g, n_folds, seed)
    need = set(np.unique(y))
    for k in range(n_folds):
        val = fold == k
        if set(np.unique(y[val])) == need and set(np.unique(y[~val])) == need:
            return np.where(val, "val", "train"), {"val_fold": k, "n_folds": n_folds, "seed": seed}
    raise PrepError(f"{dataset_id}: không có fold validation nào chứa đủ lớp {sorted(need)} ở cả train và val")


def split_iot(cand: pd.DataFrame, n_folds: int, seed: int) -> tuple[np.ndarray, dict]:
    """StratifiedGroupKFold theo capture trên reservoir; chọn cặp (test, val) đầu tiên đủ ba lớp mỗi phía."""
    y, g = cand["y"].values, cand["capture_id"].values
    if len(np.unique(g)) < n_folds:
        raise PrepError(f"IoT: chỉ có {len(np.unique(g))} capture, cần ≥ {n_folds} cho group k-fold")
    fold = group_kfold(y, g, n_folds, seed)
    need = set(range(len(ad.CLASSES)))
    for t in range(n_folds):
        for v in range(n_folds):
            if v == t:
                continue
            s = np.where(fold == t, "test", np.where(fold == v, "val", "train"))
            if all(set(np.unique(y[s == name])) >= need for name in SPLITS):
                return s, {"test_fold": t, "val_fold": v, "n_folds": n_folds, "seed": seed}
    tab = pd.crosstab(cand["capture_id"], cand["y"]).to_string()
    raise PrepError(f"IoT: không có cặp fold test/val nào đủ ba lớp ở train/val/test.\nCapture × lớp:\n{tab}")


def allocate_quota(full: dict, avail: dict, cap: int) -> dict:
    """Quota lớp tỷ lệ với số dòng gốc của split (water-filling khi một lớp không đủ ứng viên).
    Giữ ≥ 1 mẫu cho lớp có mặt nếu ngân sách cho phép; không nhân bản."""
    classes = [c for c in full if full[c] > 0 and avail.get(c, 0) > 0]
    if sum(avail[c] for c in classes) <= cap:
        return {c: int(avail[c]) for c in classes}
    q = {c: 0 for c in classes}
    if cap >= len(classes):
        q = {c: 1 for c in classes}
    budget, open_ = cap - sum(q.values()), [c for c in classes if avail[c] > q[c]]
    while budget > 0 and open_:
        tot = sum(full[c] for c in open_)
        share = {c: budget * full[c] / tot for c in open_}
        add = {c: min(int(np.floor(share[c])), avail[c] - q[c]) for c in open_}
        if sum(add.values()) == 0:  # phần dư: chia theo phần lẻ lớn nhất, tie theo chỉ số lớp
            for c in sorted(open_, key=lambda c: (-(share[c] - np.floor(share[c])), c))[:budget]:
                add[c] = 1
        for c in open_:
            q[c] += add[c]
        budget = cap - sum(q.values())
        open_ = [c for c in open_ if avail[c] > q[c]]
    return q


def select_subset(df: pd.DataFrame, quota: dict) -> np.ndarray:
    """Chỉ số dòng được chọn: mỗi lớp lấy `quota` dòng có sel_hash nhỏ nhất."""
    keep = []
    for c, k in quota.items():
        idx = np.where(df["y"].values == c)[0]
        if k:
            order = np.argsort(df["sel_hash"].values[idx], kind="stable")[:k]
            keep.append(idx[order])
    return np.sort(np.concatenate(keep)) if keep else np.array([], dtype=np.int64)


# ================================================================ đặc trưng
def derive(frame: pd.DataFrame) -> pd.DataFrame:
    """8 cột liên tục (rate = missing khi duration không dương/thiếu) + 6 cột cố định 0/1."""
    d = frame["duration_s"].values.astype(np.float64)
    f, b = frame["fwd_packets"].values.astype(np.float64), frame["bwd_packets"].values.astype(np.float64)
    tot = f + b
    pos = np.isfinite(d) & (d > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = lambda num: np.where(pos, num / np.where(pos, d, 1.0), np.nan)  # noqa: E731
        out = pd.DataFrame({
            "duration_s": d, "fwd_packets": f, "bwd_packets": b, "total_packets": tot,
            "flow_packets_s": rate(tot), "fwd_packets_s": rate(f), "bwd_packets_s": rate(b),
            "bwd_packet_fraction": np.where(tot > 0, b / np.where(tot > 0, tot, 1.0), np.nan),
        }, index=frame.index)
    pg = frame["protocol_group"].astype(str).values
    for g in ad.PROTO_GROUPS:
        out[f"proto_{g}"] = (pg == g).astype(np.float32)
    out["duration_missing"] = (~np.isfinite(d)).astype(np.float32)
    out["duration_zero"] = (np.isfinite(d) & (d == 0)).astype(np.float32)
    return out


def log1p_valid(x: np.ndarray) -> np.ndarray:
    """log1p cho giá trị hữu hạn không âm; còn lại -> NaN (missing)."""
    x = np.asarray(x, dtype=np.float64)
    ok = np.isfinite(x) & (x >= 0)
    out = np.full_like(x, np.nan)
    out[ok] = np.log1p(x[ok])
    return out


def afn_stats(x: np.ndarray, groups: np.ndarray) -> dict:
    """Tại client: số quan sát hợp lệ, tổng, tổng bình phương theo nhóm protocol và cột."""
    out = {}
    for g in np.unique(groups):
        xg = x[groups == g]
        v = np.isfinite(xg)
        z = np.where(v, xg, 0.0)
        out[str(g)] = {"n_rows": int(len(xg)), "n_valid": v.sum(0).astype(np.int64),
                       "sum": z.sum(0), "sumsq": (z ** 2).sum(0)}
    return out


def aggregate_afn(stats: list, columns: list) -> dict:
    """Tại server: mean/std theo nhóm và '__all__' (cho nhóm chưa gặp); std = 0 -> scale = 1.
    Ô (nhóm, cột) không có quan sát dùng tham số global; cột không có quan sát train bị loại."""
    k = len(columns)
    acc = {}
    for st in stats:
        for g, s in st.items():
            for key in (g, "__all__"):
                a = acc.setdefault(key, {"n_rows": 0, "n_valid": np.zeros(k, np.int64), "sum": np.zeros(k),
                                         "sumsq": np.zeros(k)})
                a["n_rows"] += s["n_rows"]
                a["n_valid"] = a["n_valid"] + s["n_valid"]
                a["sum"] = a["sum"] + s["sum"]
                a["sumsq"] = a["sumsq"] + s["sumsq"]
    glob = acc["__all__"]
    usable = glob["n_valid"] > 0
    params = {}
    for g, a in acc.items():
        n = np.maximum(a["n_valid"], 1)
        mean = a["sum"] / n
        std = np.sqrt(np.maximum(a["sumsq"] / n - mean ** 2, 0.0))
        scale = np.where(std > 1e-9, std, 1.0)
        params[g] = {"n_rows": int(a["n_rows"]), "n_valid": a["n_valid"].tolist(), "mean": mean, "scale": scale,
                     "fallback_global": (a["n_valid"] == 0).tolist()}
    for g, p in params.items():
        fb = np.array(p["fallback_global"])
        p["mean"] = np.where(fb, params["__all__"]["mean"], p["mean"]).tolist()
        p["scale"] = np.where(fb, params["__all__"]["scale"], p["scale"]).tolist()
    return {"columns": columns, "usable": usable.tolist(), "groups": params}


def apply_afn(x: np.ndarray, groups: np.ndarray, afn: dict) -> np.ndarray:
    """z = (x − mean) / scale; missing được thay bằng mean nên thành 0."""
    out = np.empty_like(x, dtype=np.float64)
    gp = afn["groups"]
    for g in np.unique(groups):
        p = gp.get(str(g), gp["__all__"])
        m = groups == g
        z = (x[m] - np.asarray(p["mean"])) / np.asarray(p["scale"])
        out[m] = np.where(np.isfinite(z), z, 0.0)
    return out


def das_stats(x: np.ndarray, y: np.ndarray, n_classes: int) -> dict:
    onehot = np.eye(n_classes)[y]
    return {"n": len(x), "sx": x.sum(0), "sxx": x.T @ x, "sxy": x.T @ onehot, "sy": onehot.sum(0)}


def das_relevance(stats: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """CRA (Eq.7–8): TB qua lớp có phương sai > 0 của Cov(x, 1[y=c])² / (Var x · Var 1[y=c]).
    Trả (relevance, var_x, corr). Cột hằng có relevance = 0 (không chia cho 0)."""
    n = sum(s["n"] for s in stats)
    mx, my = sum(s["sx"] for s in stats) / n, sum(s["sy"] for s in stats) / n
    cov_xx = sum(s["sxx"] for s in stats) / n - np.outer(mx, mx)
    cov_xy = sum(s["sxy"] for s in stats) / n - np.outer(mx, my)
    var_x, var_y = np.maximum(np.diag(cov_xx), 0.0), my * (1 - my)
    live, ok = var_y > EPS, var_x > EPS
    rel = np.zeros(len(var_x))
    if live.any():
        rel[ok] = (cov_xy[ok][:, live] ** 2 / (var_x[ok, None] * var_y[None, live])).mean(1)
    sd = np.sqrt(np.where(ok, var_x, 1.0))
    corr = np.where(np.outer(ok, ok), cov_xx / np.outer(sd, sd), 0.0)
    return rel, var_x, corr


def das_select(stats: list, names: list, theta: float, gamma: float, max_k: int) -> tuple[list, pd.DataFrame]:
    """IDF (Eq.9): xét theo CRA giảm dần (hòa -> theo tên cột), bỏ cột có |corr| ≥ γ với cột đã chọn."""
    rel, var_x, corr = das_relevance(stats)
    order = sorted(range(len(names)), key=lambda i: (-rel[i], names[i]))
    chosen, rows = [], []
    for rank, i in enumerate(order, 1):
        status, reason = "dropped", ""
        if var_x[i] <= EPS:
            reason = "constant"
        elif rel[i] <= theta:
            reason = f"relevance<={theta}"
        elif len(chosen) >= max_k:
            reason = f"max_continuous={max_k}"
        else:
            red = next((p for p in chosen if abs(corr[i, p]) >= gamma), None)
            if red is not None:
                reason = f"redundant_with:{names[red]}(|r|={abs(corr[i, red]):.3f})"
            else:
                chosen.append(i)
                status = "selected"
        rows.append({"feature": names[i], "rank": rank, "relevance_pooled": float(rel[i]), "status": status,
                     "reason": reason})
    return [names[i] for i in chosen], pd.DataFrame(rows)


def class_weights(y: np.ndarray, n_classes: int, clip=(0.1, 10.0)) -> list:
    """Nghịch đảo tần suất lớp có mặt; TB weight lớp có mặt = 1; clip; lớp vắng weight = 0."""
    cnt = np.bincount(y, minlength=n_classes).astype(float)
    present = cnt > 0
    w = np.zeros(n_classes)
    w[present] = 1.0 / cnt[present]
    w[present] /= w[present].mean()
    w[present] = np.clip(w[present], *clip)
    return w.tolist()


# ================================================================ preprocessor (fit / transform)
def fit_preprocessor(train_frames: dict, cfg: dict, feature_set: str = "das") -> tuple[dict, pd.DataFrame]:
    """train_frames: {dataset_id: DataFrame canonical của train subset}. Trả (fitted, bảng DAS)."""
    raw = {k: derive(v) for k, v in train_frames.items()}
    logx = {k: log1p_valid(r[CONTINUOUS].values) for k, r in raw.items()}
    groups = {k: v["protocol_group"].astype(str).values for k, v in train_frames.items()}
    afn = aggregate_afn([afn_stats(logx[k], groups[k]) for k in train_frames], CONTINUOUS)
    usable = [c for c, u in zip(CONTINUOUS, afn["usable"]) if u]
    unusable = [c for c in CONTINUOUS if c not in usable]
    ui = [CONTINUOUS.index(c) for c in usable]
    z = {k: apply_afn(logx[k], groups[k], afn)[:, ui] for k in train_frames}
    ys = {k: v["y"].values.astype(np.int64) for k, v in train_frames.items()}
    nc = len(ad.CLASSES)
    d = cfg["das"]
    stats = {k: das_stats(z[k], ys[k], nc) for k in train_frames}
    selected, table = das_select(list(stats.values()), usable, d["theta"], d["gamma"], d["max_continuous"])
    for k, s in stats.items():
        rel, _, _ = das_relevance([s])
        table[f"relevance_{k}"] = table["feature"].map(dict(zip(usable, rel.tolist())))
    for c in unusable:
        table = pd.concat([table, pd.DataFrame([{"feature": c, "status": "dropped", "reason": "no_valid_train_obs"}])],
                          ignore_index=True)
    if feature_set == "all":  # đối chứng: mọi cột liên tục hợp lệ (không hằng, có quan sát), theo thứ hạng CRA
        valid = table[~table["reason"].fillna("").isin(["constant", "no_valid_train_obs"])]
        selected = valid.sort_values("rank")["feature"].tolist()
        table["status_all"] = np.where(table["feature"].isin(selected), "used", "dropped")
    elif feature_set != "das":
        raise ValueError(f"feature_set lạ: {feature_set}")
    if not selected:
        raise PrepError("DAS không chọn được cột liên tục nào (xem feature_selection.csv); không tự hạ ngưỡng.")
    fitted = {"pipeline": cfg["pipeline"], "schema_version": cfg["schema_version"], "classes": ad.CLASSES,
              "continuous_candidates": CONTINUOUS, "continuous_usable": usable, "continuous_selected": selected,
              "fixed": FIXED, "features": selected + FIXED, "feature_set": feature_set,
              "transform": "log1p(finite, >=0) -> AFN theo protocol_group (missing -> 0)",
              "afn": afn, "das": {**d, "pooled": True}, "protocol_groups": ad.PROTO_GROUPS}
    return fitted, table


def transform_canonical(frame: pd.DataFrame, fitted: dict) -> pd.DataFrame:
    """Raw canonical -> đầu vào mô hình (float32, đúng thứ tự features). Không cập nhật tham số."""
    raw = derive(frame)
    x = apply_afn(log1p_valid(raw[CONTINUOUS].values), frame["protocol_group"].astype(str).values, fitted["afn"])
    cont = pd.DataFrame(x, columns=CONTINUOUS, index=frame.index)[fitted["continuous_selected"]]
    out = pd.concat([cont, raw[FIXED]], axis=1)[fitted["features"]].astype(np.float32)
    if not np.isfinite(out.values).all():
        raise PrepError("Đầu vào sau transform có NaN/Inf")
    return out


def model_frame(frame: pd.DataFrame, fitted: dict) -> pd.DataFrame:
    x = transform_canonical(frame, fitted).reset_index(drop=True)
    meta = frame[KEEP_META].reset_index(drop=True)
    y = frame["y"].values.astype(np.int64)
    return pd.concat([x, meta], axis=1).assign(y=y, binary=(y != 0).astype(np.int64),
                                               label=np.array(ad.CLASSES)[y])


# ================================================================ điều phối
def _split_counts(df: pd.DataFrame, split_col="split") -> dict:
    out = {}
    for s, g in df.groupby(split_col):
        out[s] = {ad.CLASSES[int(c)]: int(n) for c, n in g["y"].value_counts().sort_index().items()}
    return out


def build_splits(sources: dict, cfg: dict) -> dict:
    """Gán train/val/test cho mọi dòng ứng viên; trả {dataset_id: {"rows": DataFrame, "info", "full_counts"}}."""
    nf, seed = int(cfg["split"]["n_folds"]), int(cfg["split"]["group_kfold_seed"])
    out = {}
    for ds, s in sources.items():
        if ds == "iot23":
            cand = s["candidates"].copy()
            split, info = split_iot(cand, nf, seed)
            cand["split"], cand["group"] = split, cand["capture_id"]
            cap_split = cand.groupby("capture_id")["split"].first()
            cc = s["capture_counts"].assign(split=lambda d: d["capture_id"].map(cap_split))
            unassigned = cc["split"].isna()
            if unassigned.any():  # capture có dòng hợp lệ nhưng không lớp nào vào reservoir -> không xảy ra
                raise PrepError(f"IoT: capture không có split: {sorted(cc.loc[unassigned, 'capture_id'].unique())}")
            full = {sp: g.groupby("y")["n"].sum().to_dict() for sp, g in cc[cc["y"] >= 0].groupby("split")}
            info["captures"] = {sp: sorted(cap_split[cap_split == sp].index) for sp in SPLITS}
            rows = cand
        else:
            pool, test = s["pools"]["pool"].copy(), s["pools"]["test"].copy()
            pool = pool[pool["y"] >= 0].reset_index(drop=True)
            test = test[test["y"] >= 0].reset_index(drop=True)
            pool["split"], info = split_train_val(pool, nf, seed, ds)
            test["split"] = "test"
            rows = pd.concat([pool, test], ignore_index=True)
            rows["group"] = rows["fingerprint"].astype(str)
            full = {sp: g["y"].value_counts().to_dict() for sp, g in rows.groupby("split")}
        out[ds] = {"rows": rows, "info": info, "full_counts": full}
    return out


def choose_subsets(splits: dict, caps: dict) -> dict:
    for ds, s in splits.items():
        rows = s["rows"]
        sel = np.zeros(len(rows), dtype=bool)
        s["quota"] = {}
        for sp in SPLITS:
            idx = np.where(rows["split"].values == sp)[0]
            part = rows.iloc[idx]
            avail = part["y"].value_counts().to_dict()
            q = allocate_quota({int(k): int(v) for k, v in s["full_counts"].get(sp, {}).items()},
                               {int(k): int(v) for k, v in avail.items()}, int(caps[sp]))
            sel[idx[select_subset(part.reset_index(drop=True), q)]] = True
            s["quota"][sp] = {ad.CLASSES[c]: int(n) for c, n in q.items()}
        rows["selected"] = sel
    return splits


def independence_checks(splits: dict) -> dict:
    out = {}
    for ds, s in splits.items():
        r = s["rows"]
        gs = {sp: set(r.loc[r["split"] == sp, "group"]) for sp in SPLITS}
        dup_ids = int(r["row_id"].duplicated().sum())
        chk = {"train_val_group_overlap": len(gs["train"] & gs["val"]), "duplicate_row_id": dup_ids}
        if ds == "iot23":
            chk["capture_in_multiple_splits"] = len((gs["train"] & gs["val"]) | (gs["train"] & gs["test"]) |
                                                    (gs["val"] & gs["test"]))
            if "flow_uid" in r:
                chk["duplicate_flow_uid_in_reservoir"] = int(r.duplicated(["capture_id", "flow_uid"]).sum())
        else:
            fp = {sp: set(r.loc[r["split"] == sp, "fingerprint"]) for sp in SPLITS}
            chk["train_vectors_also_in_test"] = len(fp["train"] & fp["test"])
            chk["val_vectors_also_in_test"] = len(fp["val"] & fp["test"])
            chk["note"] = "Vector trùng với test chính thức chỉ được báo cáo, không tự chứng minh rò rỉ nhãn."
        bad = chk["train_val_group_overlap"] or dup_ids or chk.get("capture_in_multiple_splits", 0)
        if bad:
            raise PrepError(f"{ds}: vi phạm ràng buộc split: {chk}")
        for sp in SPLITS:
            if not ((r["split"] == sp) & r["selected"]).any():
                raise PrepError(f"{ds}: split '{sp}' rỗng sau khi lấy subset")
        out[ds] = chk
    return out


def load_sources(cfg: dict, root: Path, only=None) -> dict:
    sources = {}
    for c in cfg["clients"]:
        ds = c["dataset_id"]
        if only and ds not in only:
            continue
        log(f"Đọc nguồn {ds}")
        sources[ds] = collect_iot(cfg, root) if ds == "iot23" else collect_tabular(ds, cfg, root)
    return sources


def prepare_multidataset(config: dict, profile: str, root: Path | str = ".", out_dir=None,
                         feature_set: str = "das", sources: dict | None = None) -> dict:
    """Chạy toàn bộ pipeline cho một profile (smoke | main); trả tóm tắt. Ghi artifacts vào out_dir."""
    cfg, root = config, Path(root)
    caps = cfg["profiles"][profile]
    out = Path(out_dir or root / cfg["paths"]["out"] / (profile + ("" if feature_set == "das" else f"_{feature_set}")))
    sources = sources or load_sources(cfg, root)

    issues = Counter()
    for s in sources.values():
        issues.update(s["issues"])
    quality = {"profile": profile, "caps": caps, "feature_set": feature_set,
               "issues": counter_rows(issues, ("dataset_id", "issue")),
               "drops": {ds: counter_rows(s["drops"], ("reason", "original_label")) for ds, s in sources.items()},
               "compatibility_checks": {ds: s["checks"] for ds, s in sources.items()}}
    if issues:
        dump_json(quality, out / "quality_report.json")
        raise PrepError(f"Còn {len(issues)} loại nhãn lạ/mâu thuẫn chưa có quy tắc -> không xuất artifacts. "
                        f"Xem {out / 'quality_report.json'}: {list(issues.items())[:5]}")

    log("Chia train/validation/test theo nhóm")
    splits = choose_subsets(build_splits(sources, cfg), {"train": caps["train"], "val": caps["val"],
                                                          "test": caps["test"]})
    quality["independence"] = independence_checks(splits)
    sub = {ds: {sp: s["rows"][(s["rows"]["split"] == sp) & s["rows"]["selected"]].reset_index(drop=True)
                for sp in SPLITS} for ds, s in splits.items()}
    gtrain = set().union(*[set(sub[ds]["train"]["y"]) for ds in sub])
    if gtrain != set(range(len(ad.CLASSES))):
        raise PrepError(f"Train gộp của ba client thiếu lớp: có {sorted(gtrain)}")

    log("Fit log1p + AFN theo protocol và DAS trên train ba client")
    fitted, table = fit_preprocessor({ds: sub[ds]["train"] for ds in sub}, cfg, feature_set)
    log(f"Đặc trưng cuối ({len(fitted['features'])}): {fitted['features']}")

    (out / "multidataset").mkdir(parents=True, exist_ok=True)
    (out / "test").mkdir(parents=True, exist_ok=True)
    weights, manifest_clients = {}, []
    for c in cfg["clients"]:
        ds, k = c["dataset_id"], c["client"]
        tr, va, te = (model_frame(sub[ds][sp], fitted) for sp in SPLITS)
        tr.to_parquet(out / "multidataset" / f"client_{k}.parquet", index=False)
        va.to_parquet(out / "multidataset" / f"val_client_{k}.parquet", index=False)
        te.to_parquet(out / "test" / f"{ds}.parquet", index=False)
        weights[f"client_{k}"] = class_weights(tr["y"].values, len(ad.CLASSES), tuple(cfg["class_weight_clip"]))
        manifest_clients.append({**c, "n_train": len(tr), "n_val": len(va), "n_test": len(te),
                                 "train_file": f"multidataset/client_{k}.parquet",
                                 "val_file": f"multidataset/val_client_{k}.parquet", "test_file": f"test/{ds}.parquet"})
    dump_json({**weights, "rule": "inverse frequency, mean(present)=1, clip " + str(cfg["class_weight_clip"]) +
               ", absent=0"}, out / "multidataset" / "class_weights.json")

    smf = pd.concat([s["rows"][["dataset_id", "row_id", "capture_id", "group", "split", "selected", "y"]]
                     .assign(sel_hash=s["rows"]["sel_hash"].astype("uint64")) for s in splits.values()],
                    ignore_index=True)
    smf.to_parquet(out / "split_manifest.parquet", index=False)
    split_hash = sha256_json(smf.loc[smf["selected"], ["dataset_id", "row_id", "split"]]
                             .sort_values(["dataset_id", "row_id"]).values.tolist())
    prep = {k: v for k, v in fitted.items()}
    prep_hash = sha256_json(prep)
    schema_hash = sha256_json({"features": fitted["features"], "classes": fitted["classes"],
                               "schema_version": fitted["schema_version"]})
    hashes = {"schema": schema_hash, "preprocessor": prep_hash, "split": split_hash}
    dump_json({**prep, "hashes": hashes, "label_map": cfg["label_map"], "prep_seed": cfg["prep_seed"]},
              out / "prep_params.json")
    table.to_csv(out / "feature_selection.csv", index=False)
    dump_json({"pipeline": cfg["pipeline"], "scenario": cfg["scenario"], "schema_version": cfg["schema_version"],
               "classes": ad.CLASSES, "features": fitted["features"],
               "continuous_selected": fitted["continuous_selected"], "fixed": FIXED, "feature_set": feature_set,
               "profile": profile, "hashes": hashes, "n_clients": len(cfg["clients"])}, out / "features.json")

    quality.update({
        "full_counts": {ds: {sp: {ad.CLASSES[int(c)]: int(n) for c, n in v.items()} for sp, v in s["full_counts"].items()}
                        for ds, s in splits.items()},
        "candidate_counts": {ds: _split_counts(s["rows"]) for ds, s in splits.items()},
        "used_counts": {ds: {sp: {ad.CLASSES[int(c)]: int(n) for c, n in sub[ds][sp]["y"].value_counts()
                                  .sort_index().items()} for sp in SPLITS} for ds in sub},
        "quota": {ds: s["quota"] for ds, s in splits.items()},
        "missing_duration": {ds: {sp: float(sub[ds][sp]["duration_s"].isna().mean()) for sp in SPLITS} for ds in sub},
        "note": "Subset theo quota lớp; không phải toàn bộ benchmark. Không sinh mẫu trong v1.",
    })
    dump_json(quality, out / "quality_report.json")
    raw_manifest = {}
    for ds in sources:
        mf = root / cfg["sources"][ds]["dir"] / "download_manifest.json"
        raw_manifest[ds] = read_json(mf) if mf.exists() else None
    dump_json({"pipeline": cfg["pipeline"], "clients": manifest_clients,
               "sources": {ds: {"files": s["files"], "download_manifest": raw_manifest[ds],
                                "split": splits[ds]["info"], "cache": s.get("cache"),
                                "config": cfg["sources"][ds]} for ds, s in sources.items()},
               "conventions": {"cicddos2019": cfg["sources"]["cicddos2019"].get("note", ""),
                               "unsw_nb15": "test = testing-set chính thức; train/val = 5-fold nhóm fingerprint",
                               "iot23": "StratifiedGroupKFold 5-fold theo capture trên reservoir"},
               "hashes": hashes, "created": time.strftime("%Y-%m-%d %H:%M:%S")}, out / "dataset_manifest.json")
    log(f"Xong -> {out}")
    return {"out": str(out), "features": fitted["features"], "hashes": hashes, "clients": manifest_clients,
            "used_counts": quality["used_counts"]}


def load_config(path) -> dict:
    return read_json(path)
