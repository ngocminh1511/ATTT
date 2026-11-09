"""Mô hình, nạp dữ liệu, huấn luyện và đánh giá (mục 6.3).

Hai loại dữ liệu, phân biệt bằng features.json:
  - pipeline cũ (data/): cột đặc trưng ĐÃ slog1p, chuẩn hóa bằng scaler.json khi tạo tensor; nhãn "binary".
  - pipeline paper (data_paper/, prepare/paper_pipeline.py): đặc trưng đã qua AFN…LIS, dùng nguyên;
    nhãn đa lớp "y" theo meta["classes"] (lớp 0 = BENIGN; −100 = lớp chưa gặp lúc train, bỏ qua trong loss).
  - pipeline multidataset_v1 (data_paper_multi/, prepare/multidataset_pipeline.py): 2 client × 3 lớp,
    đặc trưng đã qua log1p + AFN, dùng nguyên; validation đã chia sẵn (val_client_k.parquet) TRƯỚC mọi bước fit.
Cả ba đều có cột "label" (tên loại) và "binary" (0/1) cho metric phát hiện nhị phân.
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (average_precision_score, confusion_matrix, log_loss,
                             precision_recall_fscore_support, roc_auc_score)
from torch.utils.data import DataLoader, TensorDataset

from fl_ddos import paths
from fl_ddos.features import load_meta, load_scaler, standardize
from fl_ddos.models import ARCH_NAMES, DDoSNet, build_model  # noqa: F401  (DDoSNet: tương thích ngược)

IGNORE = -100


@lru_cache(maxsize=8)
def _meta_at(path: str, mtime: float) -> dict:
    return load_meta(path)


def meta() -> dict:
    """features.json của thư mục data hiện tại; cache theo (đường dẫn, mtime) nên đổi data-dir không dùng nhầm schema."""
    f = paths.FEATURES_JSON
    return _meta_at(str(f), f.stat().st_mtime if f.exists() else 0.0)


def features() -> list:
    return meta()["features"]


def classes() -> list:
    return meta().get("classes", ["BENIGN", "DDoS"])


def is_paper() -> bool:
    return meta().get("pipeline") == "paper"


MULTI = "multidataset_v1"


def is_multi() -> bool:
    return meta().get("pipeline") == MULTI


def uses_scaler() -> bool:
    """Chỉ pipeline MLP cũ (data/) chuẩn hóa bằng scaler.json lúc tạo tensor."""
    return meta().get("pipeline") not in ("paper", MULTI)


@lru_cache(maxsize=8)
def _scaler_at(path: str, mtime: float):
    return load_scaler(path)


def scaler():
    f = paths.SCALER_JSON
    return _scaler_at(str(f), f.stat().st_mtime if f.exists() else 0.0)


def make_model(arch: str = "mlp", dropout: float = 0.3) -> nn.Module:
    return build_model(arch, len(features()), len(classes()), dropout)


def to_tensor(df: pd.DataFrame, flip_labels: bool = False) -> TensorDataset:
    x = df[features()].values.astype(np.float64)
    if uses_scaler():
        mean, std = scaler()
        x = standardize(x, mean, std)
    y = df["y" if "y" in df.columns else "binary"].values.astype(np.int64)
    if flip_labels:  # E7: client bị chiếm, đảo nhãn (nhị phân) / dịch nhãn (đa lớp)
        y = np.where(y >= 0, (y + 1) % len(classes()), y) if len(classes()) > 2 else 1 - y
    return TensorDataset(torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.long))


def read_local(pid: int, scenario: str) -> pd.DataFrame:
    return pd.read_parquet(paths.client_file(scenario, pid))


def load_local(pid: int, scenario: str, batch: int, seed: int = 0, poison: bool = False):
    if is_multi():  # validation đã chia theo nhóm trước mọi bước fit, không tách lại từ file train
        tr, val = read_local(pid, scenario), pd.read_parquet(paths.val_file(scenario, pid))
    else:
        df = read_local(pid, scenario)
        val = df.sample(frac=0.1, random_state=seed)
        tr = df.drop(val.index)
    g = torch.Generator().manual_seed(seed + pid)
    return (DataLoader(to_tensor(tr, poison), batch_size=batch, shuffle=True, generator=g),
            DataLoader(to_tensor(val), batch_size=1024))


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def mtb_weights(pid: int, scenario: str):
    """Class weight do pipeline tính sẵn cho client: MTB (Eq.3) của paper_pipeline.py, hoặc
    class_weights.json (nghịch đảo tần suất, lớp vắng = 0) của multidataset_v1; None nếu không có."""
    for name in ("class_weights.json", "mtb_weights.json"):
        f = paths.DATA / scenario / name
        if f.exists():
            return _read_json(f)[f"client_{pid + 1}"]
    if is_multi():
        raise FileNotFoundError(f"Thiếu {paths.DATA / scenario / 'class_weights.json'}")
    return None


def load_global_test(batch: int = 4096) -> DataLoader:
    return DataLoader(to_tensor(pd.read_parquet(paths.TEST_DAY2)), batch_size=batch)


def test_labels() -> np.ndarray:
    return pd.read_parquet(paths.TEST_DAY2, columns=["label"])["label"].values


def train(model, loader, epochs, lr, mu, device, class_weight=None):
    model.to(device).train()
    global_params = [p.detach().clone() for p in model.parameters()]  # cho FedProx
    if class_weight is None:  # cân bằng theo tần suất trong dữ liệu cục bộ
        y = loader.dataset.tensors[1]
        w = torch.bincount(y[y >= 0], minlength=len(classes())).float()
        w = w.sum() / (len(w) * w.clamp(min=1))
    else:
        w = torch.tensor(class_weight, dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=w.to(device), ignore_index=IGNORE)
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
    """Trả về (y, P, loss): P là xác suất softmax N×C."""
    model.to(device).eval()
    ys, ps, loss, ce = [], [], 0.0, nn.CrossEntropyLoss(ignore_index=IGNORE)
    for xb, yb in loader:
        out = model(xb.to(device))
        if (yb >= 0).any():
            loss += ce(out, yb.to(device)).item()
        ps.append(torch.softmax(out, 1).cpu())
        ys.append(yb)
    return torch.cat(ys).numpy(), torch.cat(ps).numpy(), loss / max(len(loader), 1)


def p_attack(P: np.ndarray) -> np.ndarray:
    """Xác suất là tấn công = 1 − P(BENIGN) (lớp 0)."""
    return 1.0 - P[:, 0]


def metrics(y, P, loss=float("nan"), thresh=0.5) -> dict:
    """Metric phát hiện nhị phân (f1, recall, fpr, auc… như trước) + metric đa lớp của paper:
    msi (Eq.23, recall TB theo lớp), far (Eq.24, = fpr), f1_macro, log_loss, auc_ovr.
    Mẫu có y = −100 (lớp chưa gặp, vd. PortScan) chỉ tính vào phần nhị phân, như một tấn công."""
    yb, p = (y != 0).astype(int), p_attack(P)
    pred = (p >= thresh).astype(int)
    prec, rec, f1, _ = precision_recall_fscore_support(yb, pred, average="binary", zero_division=0)
    tn, fp, fn, tp = confusion_matrix(yb, pred, labels=[0, 1]).ravel()
    two = len(set(yb)) > 1
    out = {"loss": float(loss), "precision": float(prec), "recall": float(rec), "f1": float(f1),
           "fpr": float(fp / max(fp + tn, 1)), "far": float(fp / max(fp + tn, 1)),
           "auc": float(roc_auc_score(yb, p)) if two else 0.0,
           "pr_auc": float(average_precision_score(yb, p)) if two else 0.0}
    known = y >= 0
    yk, Pk = y[known], P[known]
    pk = Pk.argmax(1)
    present = np.unique(yk)
    _, rec_c, f1_c, _ = precision_recall_fscore_support(yk, pk, labels=present, zero_division=0)
    aucs = [roc_auc_score(yk == c, Pk[:, c]) for c in present if 0 < (yk == c).sum() < len(yk)]
    out.update({"acc": float((pk == yk).mean()) if len(yk) else 0.0,
                "msi": float(rec_c.mean()) if len(present) else 0.0,
                "f1_macro": float(f1_c.mean()) if len(present) else 0.0,  # = F1-macro-present
                "f1_macro_present": float(f1_c.mean()) if len(present) else float("nan"),
                "log_loss": float(log_loss(yk, np.clip(Pk, 1e-7, 1), labels=range(P.shape[1]))) if len(yk) else 0.0,
                "auc_ovr": float(np.mean(aucs)) if aucs else 0.0})
    return out


def evaluate(model, loader, device):
    y, P, loss = predict(model, loader, device)
    return metrics(y, P, loss)


def per_attack_recall(labels, p, thresh=0.5) -> dict:
    """Tỉ lệ bị gắn là tấn công theo từng loại (với BENIGN là tỉ lệ báo nhầm = FPR). p = p_attack."""
    pred = p >= thresh
    return {lab: float(pred[labels == lab].mean()) for lab in sorted(set(labels))}


def per_class_recall(y, P) -> dict:
    """Recall đa lớp theo từng lớp đã biết (đúng LOẠI tấn công, không chỉ đúng là tấn công)."""
    pred = P.argmax(1)
    return {classes()[c]: float((pred[y == c] == c).mean()) for c in np.unique(y[y >= 0])}


def set_seed(seed: int):
    np.random.seed(seed)
    torch.manual_seed(seed)


def device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def method_label(mu, strategy="fedavg", poison="", arch="mlp") -> str:
    """Tên phương pháp thống nhất giữa log server, per_attack.csv và bảng tổng hợp."""
    mu = float(mu)
    name = "FedTrimmedAvg" if strategy == "trimmed" else "FedAvg"
    if mu > 0:
        name = f"FedProx μ={mu:g}" + (" + TrimmedAvg" if strategy == "trimmed" else "")
    if str(arch) not in ("mlp", "", "nan"):
        name = f"{ARCH_NAMES.get(arch, arch)} · {name}"
    return name + (" [poison]" if str(poison) not in ("", "nan") else "")
