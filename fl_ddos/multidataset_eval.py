"""Đánh giá cuối cho multidataset_v1 (kế hoạch mục 9): MỘT checkpoint -> hai tập test, cùng trọng số và ngưỡng.

Metric mỗi nguồn:
  - 3 lớp: confusion matrix 3×3, accuracy, F1-macro-present (TB F1 của các lớp có support thật),
    precision/recall/F1/support từng lớp.
  - attack_*: phát hiện mọi tấn công, y != BENIGN, điểm = 1 − P(BENIGN), ngưỡng cố định.
  - dos_*: phát hiện nhóm DoS/DDoS, y == DOS_DDOS, điểm = P(DOS_DDOS), ngưỡng cố định.
  - FAR trên benign; ROC-AUC/AP chỉ khi có đủ hai nhãn. Metric không xác định = None (N/A), không thay 0/1.
Thêm: TB đều theo nguồn, nguồn kém nhất, và "pooled" tính từ dự đoán gộp (không phải TB các F1).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from torch.utils.data import DataLoader

from fl_ddos import paths
from fl_ddos.multidataset_prep import read_json
from fl_ddos.task import MULTI, _meta_at, build_model, meta, predict, to_tensor

SOURCES = ("cicddos2019", "unsw_nb15")
CLASSES = ["BENIGN", "DOS_DDOS", "OTHER_ATTACK"]
HEADLINE = ["acc", "f1_macro_present", "attack_f1", "attack_recall", "attack_far_benign", "attack_roc_auc",
            "dos_f1", "dos_recall", "dos_far_benign", "dos_roc_auc"]


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _div(a, b):
    return float(a / b) if b else None


def binary_block(prefix: str, truth: np.ndarray, score: np.ndarray, benign: np.ndarray, thresh: float) -> dict:
    pred = score >= thresh
    tp, fp = int((pred & truth).sum()), int((pred & ~truth).sum())
    fn = int((~pred & truth).sum())
    p, r = _div(tp, tp + fp), _div(tp, tp + fn)
    if r is None:  # không có mẫu dương -> F1 không xác định
        f1 = None
    elif p is None:  # không dự đoán dương nào -> recall = 0, F1 = 0
        f1 = 0.0
    else:
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    two = 0 < truth.sum() < len(truth)
    return {f"{prefix}_support_pos": int(truth.sum()), f"{prefix}_support_neg": int((~truth).sum()),
            f"{prefix}_precision": p, f"{prefix}_recall": r, f"{prefix}_f1": f1,
            f"{prefix}_far_benign": _div(int((pred & benign).sum()), int(benign.sum())),
            f"{prefix}_roc_auc": float(roc_auc_score(truth, score)) if two else None,
            f"{prefix}_ap": float(average_precision_score(truth, score)) if two else None,
            f"{prefix}_threshold": thresh}


def source_metrics(y: np.ndarray, P: np.ndarray, thresh: float = 0.5) -> tuple[dict, list, np.ndarray]:
    pred = P.argmax(1)
    cm = confusion_matrix(y, pred, labels=list(range(len(CLASSES))))
    per, f1s = [], []
    for c, name in enumerate(CLASSES):
        sup, npred, tp = int(cm[c].sum()), int(cm[:, c].sum()), int(cm[c, c])
        p, r = _div(tp, npred), _div(tp, sup)
        f1 = None if sup == 0 else (0.0 if not p or not r else 2 * p * r / (p + r))
        per.append({"class": name, "support": sup, "n_pred": npred, "precision": p, "recall": r, "f1": f1})
        if sup:
            f1s.append(f1)
    benign = y == 0
    m = {"n": int(len(y)), "acc": float((pred == y).mean()) if len(y) else None,
         "f1_macro_present": float(np.mean(f1s)) if f1s else None,
         "classes_present": ",".join(CLASSES[c] for c in range(len(CLASSES)) if cm[c].sum()),
         **{f"support_{n}": int(cm[c].sum()) for c, n in enumerate(CLASSES)},
         **binary_block("attack", y != 0, 1.0 - P[:, 0], benign, thresh),
         **binary_block("dos", y == 1, P[:, 1], benign, thresh)}
    return m, per, cm


def by_original_label(labels: np.ndarray, y: np.ndarray, P: np.ndarray, thresh: float) -> pd.DataFrame:
    """Phân tích theo loại gốc (không phải dự đoán loại con): tỷ lệ bị gắn tấn công / DoS, phân phối lớp dự đoán."""
    pred = P.argmax(1)
    df = pd.DataFrame({"original_label": labels, "y": y, "pred": pred,
                       "as_attack": (1 - P[:, 0]) >= thresh, "as_dos": P[:, 1] >= thresh})
    out = df.groupby("original_label").agg(n=("y", "size"), true_class=("y", "first"),
                                           attack_detect_rate=("as_attack", "mean"), dos_detect_rate=("as_dos", "mean"))
    for c, name in enumerate(CLASSES):
        out[f"pred_{name}"] = df.groupby("original_label")["pred"].apply(lambda s, c=c: float((s == c).mean()))
    out["true_class"] = out["true_class"].map(lambda c: CLASSES[int(c)])
    return out.reset_index()


def load_checkpoint(ckpt_path) -> tuple[torch.nn.Module, dict]:
    """Nạp checkpoint và xác minh schema/preprocessor khớp features.json của data dir hiện tại."""
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    md = meta()
    if md.get("pipeline") != MULTI:
        raise ValueError(f"{paths.FEATURES_JSON}: pipeline {md.get('pipeline')}, cần {MULTI}")
    if ck.get("pipeline") != MULTI:
        raise ValueError(f"{ckpt_path}: checkpoint không phải {MULTI}")
    if ck["features"] != md["features"] or ck["classes"] != md["classes"]:
        raise ValueError("Checkpoint và data dir khác danh sách đặc trưng/lớp")
    for k in ("schema", "preprocessor", "split"):
        if ck.get("hashes", {}).get(k) != md.get("hashes", {}).get(k):
            raise ValueError(f"Hash {k} của checkpoint khác data dir: {ck.get('hashes', {}).get(k)} != "
                             f"{md.get('hashes', {}).get(k)}")
    model = build_model(ck["arch"], len(ck["features"]), len(ck["classes"]), ck["dropout"])
    model.load_state_dict(ck["state_dict"])
    return model, ck


def method_name(ck: dict) -> str:
    if ck.get("method"):
        return ck["method"]
    fs = meta().get("feature_set", "das")
    return f"FL · {ck['arch']} · {'DAS' if fs == 'das' else 'all-continuous'}"


def _replace_rows(file: Path, new: pd.DataFrame, key="checkpoint_sha256"):
    if file.exists():
        old = pd.read_csv(file)
        if key in old:
            old = old[~old[key].isin(new[key].unique())]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(file, index=False)


def evaluate_checkpoint(checkpoint_path, data_dir, results_dir, thresh: float = 0.5, device: str = "cpu",
                        write: bool = True) -> pd.DataFrame:
    paths.configure(str(data_dir), str(results_dir))
    _meta_at.cache_clear()
    model, ck = load_checkpoint(checkpoint_path)
    digest = file_sha256(checkpoint_path)
    key = {"method": method_name(ck), "checkpoint": Path(checkpoint_path).name, "checkpoint_sha256": digest,
           "kind": ck.get("kind"), "selected_round": ck.get("round"), "val_score": ck.get("val_score"),
           "seed": ck.get("seed"), "arch": ck["arch"], "feature_set": meta().get("feature_set"),
           "profile": meta().get("profile")}
    rows, per_rows, cms, orig, ys, Ps = [], [], {}, [], [], []
    for ds in SOURCES:
        df = pd.read_parquet(paths.multi_test_file(ds))
        y, P, _ = predict(model, DataLoader(to_tensor(df), batch_size=4096), device)
        m, per, cm = source_metrics(y, P, thresh)
        rows.append({**key, "dataset_id": ds, **m})
        per_rows += [{**key, "dataset_id": ds, **r} for r in per]
        cms[ds] = cm
        orig.append(by_original_label(df["original_label"].astype(str).values, y, P, thresh).assign(dataset_id=ds, **key))
        ys.append(y)
        Ps.append(P)
    res = pd.DataFrame(rows)
    agg = {**key, "n": int(res["n"].sum())}
    num = [c for c in res.columns if c not in key and c not in ("dataset_id", "classes_present", "n")
           and pd.api.types.is_numeric_dtype(res[c])]
    mean = {**agg, "dataset_id": "mean_over_sources", **{c: res[c].mean() for c in num if res[c].notna().all()}}
    worst = {**agg, "dataset_id": "worst_source", **{c: (res[c].max() if "far" in c else res[c].min())
                                                     for c in HEADLINE if c in res and res[c].notna().all()}}
    pm, _, pcm = source_metrics(np.concatenate(ys), np.concatenate(Ps), thresh)
    res = pd.concat([res, pd.DataFrame([mean, worst, {**key, "dataset_id": "pooled_predictions", **pm}])],
                    ignore_index=True)
    cms["pooled_predictions"] = pcm
    if write:
        out = Path(results_dir)
        (out / "figures").mkdir(parents=True, exist_ok=True)
        _replace_rows(out / "evaluation_by_dataset.csv", res)
        _replace_rows(out / "per_class.csv", pd.DataFrame(per_rows))
        _replace_rows(out / "per_original_label.csv", pd.concat(orig, ignore_index=True))
        conf = pd.DataFrame([{**key, "dataset_id": ds, "true": CLASSES[i], "pred": CLASSES[j], "n": int(cm[i, j])}
                             for ds, cm in cms.items() for i in range(3) for j in range(3)])
        _replace_rows(out / "confusion.csv", conf)
        plot_confusions(cms, out / "figures" / f"confusion_{Path(checkpoint_path).stem}.png", key["method"])
        write_summary(out)
    return res


def plot_confusions(cms: dict, file: Path, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(cms), figsize=(4 * len(cms), 3.8))
    for ax, (ds, cm) in zip(np.atleast_1d(axes), cms.items()):
        norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
        ax.imshow(norm, vmin=0, vmax=1, cmap="Blues")
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{cm[i, j]}", ha="center", va="center",
                        color="white" if norm[i, j] > 0.6 else "black", fontsize=8)
        ax.set_xticks(range(3), ["BEN", "DOS", "OTH"])
        ax.set_yticks(range(3), ["BEN", "DOS", "OTH"])
        ax.set_title(ds, fontsize=9)
        ax.set_xlabel("dự đoán")
    np.atleast_1d(axes)[0].set_ylabel("thật")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(file, dpi=130)
    plt.close(fig)


def _fmt(v):
    return "N/A" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.4f}"


def write_summary(results_dir: Path):
    res = pd.read_csv(results_dir / "evaluation_by_dataset.csv")
    lines = ["# Kết quả multidataset_v1 (2 client × 3 lớp)", "",
             "Mỗi checkpoint được chọn bằng validation rồi đánh giá MỘT lần trên hai tập test với cùng trọng số, "
             "ngưỡng 0,5. `attack_*` = phát hiện mọi tấn công (1 − P(BENIGN)); `dos_*` = phát hiện nhóm DoS/DDoS "
             "(P(DOS_DDOS)). F1-macro-present chỉ lấy TB trên các lớp có support thật. N/A = không xác định "
             "(thiếu một trong hai nhãn). Tập test là subset theo quota lớp, không phải toàn bộ benchmark.", ""]
    cols = ["acc", "f1_macro_present", "attack_f1", "attack_far_benign", "attack_roc_auc", "dos_f1", "dos_roc_auc"]
    for (method, prof), g in res.groupby(["method", "profile"], dropna=False):
        seeds = sorted(g["seed"].dropna().unique().tolist())
        if prof == "smoke":
            lines += ["**SMOKE: chỉ kiểm tra tích hợp; không dùng các điểm dưới đây để kết luận chất lượng mô hình.**", ""]
        lines += [f"## {method} — profile {prof}", "", f"Seed: {seeds} ({len(seeds)} lượt)." +
                  (" Một seed: không đánh giá độ biến động." if len(seeds) < 2 else ""), "",
                  "| Nguồn | n | " + " | ".join(cols) + " |", "|---|---:|" + "---:|" * len(cols)]
        for ds, gd in g.groupby("dataset_id", sort=False):
            cells = []
            for c in cols:
                v = gd[c].dropna() if c in gd else pd.Series(dtype=float)
                if len(v) == 0:
                    cells.append("N/A")
                elif len(seeds) > 1:
                    cells.append(f"{v.mean():.4f} ± {v.std(ddof=1) if len(v) > 1 else 0:.4f}")
                else:
                    cells.append(_fmt(float(v.iloc[0])))
            lines.append(f"| {ds} | {int(gd['n'].iloc[0])} | " + " | ".join(cells) + " |")
        lines.append("")
    (results_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def features_hash_info(data_dir) -> dict:
    return read_json(Path(data_dir) / "features.json").get("hashes", {})
