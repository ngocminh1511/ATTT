"""Mục 8.3–8.4: bảng kết quả và các hình cho báo cáo.

Đọc:  {results}/fl/*.csv (log từng vòng của server), baselines.csv, per_attack.csv
Ghi:  {results}/figures/*.png và {results}/summary.md
  python analysis/plots.py                                              # pipeline paper: data_paper/, results_paper/
  python analysis/plots.py --data-dir data --results-dir results        # pipeline cũ
  python analysis/plots.py --model results_paper/fl/paper_resvgg_swin_mu0.0_fedavg_seed0_global.pt
Với dữ liệu đa lớp có thêm confusion_multiclass.png (hàng = nhãn thật trên test, kể cả lớp chưa gặp lúc train).
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
from fl_ddos.task import method_label  # noqa: E402  (các hàm khác của task nạp lười, sau paths.configure)

# Bảng màu categorical cố định (thứ tự không đổi), mực chữ trung tính, lưới nhạt.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948",
          "#777777", "#8c564b"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": GRID,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    "legend.frameon": False, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
})
def fig_dir() -> Path:
    return paths.RESULTS / "figures"


def load_fl():
    # *_clients.csv là log từng client (cấu trúc khác), không gộp vào đây
    files = [f for f in glob.glob(str(paths.RESULTS / "fl" / "*.csv")) if not f.endswith("_clients.csv")]
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["poison"] = df["poison"].fillna("").astype(str)
    df["arch"] = df["arch"].fillna("mlp") if "arch" in df.columns else "mlp"
    df["method"] = [method_label(m, s, p, a) for m, s, p, a in zip(df["mu"], df["strategy"], df["poison"], df["arch"])]
    return df


def save(fig, name, tight=True):
    fig_dir().mkdir(parents=True, exist_ok=True)
    if tight:
        fig.tight_layout()
    fig.savefig(fig_dir() / name, dpi=200)
    plt.close(fig)
    print(f"  {fig_dir() / name}")


def is_central(m: str) -> bool:
    return "Centralized" in m


def is_local(m: str) -> bool:
    return "Local-only" in m


METHOD_ORDER = ["Local-only", "FedAvg", "FedProx μ=0.01", "FedProx μ=0.1", "Centralized"]


def display_method(method: str) -> str:
    """Log cũ lược tên MLP; luôn ghi cả mô hình và cách học khi trình bày."""
    return method if " · " in method else f"MLP · {method}"


def color_map(methods) -> dict:
    """Màu đi theo phương pháp (không theo thứ hạng/panel): cố định thứ tự, không quay vòng."""
    ordered = [m for m in METHOD_ORDER if m in methods] + sorted(set(methods) - set(METHOD_ORDER))
    palette = SERIES if len(ordered) <= len(SERIES) else [
        matplotlib.colors.to_hex(c) for c in matplotlib.colormaps["tab20"].resampled(len(ordered))(range(len(ordered)))
    ]
    return dict(zip(ordered, palette))


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
    axes[0][0].set_ylabel("F1 nhị phân trên test")
    handles = [plt.Line2D([], [], color=c, lw=2) for c in colors.values()]
    fig.legend(handles, [display_method(m) for m in colors], loc="lower center", ncol=min(len(colors), 4),
               bbox_to_anchor=(0.5, -0.02))
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
    central = d[d.method.map(is_central)]
    scen = [s for s in ["paper", "S1", "S3"] if s in set(d.scenario)]
    d = d[d.scenario.isin(scen) & ~d.method.map(is_central)]
    order = [m for m in colors if m in set(d.method)]
    if not order:
        return
    fig, ax = plt.subplots(figsize=(max(7, 1.2 * len(order) * len(scen)), 3.6))
    width = 0.8 / max(len(order), 1)
    for i, m in enumerate(order):
        x, mean, std = [], [], []
        for j, sc in enumerate(scen):
            g = d[(d.method == m) & (d.scenario == sc)]["f1"]
            if len(g):
                x.append(j + (i - (len(order) - 1) / 2) * width)
                mean.append(g.mean()); std.append(g.std() if len(g) > 1 else 0)
        ax.bar(x, mean, width - 0.02, yerr=std, color=colors[m], label=display_method(m),
               error_kw={"ecolor": INK2, "lw": 1})
    for m, g in central.groupby("method"):  # baseline thực nghiệm, không bảo đảm là cận trên
        ax.axhline(g.f1.mean(), color=INK2, linestyle="--", linewidth=1.2,
                   label=f"{display_method(m)} ({g.f1.mean():.3f})")
    ax.set_xticks(range(len(scen))); ax.set_xticklabels(scen); ax.set_ylabel("F1 nhị phân trên test"); ax.set_ylim(0, 1.08)
    ax.legend(ncol=min(len(order), 3), loc="upper center", bbox_to_anchor=(0.5, -0.1))
    save(fig, "bar_f1.png")


def load_model(model_path):
    """Đọc .pt mới ({"arch", "dropout", "state_dict"}) hoặc state_dict trần của pipeline cũ (MLP)."""
    from fl_ddos.task import make_model
    ckpt = torch.load(model_path, map_location="cpu")
    if "state_dict" in ckpt:
        model = make_model(ckpt.get("arch", "mlp"), float(ckpt.get("dropout", 0.3)))
        model.load_state_dict(ckpt["state_dict"])
    else:
        model = make_model("mlp")
        model.load_state_dict(ckpt)
    return model


def draw_matrix(ax, mat, xlabels, ylabels, fmt):
    ax.imshow(mat, cmap="Blues", vmin=0, aspect="auto"); ax.grid(False)
    top = np.nanmax(mat) if mat.size else 1
    for (i, j), v in np.ndenumerate(mat):
        ax.text(j, i, fmt(v), ha="center", va="center", fontsize=7 if mat.shape[1] > 4 else 9,
                color="white" if v > top / 2 else INK)
    rot = len(xlabels) > 4
    ax.set_xticks(range(len(xlabels)), xlabels, rotation=45 if rot else 0, ha="right" if rot else "center")
    ax.set_yticks(range(len(ylabels)), ylabels)
    ax.set_xlabel("Dự đoán"); ax.set_ylabel("Thực tế")


def fig_confusion_roc(model_path):
    from fl_ddos.task import classes, load_global_test, p_attack, predict, test_labels
    y, P, _ = predict(load_model(model_path), load_global_test(), "cpu")
    yb, p = (y != 0).astype(int), p_attack(P)
    cm = confusion_matrix(yb, (p >= 0.5).astype(int), labels=[0, 1])
    fpr, tpr, _ = roc_curve(yb, p)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.4))
    draw_matrix(a1, cm, ["BENIGN", "Tấn công"], ["BENIGN", "Tấn công"], lambda v: f"{v:,}")
    a1.set_title("Ma trận nhầm lẫn (nhị phân)")
    a2.plot(fpr, tpr, color=SERIES[0]); a2.plot([0, 1], [0, 1], color=GRID, linestyle="--", linewidth=1)
    a2.set_xlabel("FPR"); a2.set_ylabel("TPR"); a2.set_title("ROC (tấn công vs BENIGN)")
    fig.suptitle(Path(model_path).stem, color=INK2, fontsize=9)
    save(fig, "confusion_roc.png")

    cls = classes()
    if len(cls) <= 2:
        return
    # Hàng = nhãn thật trên test (kể cả lớp chưa gặp lúc train, vd. PortScan), cột = lớp dự đoán.
    # Chuẩn hóa theo hàng: ô (i, j) = tỉ lệ mẫu loại i bị gán thành lớp j.
    truth, pred = test_labels(), np.array(cls)[P.argmax(1)]
    rows = [c for c in cls if c in set(truth)] + sorted(set(truth) - set(cls))
    mat = pd.crosstab(pd.Categorical(truth, rows), pd.Categorical(pred, cls), normalize="index", dropna=False)
    fig, ax = plt.subplots(figsize=(0.55 * len(cls) + 2.5, 0.45 * len(rows) + 1.6))
    draw_matrix(ax, mat.values, cls, [f"{r} ({(truth == r).sum():,})" for r in rows],
                lambda v: f"{v:.2f}" if v >= 0.005 else "")
    ax.set_title("Ma trận nhầm lẫn đa lớp (chuẩn hóa theo hàng)")
    fig.suptitle(Path(model_path).stem, color=INK2, fontsize=9)
    save(fig, "confusion_multiclass.png")


def fig_heatmap(pa, scenario="S3"):
    sub = pa[(pa.scenario == scenario) & ~pa.method.map(is_central)]
    if sub.empty:
        return
    attack_cols = [c for c in sub.columns if c not in ("method", "scenario", "client", "seed") and c != "BENIGN"]
    sub = sub.assign(row=np.where(sub.method.map(is_local), sub.method + " · client " + sub.client.astype(str),
                                  sub.method))
    mat = sub.groupby("row")[attack_cols].mean()
    fig, ax = plt.subplots(figsize=(0.7 * len(attack_cols) + 2.5, 0.45 * len(mat) + 1.2))
    im = ax.imshow(mat.values, cmap="Blues", vmin=0, vmax=1, aspect="auto"); ax.grid(False)
    for (i, j), v in np.ndenumerate(mat.values):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="white" if v > 0.6 else INK)
    ax.set_xticks(range(len(attack_cols)), attack_cols, rotation=45, ha="right")
    ax.set_yticks(range(len(mat)), [display_method(m) for m in mat.index])
    ax.set_title(f"Tỉ lệ phát hiện theo loại tấn công ({scenario})")
    fig.colorbar(im, ax=ax, fraction=0.03)
    save(fig, f"heatmap_recall_{scenario}.png")


def summary(fl, base, pa):
    # F1/Recall/FPR/AUC (phát hiện nhị phân) lấy ở vòng cuối; MSI/F1-macro là metric đa lớp của paper.
    # "F1 tốt nhất (vòng)" cho thấy mô hình có bị suy giảm về cuối không.
    lines = ["| Phương pháp | Kịch bản | F1 | Recall | FPR (FAR) | AUC | MSI | F1-macro | F1 tốt nhất (vòng) "
             "| Vòng để F1 ≥ 0,95 | MB truyền | Recall SYN | Recall PortScan |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda s: f"{s.mean():.4f} ± {s.std():.4f}" if len(s) > 1 else f"{s.mean():.4f}"  # noqa: E731

    def col(g, c):
        return fmt(g[c].dropna()) if c in g.columns and g[c].notna().any() else "—"

    def attack(method, sc, c):
        if pa.empty or c not in pa.columns:
            return "—"
        sel = pa[(pa.method == method) & (pa.scenario == sc)]
        sel = (sel.groupby("seed")[c].mean() if is_local(method) else sel[c]).dropna()  # Local-only: TB client mỗi seed
        return fmt(sel) if len(sel) else "—"
    if not base.empty:
        for (m, sc), g in base[base.client.astype(str).isin(["all", "mean"])].groupby(["method", "scenario"]):
            lines.append(f"| {display_method(m)} | {sc} | {fmt(g.f1)} | {fmt(g.recall)} | {fmt(g.fpr)} | {fmt(g.auc)} | {col(g, 'msi')} "
                         f"| {col(g, 'f1_macro')} | — | — | — | {attack(m, sc, 'SYN')} | {attack(m, sc, 'PortScan')} |")
    if not fl.empty:
        last = final_round(fl)
        for (m, sc), g in last.groupby(["method", "scenario"]):
            full = fl[(fl.method == m) & (fl.scenario == sc) & (fl["round"] > 0)]
            reach = full[full.f1 >= 0.95].groupby("seed")["round"].min()
            r = f"{reach.mean():.1f}" if len(reach) else "chưa đạt"
            best = full.loc[full.groupby("seed")["f1"].idxmax()]
            b = f"{best.f1.mean():.4f} ({best['round'].mean():.0f})"
            lines.append(f"| {display_method(m)} | {sc} | {fmt(g.f1)} | {fmt(g.recall)} | {fmt(g.fpr)} | {fmt(g.auc)} | {col(g, 'msi')} "
                         f"| {col(g, 'f1_macro')} | {b} | {r} | {g.comm_MB.mean():.2f} "
                         f"| {attack(m, sc, 'SYN')} | {attack(m, sc, 'PortScan')} |")
    out = paths.RESULTS / "summary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"  {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(paths.ROOT / "data_paper"))
    ap.add_argument("--results-dir", default=str(paths.ROOT / "results_paper"))
    ap.add_argument("--model", help="global.pt dùng cho ma trận nhầm lẫn + ROC (mặc định: file mới nhất)")
    a = ap.parse_args()
    paths.configure(a.data_dir, a.results_dir)
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
    summary(fl, base, pa)


if __name__ == "__main__":
    main()
