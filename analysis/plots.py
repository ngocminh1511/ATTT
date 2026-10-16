"""Mục 8.3–8.4: bảng kết quả và các hình cho báo cáo.

Đọc:  results/fl/*.csv (log từng vòng của server), results/baselines.csv, results/per_attack.csv,
      results/lab_latency.csv (nếu có)
Ghi:  results/figures/*.png và results/summary.md
  python analysis/plots.py [--model results/fl/S3_mu0.0_fedavg_seed0_global.pt]
"""
import argparse
import glob
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.ticker  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from sklearn.metrics import confusion_matrix, roc_curve  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paths  # noqa: E402
from fl_ddos.task import method_label  # noqa: E402

# Bảng màu categorical cố định (thứ tự không đổi), mực chữ trung tính, lưới nhạt.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": GRID,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    "legend.frameon": False, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
})
FIG = paths.RESULTS / "figures"


def load_fl():
    files = glob.glob(str(paths.RESULTS / "fl" / "*.csv"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["poison"] = df["poison"].fillna("").astype(str)
    df["method"] = [method_label(m, s, p) for m, s, p in zip(df["mu"], df["strategy"], df["poison"])]
    return df


def save(fig, name, tight=True):
    FIG.mkdir(parents=True, exist_ok=True)
    if tight:
        fig.tight_layout()
    fig.savefig(FIG / name, dpi=200)
    plt.close(fig)
    print(f"  {FIG / name}")


METHOD_ORDER = ["Local-only", "FedAvg", "FedProx μ=0.01", "FedProx μ=0.1", "Centralized"]


def color_map(methods) -> dict:
    """Màu đi theo phương pháp (không theo thứ hạng/panel): cố định thứ tự, không quay vòng."""
    ordered = [m for m in METHOD_ORDER if m in methods] + sorted(set(methods) - set(METHOD_ORDER))
    return {m: SERIES[i] for i, m in enumerate(ordered[:len(SERIES)])}


def fig_f1_vs_round(fl):
    scen = sorted(fl["scenario"].unique())
    colors = color_map(set(fl["method"]))
    fig, axes = plt.subplots(1, len(scen), figsize=(3.6 * len(scen), 3.4), sharey=True, squeeze=False)
    for ax, sc in zip(axes[0], scen):
        for m, g in fl[fl.scenario == sc].groupby("method"):
            if m not in colors:
                continue
            curve = g.groupby("round")["f1"].agg(["mean", "std"]).fillna(0)
            ax.plot(curve.index, curve["mean"], color=colors[m], label=m)
            ax.fill_between(curve.index, curve["mean"] - curve["std"], curve["mean"] + curve["std"],
                            color=colors[m], alpha=0.15, linewidth=0)
        ax.set_title(sc); ax.set_xlabel("Vòng FL")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    axes[0][0].set_ylabel("F1 trên test ngày 2")
    handles = [plt.Line2D([], [], color=c, lw=2) for c in colors.values()]
    fig.legend(handles, list(colors), loc="lower center", ncol=min(len(colors), 4), bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.1 if len(colors) <= 4 else 0.16, 1, 1))
    save(fig, "f1_vs_round.png", tight=False)


def final_round(fl):
    last = fl[fl["round"] == fl.groupby(["scenario", "method", "seed"])["round"].transform("max")]
    return last


def fig_bar(fl, base):
    rows = []
    if not fl.empty:
        rows.append(final_round(fl)[["scenario", "method", "seed", "f1"]])
    if not base.empty:
        b = base[base.client.astype(str).isin(["all", "mean"])][["scenario", "method", "seed", "f1"]]
        rows.append(b)
    if not rows:
        return
    d = pd.concat(rows)
    colors = color_map(set(d.method))
    central = d[d.method == "Centralized"]["f1"]
    d = d[d.scenario.isin(["S1", "S3"]) & d.method.isin(METHOD_ORDER[:-1])]
    order = [m for m in METHOD_ORDER[:-1] if m in set(d.method)]
    scen = [s for s in ["S1", "S3"] if s in set(d.scenario)]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    width = 0.8 / max(len(order), 1)
    for i, m in enumerate(order):
        x, mean, std = [], [], []
        for j, sc in enumerate(scen):
            g = d[(d.method == m) & (d.scenario == sc)]["f1"]
            if len(g):
                x.append(j + (i - (len(order) - 1) / 2) * width)
                mean.append(g.mean()); std.append(g.std() if len(g) > 1 else 0)
        ax.bar(x, mean, width - 0.02, yerr=std, color=colors[m], label=m, error_kw={"ecolor": INK2, "lw": 1})
    if len(central):  # cận trên: đường tham chiếu, không phải một cột nữa
        ax.axhline(central.mean(), color=INK2, linestyle="--", linewidth=1.2)
        ax.annotate(f"Centralized {central.mean():.3f}", xy=(1, central.mean()), xycoords=("axes fraction", "data"),
                    xytext=(-4, 4), textcoords="offset points", ha="right", color=INK2, fontsize=9)
    ax.set_xticks(range(len(scen))); ax.set_xticklabels(scen); ax.set_ylabel("F1 (vòng cuối)"); ax.set_ylim(0, 1.08)
    ax.legend(ncol=max(len(order), 1), loc="upper center", bbox_to_anchor=(0.5, -0.1))
    save(fig, "bar_f1.png")


def fig_confusion_roc(model_path):
    from fl_ddos.task import DDoSNet, load_global_test, predict
    model = DDoSNet(); model.load_state_dict(torch.load(model_path, map_location="cpu"))
    y, p, _ = predict(model, load_global_test(), "cpu")
    cm = confusion_matrix(y, (p >= 0.5).astype(int), labels=[0, 1])
    fpr, tpr, _ = roc_curve(y, p)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.4))
    a1.imshow(cm, cmap="Blues"); a1.grid(False)
    for (i, j), v in np.ndenumerate(cm):
        a1.text(j, i, f"{v:,}", ha="center", va="center", color="white" if v > cm.max() / 2 else INK)
    a1.set_xticks([0, 1], ["BENIGN", "DDoS"]); a1.set_yticks([0, 1], ["BENIGN", "DDoS"])
    a1.set_xlabel("Dự đoán"); a1.set_ylabel("Thực tế"); a1.set_title("Ma trận nhầm lẫn")
    a2.plot(fpr, tpr, color=SERIES[0]); a2.plot([0, 1], [0, 1], color=GRID, linestyle="--", linewidth=1)
    a2.set_xlabel("FPR"); a2.set_ylabel("TPR"); a2.set_title("ROC")
    fig.suptitle(Path(model_path).stem, color=INK2, fontsize=9)
    save(fig, "confusion_roc.png")


