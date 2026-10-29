"""Các bước tiền xử lý theo Alshdadi et al., Future Internet 2025, 17, 88 (mục 3.2–3.6).

Mỗi bước cần thống kê toàn cục được tách làm hai nửa giống federated_scaler.py:
*_stats() chạy TẠI client và chỉ trả về tổng; aggregate_*() chạy TẠI server.
Các bước sinh/bớt mẫu (CTA, DPCA) chỉ dùng dữ liệu của chính client.

Chỗ khác paper (có lý do, ghi trong README):
  - AFN mặc định nhóm theo protocol, không theo nhãn attack/normal: lúc test không có nhãn.
    afn="label" giữ đúng nguyên văn để minh họa rò rỉ nhãn (test dùng nhãn thật).
  - TEC tính trên thứ tự dòng trong từng file (bản Kaggle không có Timestamp), trước khi sinh mẫu.
  - Eq.3 (MTB) cho trọng số LỚN với lớp xuất hiện nhiều; ở đây dùng nghịch đảo để làm class weight.
"""
import numpy as np
import pandas as pd

EPS = 1e-8


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


# ---------------------------------------------------------------- AFN (Eq.1)
def afn_groups(df: pd.DataFrame, mode: str) -> np.ndarray:
    if mode == "protocol":
        return df["protocol"].astype(int).astype(str).values
    if mode == "label":  # nguyên văn paper -> cần nhãn, RÒ RỈ khi áp lên tập test
        return np.where(df["label"] == "BENIGN", "normal", "attack")
    return np.full(len(df), "all")


def afn_stats(x: np.ndarray, groups: np.ndarray) -> dict:
    return {g: {"n": int((groups == g).sum()), "sum": x[groups == g].sum(0),
                "sumsq": (x[groups == g] ** 2).sum(0)} for g in np.unique(groups)}


def aggregate_afn(stats: list) -> dict:
    acc = {}
    for st in stats:
        for g, s in st.items():
            for key in (g, "__all__"):  # __all__: dự phòng cho nhóm chưa gặp lúc train
                a = acc.setdefault(key, {"n": 0, "sum": 0.0, "sumsq": 0.0})
                a["n"] += s["n"]; a["sum"] = a["sum"] + s["sum"]; a["sumsq"] = a["sumsq"] + s["sumsq"]
    out = {}
    for g, a in acc.items():
        mu = a["sum"] / a["n"]
        out[g] = {"n": a["n"], "mean": mu, "std": np.sqrt(np.maximum(a["sumsq"] / a["n"] - mu ** 2, 0.0))}
    return out


def apply_afn(x: np.ndarray, groups: np.ndarray, params: dict) -> np.ndarray:
    out = np.empty_like(x)
    for g in np.unique(groups):
        p = params.get(g, params["__all__"])
        out[groups == g] = (x[groups == g] - p["mean"]) / (p["std"] + EPS)
    return out


# ---------------------------------------------------------------- TEC (Eq.11)
def tec(df: pd.DataFrame, feats: list, tau: int) -> pd.DataFrame:
    """Tốc độ thay đổi TB trong cửa sổ τ flow gần nhất của cùng file (nhân quả: chỉ nhìn về trước).

    df phải được sắp theo (file_id, t_order). Σ_{t}(q_t − q_{t−1}) / (τ−1) = (q_t − q_{t−τ+1}) / (τ−1).
    """
    g = df.groupby("file_id", sort=False)
    out = {}
    for f in feats:
        first = g[f].transform("first")
        out[f"tec_{f}"] = (df[f] - g[f].shift(tau - 1).fillna(first)) / (tau - 1)
    return pd.DataFrame(out, index=df.index)


