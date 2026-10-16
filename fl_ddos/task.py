"""Mô hình, nạp dữ liệu, huấn luyện và đánh giá (mục 6.3).

Parquet trong data/ chứa các cột đặc trưng ĐÃ slog1p, cột "binary" (0/1) và "label"
(tên loại tấn công). Chuẩn hóa bằng scaler.json được áp dụng khi tạo tensor.
"""
from functools import lru_cache

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             precision_recall_fscore_support, roc_auc_score)
from torch.utils.data import DataLoader, TensorDataset

from fl_ddos import paths
from fl_ddos.features import load_meta, load_scaler, standardize


@lru_cache(maxsize=1)
def features() -> list:
    return load_meta()["features"]


@lru_cache(maxsize=1)
def scaler():
    return load_scaler()


class DDoSNet(nn.Module):
    def __init__(self, n_in: int | None = None):
        super().__init__()
        n_in = n_in or len(features())
        self.net = nn.Sequential(
            nn.Linear(n_in, 128), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 2))  # 2 lớp: benign / ddos

    def forward(self, x):
        return self.net(x)


def to_tensor(df: pd.DataFrame, flip_labels: bool = False) -> TensorDataset:
    mean, std = scaler()
    x = standardize(df[features()].values.astype(np.float64), mean, std)
    y = df["binary"].values.astype(np.int64)
    if flip_labels:  # E7: client bị chiếm, đảo nhãn
        y = 1 - y
    return TensorDataset(torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.long))


def read_local(pid: int, scenario: str) -> pd.DataFrame:
    path = paths.LOCAL_DATA or paths.client_file(scenario, pid)
    return pd.read_parquet(path)


def load_local(pid: int, scenario: str, batch: int, seed: int = 0, poison: bool = False):
    df = read_local(pid, scenario)
    val = df.sample(frac=0.1, random_state=seed)
    tr = df.drop(val.index)
    g = torch.Generator().manual_seed(seed + pid)
    return (DataLoader(to_tensor(tr, poison), batch_size=batch, shuffle=True, generator=g),
            DataLoader(to_tensor(val), batch_size=1024))


def load_global_test(batch: int = 4096) -> DataLoader:
    return DataLoader(to_tensor(pd.read_parquet(paths.TEST_DAY2)), batch_size=batch)


def test_labels() -> np.ndarray:
    return pd.read_parquet(paths.TEST_DAY2, columns=["label"])["label"].values


def train(model, loader, epochs, lr, mu, device):
    model.to(device).train()
    global_params = [p.detach().clone() for p in model.parameters()]  # cho FedProx
    y = loader.dataset.tensors[1]
    w = torch.bincount(y, minlength=2).float()
    w = (w.sum() / (2 * w.clamp(min=1))).to(device)  # class weight
    loss_fn = nn.CrossEntropyLoss(weight=w)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    total = 0.0
    for _ in range(epochs):
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            if mu > 0:  # FedProx: + mu/2 * ||w - w_global||^2
                prox = sum(((p - g) ** 2).sum() for p, g in zip(model.parameters(), global_params))
                loss = loss + mu / 2 * prox
            loss.backward()
            opt.step()
            total += loss.item()
    return total / max(epochs * len(loader), 1)


@torch.no_grad()
def predict(model, loader, device):
    model.to(device).eval()
    ys, ps, loss, ce = [], [], 0.0, nn.CrossEntropyLoss()
    for xb, yb in loader:
        out = model(xb.to(device))
        loss += ce(out, yb.to(device)).item()
        ps.append(torch.softmax(out, 1)[:, 1].cpu())
        ys.append(yb)
    return torch.cat(ys).numpy(), torch.cat(ps).numpy(), loss / max(len(loader), 1)


def metrics(y, p, loss=float("nan"), thresh=0.5) -> dict:
    pred = (p >= thresh).astype(int)
    prec, rec, f1, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    two = len(set(y)) > 1
    return {"loss": float(loss), "acc": float((pred == y).mean()),
            "precision": float(prec), "recall": float(rec), "f1": float(f1),
            "fpr": float(fp / max(fp + tn, 1)),
            "auc": float(roc_auc_score(y, p)) if two else 0.0,
            "pr_auc": float(average_precision_score(y, p)) if two else 0.0}


def evaluate(model, loader, device):
    y, p, loss = predict(model, loader, device)
    return metrics(y, p, loss)


def per_attack_recall(labels, p, thresh=0.5) -> dict:
    """Tỉ lệ phát hiện theo từng loại (với BENIGN là tỉ lệ bị báo nhầm = FPR)."""
    pred = p >= thresh
    return {lab: float(pred[labels == lab].mean()) for lab in sorted(set(labels))}


def set_seed(seed: int):
    np.random.seed(seed)
    torch.manual_seed(seed)


def device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def method_label(mu, strategy="fedavg", poison="") -> str:
    """Tên phương pháp thống nhất giữa log server, per_attack.csv và bảng tổng hợp."""
    mu = float(mu)
    name = "FedTrimmedAvg" if strategy == "trimmed" else "FedAvg"
    if mu > 0:
        name = f"FedProx μ={mu:g}" + (" + TrimmedAvg" if strategy == "trimmed" else "")
    return name + (" [poison]" if str(poison) not in ("", "nan") else "")