def fig_heatmap(pa, scenario="S3"):
    sub = pa[(pa.scenario == scenario) & (pa.method != "Centralized")]
    if sub.empty:
        return
    attack_cols = [c for c in sub.columns if c not in ("method", "scenario", "client", "seed") and c != "BENIGN"]
    sub = sub.assign(row=np.where(sub.method == "Local-only", "Local client " + sub.client.astype(str), sub.method))
    mat = sub.groupby("row")[attack_cols].mean()
    fig, ax = plt.subplots(figsize=(0.7 * len(attack_cols) + 2.5, 0.45 * len(mat) + 1.2))
    im = ax.imshow(mat.values, cmap="Blues", vmin=0, vmax=1, aspect="auto"); ax.grid(False)
    for (i, j), v in np.ndenumerate(mat.values):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="white" if v > 0.6 else INK)
    ax.set_xticks(range(len(attack_cols)), attack_cols, rotation=45, ha="right")
    ax.set_yticks(range(len(mat)), mat.index)
    ax.set_title(f"Recall theo loại tấn công ({scenario})")
    fig.colorbar(im, ax=ax, fraction=0.03)
    save(fig, f"heatmap_recall_{scenario}.png")


def fig_latency():
    f = paths.RESULTS / "lab_latency.csv"
    if not f.exists():
        return
    d = pd.read_csv(f).dropna(subset=["latency_s"])
    methods = list(d.method.unique())
    fig, ax = plt.subplots(figsize=(6, 3.2))
    bp = ax.boxplot([d[d.method == m]["latency_s"] for m in methods], patch_artist=True)
    ax.set_xticks(range(1, len(methods) + 1), methods)
    for i, b in enumerate(bp["boxes"]):
        b.set(facecolor=SERIES[i], alpha=0.6, edgecolor=INK2)
    ax.set_ylabel("Độ trễ phát hiện (giây)")
    save(fig, "latency_boxplot.png")


