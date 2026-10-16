"""Tiện ích chung cho hai baseline: cùng DDoSNet, cùng hàm train/evaluate với FL."""
import csv
import sys
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paths  # noqa: E402
from fl_ddos.task import (DDoSNet, load_global_test, metrics, per_attack_recall,  # noqa: E402
                          predict, test_labels, to_tensor, train)


def fit_and_test(df: pd.DataFrame, epochs: int, lr: float, batch: int, dev, seed: int):
    torch.manual_seed(seed)
    model = DDoSNet()
    loader = DataLoader(to_tensor(df), batch_size=batch, shuffle=True,
                        generator=torch.Generator().manual_seed(seed))
    train(model, loader, epochs, lr, 0.0, dev)
    y, p, loss = predict(model, load_global_test(), dev)
    return model, metrics(y, p, loss), per_attack_recall(test_labels(), p)


def append_row(file: Path, row: dict):
    paths.RESULTS.mkdir(parents=True, exist_ok=True)
    new = not file.exists()
    with open(file, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)