# ---------------------------------------------------------------- CTA (Eq.2)
def cta(x, y, t, ratio, window, rng):
    """Sinh ratio·n mẫu: z = λ z_p + (1 − λ) z_q, λ = e^{−s}/(1 + e^{−s}).

    z_q là mẫu CÙNG LỚP đứng sau z_p không quá `window` vị trí theo thời gian (trộn hai lớp khác
    nhau sẽ tạo nhãn mơ hồ); s = khoảng cách thời gian chia cho window.
    """
    m = int(len(x) * ratio)
    if m == 0 or len(x) < 2:
        return x[:0], y[:0], t[:0]
    order = np.lexsort((t, y))  # gom theo lớp, trong lớp sắp theo thời gian
    pos = rng.integers(0, len(x) - 1, m)
    q = np.minimum(pos + rng.integers(1, window + 1, m), len(x) - 1)
    ip, iq = order[pos], order[q]
    ok = y[ip] == y[iq]
    ip, iq = ip[ok], iq[ok]
    lam = sigmoid(-np.abs(t[ip] - t[iq]) / window)[:, None]
    return lam * x[ip] + (1 - lam) * x[iq], y[ip], t[ip]


# ---------------------------------------------------------------- DPCA = WIS + FBSA (Eq.4–6)
def dpca(x, y, t, rng, n_cand=5):
    """Đưa mọi lớp về gần n̄ (tần suất TB các lớp).

    β_k = (n̄ − n_k) / n_k > 0 -> WIS sinh β_k·n_k mẫu: v = λ v_a + (1 − λ) v_b, λ = sigmoid(δ), v_b là
    mẫu gần v_a nhất trong n_cand ứng viên cùng lớp, δ = khoảng cách Euclid.
    β_k < 0 -> FBSA giữ mỗi mẫu với xác suất π_k = n̄ / n_k.
    """
    classes, counts = np.unique(y, return_counts=True)
    nbar = counts.mean()
    xs, ys, ts = [], [], []
    for c, n_k in zip(classes, counts):
        idx = np.where(y == c)[0]
        beta = (nbar - n_k) / max(n_k, EPS)
        if beta < 0:
            keep = idx[rng.random(n_k) < nbar / (n_k + EPS)]
            xs.append(x[keep]); ys.append(y[keep]); ts.append(t[keep])
            continue
        xs.append(x[idx]); ys.append(y[idx]); ts.append(t[idx])
        m = int(round(beta * n_k))
        if m == 0:
            continue
        a = rng.choice(idx, m)
        cand = rng.choice(idx, (m, n_cand))
        d = np.linalg.norm(x[cand] - x[a][:, None, :], axis=2)
        j = d.argmin(1)
        b, delta = cand[np.arange(m), j], d[np.arange(m), j]
        lam = sigmoid(delta)[:, None]
        xs.append(lam * x[a] + (1 - lam) * x[b]); ys.append(np.full(m, c)); ts.append(t[a])
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(ts)


# ---------------------------------------------------------------- MTB (Eq.3)
def mtb_weights(y, t, n_classes, n_windows=10, clip=(0.1, 10.0)) -> list:
    """ω_c = (1/M) Σ_m f_{c,m} / max_c f_{c,m}; class weight = 1/ω_c (chuẩn hóa TB = 1 trên các lớp có mặt)."""
    chunks = np.array_split(y[np.argsort(t, kind="stable")], n_windows)
    f = np.stack([np.bincount(ch, minlength=n_classes) / max(len(ch), 1) for ch in chunks])
    omega = (f / np.maximum(f.max(1, keepdims=True), EPS)).mean(0)
    present = np.bincount(y, minlength=n_classes) > 0
    w = np.ones(n_classes)
    w[present] = 1.0 / np.maximum(omega[present], EPS)
    w[present] /= w[present].mean()
    return np.clip(w, *clip).tolist()


# ---------------------------------------------------------------- DAS = CRA + IDF (Eq.7–9)
def das_stats(x: np.ndarray, y: np.ndarray, n_classes: int) -> dict:
    onehot = np.eye(n_classes)[y]
    return {"n": len(x), "sx": x.sum(0), "sxx": x.T @ x, "sxy": x.T @ onehot, "sy": onehot.sum(0)}


