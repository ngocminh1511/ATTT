"""Baseline đối chứng cho multidataset_v1 (kế hoạch mục 9), cùng split/subset với FL.

  local        mỗi nguồn một mô hình, chỉ học train của nguồn đó; chọn epoch theo validation của nguồn đó
  centralized  gộp train hai nguồn (nghiên cứu tập trung); chọn epoch theo TB đều F1-macro-present 2 validation

Cả hai: class weight tính bằng cùng hàm với FL trên đúng tập train được dùng, Adam lr 0.001, batch 64,
mốc 150 epoch (= 30 vòng × 5 epoch của FL). Best checkpoint được đánh giá một lần trên hai tập test bằng
fl_ddos/multidataset_eval.py. Không gọi centralized là cận trên được bảo đảm.

  python baselines/multidataset_baselines.py --mode local --data-dir data_paper_multi/smoke \
      --results-dir results_multidataset/smoke --epochs 2 --seed 0
  python baselines/multidataset_baselines.py --mode centralized --data-dir data_paper_multi/main \
      --results-dir results_multidataset/main --epochs 150 --seed 0
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fl_ddos import paths  # noqa: E402
from fl_ddos.multidataset_prep import read_json  # noqa: E402
from fl_ddos.models import ARCH_NAMES  # noqa: E402
from fl_ddos.multidataset_eval import evaluate_checkpoint  # noqa: E402
from fl_ddos.multidataset_prep import class_weights  # noqa: E402
from fl_ddos.task import IGNORE, MULTI, classes, device, evaluate, features, make_model, meta, to_tensor  # noqa: E402


def fit_select(train_df, val_dfs: list, a, dev, weights) -> tuple[dict, int, float, list]:
    torch.manual_seed(a.seed)
    np.random.seed(a.seed)
    model = make_model(a.arch, a.dropout).to(dev)
    loader = DataLoader(to_tensor(train_df), batch_size=a.batch_size, shuffle=True,
                        generator=torch.Generator().manual_seed(a.seed))
    vals = [DataLoader(to_tensor(v), batch_size=4096) for v in val_dfs]
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32, device=dev), ignore_index=IGNORE)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    best, best_ep, best_score, hist = None, None, -np.inf, []
    for ep in range(1, a.epochs + 1):
        model.train()
        tot = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(dev), yb.to(dev)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            tot += loss.item()
        per = [evaluate(model, v, dev)["f1_macro_present"] for v in vals]
        score = float(np.mean(per))
        if not np.isfinite(score):
            raise RuntimeError(f"Epoch {ep}: điểm validation không hữu hạn {per}")
        hist.append({"epoch": ep, "train_loss": tot / max(len(loader), 1), "val_score": score,
                     **{f"val_f1mp_{i}": v for i, v in enumerate(per)}})
        if score > best_score:  # hòa -> giữ epoch sớm hơn
            best_score, best_ep = score, ep
            best = {k: t.detach().cpu().clone() for k, t in model.state_dict().items()}
        if ep % 10 == 0 or ep == a.epochs:
            print(f"  epoch {ep}/{a.epochs}: loss {hist[-1]['train_loss']:.4f}, val {score:.4f} (best {best_ep})")
    return best, best_ep, best_score, hist


def main():
    for s in (sys.stdout, sys.stderr):  # console Windows (cp1252) không in được tiếng Việt
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "centralized"], required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--lr", type=float, default=0.001)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--arch", default="resvgg_swin")
    ap.add_argument("--dropout", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    data, res = Path(a.data_dir).resolve(), Path(a.results_dir).resolve()
    paths.configure(str(data), str(res))
    if meta().get("pipeline") != MULTI:
        sys.exit(f"{data}: không phải dữ liệu {MULTI}")
    dev = device()
    clients = read_json(data / "dataset_manifest.json")["clients"]
    tr = {c["dataset_id"]: pd.read_parquet(data / c["train_file"]) for c in clients}
    va = {c["dataset_id"]: pd.read_parquet(data / c["val_file"]) for c in clients}
    clip = (0.1, 10.0)
    out = res / "baselines"
    out.mkdir(parents=True, exist_ok=True)
    arch_name = ARCH_NAMES.get(a.arch, a.arch)
    fs = meta().get("feature_set", "das")
    if a.mode == "local":
        jobs = [(f"Local-only[{ds}] · {arch_name} · {fs}", tr[ds], [va[ds]], f"local_{ds}") for ds in tr]
    else:
        jobs = [(f"Centralized · {arch_name} · {fs}", pd.concat(tr.values(), ignore_index=True), list(va.values()),
                 "centralized")]
    for method, train_df, vals, stem in jobs:
        w = class_weights(train_df["y"].values, len(classes()), clip)
        print(f"{method}: {len(train_df)} mẫu train, weight {np.round(w, 3).tolist()}, {a.epochs} epoch trên {dev}")
        state, ep, score, hist = fit_select(train_df, vals, a, dev, w)
        md = meta()
        tag = f"{stem}_{a.arch}_seed{a.seed}"
        ck = {"arch": a.arch, "dropout": a.dropout, "state_dict": state, "kind": "best", "pipeline": MULTI,
              "classes": classes(), "features": features(), "round": ep, "val_score": score, "seed": a.seed,
              "method": method, "run_config": vars(a), "hashes": md.get("hashes", {}), "profile": md.get("profile"),
              "val_metric": "F1-macro-present validation (TB đều nếu nhiều nguồn)"}
        torch.save(ck, out / f"{tag}_best.pt")
        pd.DataFrame(hist).to_csv(out / f"{tag}_epochs.csv", index=False)
        r = evaluate_checkpoint(out / f"{tag}_best.pt", data, res)
        print(r[["dataset_id", "n", "acc", "f1_macro_present", "attack_f1", "dos_f1"]].to_string(index=False))


if __name__ == "__main__":
    main()
