"""Tiện ích chung cho hai baseline: cùng mô hình, cùng hàm train/evaluate với FL."""
import csv
import sys
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paths  # noqa: E402
from fl_ddos.models import ARCH_NAMES  # noqa: E402
from fl_ddos.task import (classes, load_global_test, make_model, metrics, p_attack,  # noqa: E402
                          per_attack_recall, per_class_recall, predict, test_labels, to_tensor, train)


def add_args(ap, epochs: int):
    ap.add_argument("--epochs", type=int, default=epochs)
    ap.add_argument("--lr", type=float, default=0.001)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--arch", default="resvgg_swin")
    ap.add_argument("--dropout", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=0)


def method_name(base: str, arch: str) -> str:
    return base if arch == "mlp" else f"{ARCH_NAMES.get(arch, arch)} · {base}"


def fit_and_test(df: pd.DataFrame, a, dev, seed: int):
    torch.manual_seed(seed)
    model = make_model(a.arch, a.dropout)
    loader = DataLoader(to_tensor(df), batch_size=a.batch_size, shuffle=True,
                        generator=torch.Generator().manual_seed(seed))
    train(model, loader, a.epochs, a.lr, 0.0, dev)
    y, P, loss = predict(model, load_global_test(), dev)
    per_class = per_class_recall(y, P) if len(classes()) > 2 else {}
    return model, metrics(y, P, loss), per_attack_recall(test_labels(), p_attack(P)), per_class


def append_row(file: Path, row: dict):
    paths.RESULTS.mkdir(parents=True, exist_ok=True)
    new = not file.exists()
    with open(file, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)