def aggregate_das(stats: list, n_select: int, theta: float, gamma: float) -> dict:
    """CRA: R_q = TB_r Cov(z_q, t_r)² / (Var z_q · Var t_r). IDF: bỏ đặc trưng có |C_{q,p}| ≥ γ
    với một đặc trưng đã chọn có R cao hơn. Giữ tối đa n_select đặc trưng có R_q > θ."""
    n = sum(s["n"] for s in stats)
    mx, my = sum(s["sx"] for s in stats) / n, sum(s["sy"] for s in stats) / n
    cov_xx = sum(s["sxx"] for s in stats) / n - np.outer(mx, mx)
    cov_xy = sum(s["sxy"] for s in stats) / n - np.outer(mx, my)
    var_x, var_y = np.maximum(np.diag(cov_xx), 0.0), my * (1 - my)
    live = var_y > EPS
    rel = (cov_xy[:, live] ** 2 / (var_x[:, None] * var_y[None, live] + EPS)).mean(1)
    corr = cov_xx / (np.sqrt(np.outer(var_x, var_x)) + EPS)
    chosen = []
    for q in np.argsort(-rel):
        if rel[q] <= theta or len(chosen) >= n_select:
            break
        if var_x[q] > EPS and all(abs(corr[q, p]) < gamma for p in chosen):
            chosen.append(int(q))
    return {"selected": chosen, "relevance": rel.tolist()}


# ---------------------------------------------------------------- FDP: NDS + JAA (Eq.10, 12)
def fdp(df: pd.DataFrame, ranked: list, n_pair_top: int = 4, n_triplets: int = 2) -> pd.DataFrame:
    """NDS: log(|p_i·p_j| + 1) cho mọi cặp trong n_pair_top đặc trưng đầu; JAA: RMS của từng bộ ba liên tiếp."""
    out = {}
    top = ranked[:n_pair_top]
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            out[f"nds_{a}__{b}"] = np.log1p(np.abs(df[a].values * df[b].values))
    for k in range(n_triplets):
        tri = ranked[3 * k:3 * k + 3]
        if len(tri) == 3:
            out["jaa_" + "__".join(tri)] = np.sqrt((df[tri].values ** 2).mean(1))
    return pd.DataFrame(out, index=df.index)


# ---------------------------------------------------------------- FRP = DRA + LIS (Eq.14–16)
def dra_stats(x):
    return {"min": x.min(0), "max": x.max(0)}


def aggregate_dra(stats):
    return {"min": np.min([s["min"] for s in stats], 0), "max": np.max([s["max"] for s in stats], 0)}


def apply_dra(x, p, lo=0.0, hi=1.0):
    """Eq.14 với [F, E] = [0, 1]. Tập test có thể ra ngoài [0, 1]; không cắt để không giấu lệch phân phối."""
    return (x - p["min"]) / (p["max"] - p["min"] + EPS) * (hi - lo) + lo


def lis_stats(x, is_attack):
    return {"n": len(x), "sx": x.sum(0), "sxx": (x ** 2).sum(0), "sxp": x.T @ is_attack, "sp": is_attack.sum()}


def aggregate_lis(stats, clip=(0.1, 10.0)):
    """Eq.15: λ_n = |Cov(n, p)| / (Var(n) + ε), p = 1 nếu là tấn công; chuẩn hóa TB = 1 rồi cắt."""
    n = sum(s["n"] for s in stats)
    mx, mp = sum(s["sx"] for s in stats) / n, sum(s["sp"] for s in stats) / n
    var = np.maximum(sum(s["sxx"] for s in stats) / n - mx ** 2, 0.0)
    cov = sum(s["sxp"] for s in stats) / n - mx * mp
    lam = np.abs(cov) / (var + 1e-3)
    lam = lam / max(lam.mean(), EPS)
    return {"lambda": np.clip(lam, *clip)}
