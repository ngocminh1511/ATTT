"""Pipeline dữ liệu multidataset_v1: 2 client (CIC-DDoS2019, UNSW-NB15) × 3 lớp.

Thứ tự: adapter -> kiểm tra nhãn/chất lượng -> chia train/validation/test theo nhóm -> lấy subset theo
quota lớp (hash seed 42) -> 17 cột liên tục + 6 cột cố định -> log1p -> AFN theo protocol (thống kê
train hai client, hỗ trợ missing) -> DAS (CRA + IDF, pooled) -> class weight -> artifacts.

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
from fl_ddos.multidataset_sampling import POLICY_VERSION, PrepError, allocate_quota, evaluation_plan, select_subset

CONTINUOUS = ["duration_s", "fwd_packets", "bwd_packets", "total_packets", "flow_packets_s",
              "fwd_packets_s", "bwd_packets_s", "bwd_packet_fraction",
              "fwd_bytes", "bwd_bytes", "total_bytes", "flow_bytes_s", "fwd_packet_size_mean",
              "bwd_packet_size_mean", "bwd_byte_fraction", "fwd_iat_mean_s", "bwd_iat_mean_s"]
FIXED = ["proto_tcp", "proto_udp", "proto_icmp", "proto_other", "duration_missing", "duration_zero"]
KEEP_META = ["dataset_id", "capture_id", "row_id", "original_label", "timestamp"]
EPS = 1e-12
SPLITS = ("train", "val", "test")


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


# ================================================================ đặc trưng
def derive(frame: pd.DataFrame) -> pd.DataFrame:
    """17 cột liên tục (rate = missing khi duration không dương/thiếu; tỷ lệ/kích thước gói = missing khi
    mẫu số bằng 0) + 6 cột cố định 0/1."""
    d = frame["duration_s"].values.astype(np.float64)
    f, b = frame["fwd_packets"].values.astype(np.float64), frame["bwd_packets"].values.astype(np.float64)
    fb, bb = frame["fwd_bytes"].values.astype(np.float64), frame["bwd_bytes"].values.astype(np.float64)
    tot, totb = f + b, fb + bb
    pos = np.isfinite(d) & (d > 0)

    def ratio(num, den):
        ok = np.isfinite(num) & np.isfinite(den) & (den > 0)
        return np.where(ok, num / np.where(ok, den, 1.0), np.nan)

    with np.errstate(divide="ignore", invalid="ignore"):
        rate = lambda num: np.where(pos, num / np.where(pos, d, 1.0), np.nan)  # noqa: E731
        out = pd.DataFrame({
            "duration_s": d, "fwd_packets": f, "bwd_packets": b, "total_packets": tot,
            "flow_packets_s": rate(tot), "fwd_packets_s": rate(f), "bwd_packets_s": rate(b),
            "bwd_packet_fraction": ratio(b, tot),
            "fwd_bytes": fb, "bwd_bytes": bb, "total_bytes": totb, "flow_bytes_s": rate(totb),
            "fwd_packet_size_mean": ratio(fb, f), "bwd_packet_size_mean": ratio(bb, b),
            "bwd_byte_fraction": ratio(bb, totb),
            "fwd_iat_mean_s": frame["fwd_iat_mean_s"].values.astype(np.float64),
            "bwd_iat_mean_s": frame["bwd_iat_mean_s"].values.astype(np.float64),
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
        s["quota"], s["sampling"] = {}, {}
        for sp in SPLITS:
            idx = np.where(rows["split"].values == sp)[0]
            part = rows.iloc[idx]
            avail = part["y"].value_counts().to_dict()
            full = {int(k): int(v) for k, v in s["full_counts"].get(sp, {}).items() if v > 0}
            if sp == "train":
                minimum = int(caps.get("train_min_per_class", 1))
                q = allocate_quota(full, avail, int(caps[sp]), minimum)
                s["sampling"][sp] = {"base_budget": caps[sp], "effective_budget": sum(q.values()),
                                      "minimum_per_class": minimum, "distribution": "floor_then_proportional",
                                      "floor_shortfall": {ad.CLASSES[c]: {"available": avail.get(c, 0),
                                                                          "requested": minimum}
                                                          for c in full if avail.get(c, 0) < minimum}, "quota": q}
            else:
                q, s["sampling"][sp] = evaluation_plan(
                    full, avail, int(caps[sp]), int(caps.get("eval_max_samples", {}).get(sp, caps[sp])),
                    int(caps.get("eval_min_per_class", {}).get(sp, 1)))
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
        fp = {sp: set(r.loc[r["split"] == sp, "fingerprint"]) for sp in SPLITS}
        chk["train_vectors_also_in_test"] = len(fp["train"] & fp["test"])
        chk["val_vectors_also_in_test"] = len(fp["val"] & fp["test"])
        chk["note"] = "Vector trùng với test chính thức chỉ được báo cáo, không tự chứng minh rò rỉ nhãn."
        if chk["train_val_group_overlap"] or dup_ids:
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
        sources[ds] = collect_tabular(ds, cfg, root)
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
    try:
        splits = choose_subsets(build_splits(sources, cfg), caps)
        quality["independence"] = independence_checks(splits)
    except PrepError as e:
        quality.update({"status": "failed", "sampling_policy": POLICY_VERSION, "error": str(e)})
        dump_json(quality, out / "quality_report.json")
        raise
    sub = {ds: {sp: s["rows"][(s["rows"]["split"] == sp) & s["rows"]["selected"]].reset_index(drop=True)
                for sp in SPLITS} for ds, s in splits.items()}
    gtrain = set().union(*[set(sub[ds]["train"]["y"]) for ds in sub])
    if gtrain != set(range(len(ad.CLASSES))):
        raise PrepError(f"Train gộp của các client thiếu lớp: có {sorted(gtrain)}")

    log("Fit log1p + AFN theo protocol và DAS trên train các client")
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
                "profile": profile, "sampling_policy": POLICY_VERSION,
                "hashes": hashes, "n_clients": len(cfg["clients"])}, out / "features.json")

    quality.update({
        "full_counts": {ds: {sp: {ad.CLASSES[int(c)]: int(n) for c, n in v.items()} for sp, v in s["full_counts"].items()}
                        for ds, s in splits.items()},
        "candidate_counts": {ds: _split_counts(s["rows"]) for ds, s in splits.items()},
        "used_counts": {ds: {sp: {ad.CLASSES[int(c)]: int(n) for c, n in sub[ds][sp]["y"].value_counts()
                                  .sort_index().items()} for sp in SPLITS} for ds in sub},
        "quota": {ds: s["quota"] for ds, s in splits.items()},
        "sampling_policy": POLICY_VERSION,
        "integration_only": bool(caps.get("integration_only", False)),
        "sampling": {ds: s["sampling"] for ds, s in splits.items()},
        "capture_support": {ds: {sp: {ad.CLASSES[int(c)]: {
            "n_captures": int(g["capture_id"].nunique()),
            "counts": {str(cap): int(n) for cap, n in g.groupby("capture_id").size().items()}}
            for c, g in sub[ds][sp].groupby("y")} for sp in SPLITS} for ds in sub},
        "missing_duration": {ds: {sp: float(sub[ds][sp]["duration_s"].isna().mean()) for sp in SPLITS} for ds in sub},
        "note": "Train đặt sàn lớp; val/test giữ tỷ lệ lớp gốc, tự tăng ngân sách khi thiếu support. "
                "Không sinh mẫu.",
    })
    warnings = []
    if quality["integration_only"]:
        warnings.append("Profile smoke chỉ kiểm tra tích hợp; không dùng điểm này để kết luận chất lượng mô hình.")
    for ds, by_split in quality["sampling"].items():
        for cls, detail in by_split["train"].get("floor_shortfall", {}).items():
            warnings.append(f"{ds}/train/{cls}: chỉ có {detail['available']} mẫu thật, "
                            f"thấp hơn sàn {detail['requested']}; giữ toàn bộ, không nhân bản.")
    quality["warnings"] = warnings
    dump_json(quality, out / "quality_report.json")
    report = [f"# Chia tập và lấy mẫu — {profile}", "", f"Policy: `{POLICY_VERSION}`. "
              "Cách chia chỉ dùng nhãn/counts, không dùng điểm mô hình.", "",
              "| Nguồn | Tập | BENIGN | DOS_DDOS | OTHER_ATTACK | Tổng |", "|---|---|---:|---:|---:|---:|"]
    for ds, by_split in quality["used_counts"].items():
        for sp in SPLITS:
            counts = by_split[sp]
            report.append(f"| {ds} | {sp} | " + " | ".join(f"{counts.get(c, 0):,}" for c in ad.CLASSES) +
                          f" | {sum(counts.values()):,} |")
    report.extend(["", "Train đặt sàn rồi phân ngân sách còn lại theo counts gốc. "
                   "Val/test giữ tỷ lệ lớp gốc, không sinh mẫu hoặc lấp quota bằng lớp khác.", ""])
    report.extend(f"- {w}" for w in warnings)
    (out / "sampling_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    raw_manifest = {}
    for ds in sources:
        mf = root / cfg["sources"][ds]["dir"] / "download_manifest.json"
        raw_manifest[ds] = read_json(mf) if mf.exists() else None
    dump_json({"pipeline": cfg["pipeline"], "clients": manifest_clients,
               "sources": {ds: {"files": s["files"], "download_manifest": raw_manifest[ds],
                                "split": splits[ds]["info"],
                                "config": cfg["sources"][ds]} for ds, s in sources.items()},
               "conventions": {"cicddos2019": cfg["sources"]["cicddos2019"].get("note", ""),
                               "unsw_nb15": "test = testing-set chính thức; train/val = 5-fold nhóm fingerprint"},
               "sampling_policy": POLICY_VERSION, "sampling_config": caps,
               "hashes": hashes, "created": time.strftime("%Y-%m-%d %H:%M:%S")}, out / "dataset_manifest.json")
    log(f"Xong -> {out}")
    return {"out": str(out), "features": fitted["features"], "hashes": hashes, "clients": manifest_clients,
            "used_counts": quality["used_counts"]}


def load_config(path) -> dict:
    return read_json(path)
