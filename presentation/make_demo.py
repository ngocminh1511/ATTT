"""Tạo data/demo.json và demo.html: 30 flow thật trong tập test (15 mỗi node) với xác suất của mô hình đã huấn luyện.

  .venv\\Scripts\\python.exe presentation/make_demo.py               # tính lại dữ liệu + dựng demo.html
  python presentation/make_demo.py --html-only                       # chỉ dựng lại demo.html sau khi sửa src/demo.html

Mỗi flow được đọc lại từ file raw theo row_id, qua adapter -> 17 cột liên tục -> log1p -> AFN -> DAS,
rồi so khớp với vector đã lưu trong data_paper_multi/main/test (sai khác > 1e-4 thì dừng). Xác suất lấy
từ best checkpoint FedProx (μ = 0,1) và FedAvg DAS. Không huấn luyện lại, không ghi IP/cổng/timestamp.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from fl_ddos import dataset_adapters as ad  # noqa: E402
from fl_ddos import multidataset_prep as mp  # noqa: E402
from fl_ddos import paths  # noqa: E402
from fl_ddos.multidataset_eval import load_checkpoint  # noqa: E402
from fl_ddos.task import _meta_at  # noqa: E402

DATA = ROOT / "data_paper_multi/main"
CHECKPOINTS = {
    "prox": ROOT / "results_modal_multidataset/20261109_193340_f712a4/main/das/fl/"
                   "multidataset_resvgg_swin_seed0_fedprox_mu0.1_best.pt",
    "das": ROOT / "results_modal_multidataset/20261109_161229_a7ff36/main/das/fl/multidataset_resvgg_swin_seed0_best.pt",
}
PER_SOURCE = 15     # mỗi node 15 flow, chia đều theo lớp thật của nguồn
WRONG_SHARE = 0.25  # khoảng 1/4 là ca FedProx đoán sai, để demo thấy cả lỗi
SEED = 0


def raw_rows(source: str, row_ids: list[str], cfg: dict) -> pd.DataFrame:
    """Đọc lại đúng các dòng gốc theo row_id rồi đưa qua adapter của nguồn."""
    issues, drops = Counter(), Counter()
    frames = []
    if source == "cicddos2019":
        by_file: dict[str, list[int]] = {}
        for rid in row_ids:
            stem, idx = rid.rsplit(":", 1)
            by_file.setdefault(stem, []).append(int(idx))
        for stem, idxs in by_file.items():
            raw = pd.read_parquet(ROOT / cfg["sources"]["cicddos2019"]["dir"] / f"{stem}.parquet")
            for i in idxs:
                frames.append(ad.cic_frame(raw.iloc[i:i + 1], stem, i, cfg, issues, drops))
    else:
        csv = ROOT / cfg["sources"]["unsw_nb15"]["dir"] / cfg["sources"]["unsw_nb15"]["files"]["test"]["name"]
        raw = ad.read_unsw_csv(csv)
        ids = {int(r.split(":", 1)[1]) for r in row_ids}
        frames.append(ad.unsw_frame(raw[raw["id"].isin(ids)], "test", cfg, issues, drops))
    if issues or drops:
        raise RuntimeError(f"{source}: dòng demo không qua được adapter: {issues} {drops}")
    out = pd.concat(frames, ignore_index=True).set_index("row_id").loc[row_ids].reset_index()
    return out


def clean(v):
    v = float(v)
    return None if not np.isfinite(v) else v


def render_html():
    """Nhúng data/demo.json vào src/demo.html -> demo.html (mở offline, không cần fetch)."""
    data = (HERE / "data/demo.json").read_text(encoding="utf-8")
    payload = json.dumps(json.loads(data), ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = (HERE / "src/demo.html").read_text(encoding="utf-8")
    if html.count("__DEMO__") != 1:
        raise ValueError("src/demo.html cần đúng một __DEMO__")
    (HERE / "demo.html").write_text(html.replace("__DEMO__", payload), encoding="utf-8")
    print(f"OK: {HERE / 'demo.html'}")


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    if "--html-only" in sys.argv:  # chỉ dựng lại HTML từ data/demo.json, không cần torch
        render_html()
        return
    cfg = mp.load_config(ROOT / "configs/multidataset.json")
    prep = mp.read_json(DATA / "prep_params.json")
    paths.configure(str(DATA), str(HERE / "_demo_tmp"))
    _meta_at.cache_clear()
    models = {}
    for key, ck in CHECKPOINTS.items():
        model, meta = load_checkpoint(ck)
        models[key] = (model.eval(), meta)
    features = prep["features"]
    rng = np.random.default_rng(SEED)
    samples = []
    for source in ("cicddos2019", "unsw_nb15"):
        test = pd.read_parquet(DATA / "test" / f"{source}.parquet")
        x = torch.tensor(test[features].values, dtype=torch.float32)
        with torch.no_grad():
            probs = {k: torch.softmax(m(x), 1).numpy() for k, (m, _) in models.items()}
        pred = probs["prox"].argmax(1)
        chosen = []
        classes = sorted(test["y"].unique())
        for j, c in enumerate(classes):
            quota = PER_SOURCE // len(classes) + (1 if j < PER_SOURCE % len(classes) else 0)
            wrong = max(1, round(quota * WRONG_SHARE))
            for kind, k in (("correct", quota - wrong), ("wrong", wrong)):
                mask = (test["y"].values == c) & ((pred == c) if kind == "correct" else (pred != c))
                idx = np.flatnonzero(mask)
                chosen += [(int(i), kind) for i in rng.choice(idx, min(k, len(idx)), replace=False)]
        rows = test.iloc[[i for i, _ in chosen]]
        raw = raw_rows(source, rows["row_id"].tolist(), cfg)
        derived = mp.derive(raw)
        logx = mp.log1p_valid(derived[mp.CONTINUOUS].values)
        groups = raw["protocol_group"].astype(str).values
        z = mp.apply_afn(logx, groups, prep["afn"])
        rebuilt = mp.transform_canonical(raw, prep)[features].values
        if not np.allclose(rebuilt, rows[features].values, atol=1e-4):
            raise RuntimeError(f"{source}: vector dựng lại không khớp artifact test")
        for j, (i, kind) in enumerate(chosen):
            r = raw.iloc[j]
            samples.append({
                "id": f"{source}:{len(samples)}", "source": source, "row_id": r["row_id"],
                "original_label": str(r["original_label"]), "true": int(r["y"]), "expect": kind,
                "raw": {k: (clean(r[k]) if k != "protocol_group" else str(r[k])) for k in ad.BASE},
                "derived": {c: clean(derived.iloc[j][c]) for c in mp.CONTINUOUS},
                "z": {c: clean(z[j, mp.CONTINUOUS.index(c)]) for c in mp.CONTINUOUS},
                "fixed": {c: clean(derived.iloc[j][c]) for c in mp.FIXED},
                "input": [clean(v) for v in rebuilt[j]],
                "probs": {k: [round(float(p), 6) for p in probs[k][i]] for k in models},
            })
    out = {"version": 1, "checkpoints": {k: {"file": str(p.relative_to(ROOT)).replace("\\", "/"),
                                              "round": models[k][1]["round"]} for k, p in CHECKPOINTS.items()},
           "features": features, "continuous": mp.CONTINUOUS,
           "selected": prep["continuous_selected"], "fixed": mp.FIXED, "threshold": 0.5,
           "classes": ad.CLASSES, "afn_groups": {g: prep["afn"]["groups"][g]["n_rows"] for g in ad.PROTO_GROUPS
                                                 if g in prep["afn"]["groups"]},
           "samples": samples}
    (HERE / "data/demo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ok = sum(int(np.argmax(s["probs"]["prox"]) == s["true"]) for s in samples)
    print(f"OK: {len(samples)} flow ({ok} FedProx đoán đúng) -> {HERE / 'data/demo.json'}")
    render_html()


if __name__ == "__main__":
    main()