def summary(fl, base, pa):
    # F1/Recall/FPR/AUC lấy ở vòng cuối; "F1 tốt nhất (vòng)" cho thấy mô hình có bị suy giảm về cuối không.
    lines = ["| Phương pháp | Kịch bản | F1 | Recall | FPR | AUC | F1 tốt nhất (vòng) | Vòng để F1 ≥ 0,95 "
             "| MB truyền | Recall SYN | Recall PortScan |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda s: f"{s.mean():.4f} ± {s.std():.4f}" if len(s) > 1 else f"{s.mean():.4f}"  # noqa: E731

    def attack(method, sc, col):
        if pa.empty or col not in pa.columns:
            return "—"
        sel = pa[(pa.method == method) & (pa.scenario == sc)]
        if method == "Local-only":
            sel = sel.groupby("seed")[col].mean()  # TB các client trong mỗi seed
        else:
            sel = sel[col]
        return fmt(sel) if len(sel) else "—"
    if not base.empty:
        for (m, sc), g in base[base.client.astype(str).isin(["all", "mean"])].groupby(["method", "scenario"]):
            lines.append(f"| {m} | {sc} | {fmt(g.f1)} | {fmt(g.recall)} | {fmt(g.fpr)} | {fmt(g.auc)} | — | — | — "
                         f"| {attack(m, sc, 'SYN')} | {attack(m, sc, 'PortScan')} |")
    if not fl.empty:
        last = final_round(fl)
        for (m, sc), g in last.groupby(["method", "scenario"]):
            full = fl[(fl.method == m) & (fl.scenario == sc) & (fl["round"] > 0)]
            reach = full[full.f1 >= 0.95].groupby("seed")["round"].min()
            r = f"{reach.mean():.1f}" if len(reach) else "chưa đạt"
            best = full.loc[full.groupby("seed")["f1"].idxmax()]
            b = f"{best.f1.mean():.4f} ({best['round'].mean():.0f})"
            lines.append(f"| {m} | {sc} | {fmt(g.f1)} | {fmt(g.recall)} | {fmt(g.fpr)} | {fmt(g.auc)} | {b} | {r} | "
                         f"{g.comm_MB.mean():.2f} | {attack(m, sc, 'SYN')} | {attack(m, sc, 'PortScan')} |")
    out = paths.RESULTS / "summary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"  {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="global.pt dùng cho ma trận nhầm lẫn + ROC (mặc định: file mới nhất)")
    a = ap.parse_args()
    fl = load_fl()
    base = pd.read_csv(paths.RESULTS / "baselines.csv") if (paths.RESULTS / "baselines.csv").exists() else pd.DataFrame()
    pa = pd.read_csv(paths.RESULTS / "per_attack.csv") if (paths.RESULTS / "per_attack.csv").exists() else pd.DataFrame()
    if not fl.empty:
        fig_f1_vs_round(fl)
    fig_bar(fl, base)
    models = sorted(glob.glob(str(paths.RESULTS / "fl" / "*_global.pt")), key=lambda f: Path(f).stat().st_mtime)
    if a.model or models:
        fig_confusion_roc(a.model or models[-1])
    if not pa.empty:
        for sc in sorted(pa.scenario.unique()):
            fig_heatmap(pa, sc)
    fig_latency()
    summary(fl, base, pa)


if __name__ == "__main__":
    main()
