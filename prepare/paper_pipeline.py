"""Pipeline dữ liệu theo paper (mục 3.2–3.6) cho CIC-DDoS2019, đa lớp.

Thứ tự (như paper): log1p -> TEC -> chia client (Eq.13) -> AFN -> CTA -> DPCA -> MTB -> DAS -> NDS/JAA -> DRA -> LIS.
AFN, DAS, DRA, LIS dùng thống kê liên kết (client gửi tổng, server gộp); CTA, DPCA, MTB chạy cục bộ.
Tập test chỉ đi qua các phép biến đổi đã fit trên train (không sinh/bớt mẫu).

Output (--out, mặc định data_paper/):
  features.json            {"pipeline": "paper", "features": [...], "classes": [...], ...}
  prep_params.json         relevance DAS của mọi đặc trưng, min/max DRA, hệ số LIS (cho báo cáo)
  {scenario}/client_k.parquet, mtb_weights.json, summary.csv (số mẫu trước/sau DPCA)
  test_day2.parquet        --split day: ngày 11/03; --split random: 20% ngày 12/01 (giống paper)

Ví dụ (bản Kaggle dhoogla/cicddos2019, tên file bị đảo: *-testing = ngày 12/01):
  python prepare/paper_pipeline.py
  python prepare/paper_pipeline.py --split random --out data_paper_random
  python prepare/paper_pipeline.py --afn label --out data_paper_leak     # minh họa rò rỉ nhãn
"""
import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import paper_prep as pp  # noqa: E402
from fl_ddos import paths  # noqa: E402
from fl_ddos.features import normalize_label, slog1p  # noqa: E402
from preprocess_csv import DROP, iter_frames, snake  # noqa: E402

META = ["label", "file_id", "t_order"]
TEC_BASE = ["flow_packets_s", "flow_bytes_s", "flow_iat_mean"]


def load_day(pattern, cap, keep_all_benign, tau, file_offset, rng):
    """Đọc từng file, tính TEC trên toàn bộ dòng của file (trước khi lấy mẫu), rồi giới hạn mỗi nhãn ≤ cap."""
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"Không tìm thấy file nào khớp: {pattern}")
    parts = []
    for i, f in enumerate(files):
        df = pd.concat(list(iter_frames(f, 500_000)), ignore_index=True)
        df.columns = [snake(c) for c in df.columns]
        df = df.drop(columns=[c for c in df.columns if c in DROP])
        label = df.pop("label").astype(str).map(normalize_label)
        num = df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        num = pd.DataFrame(slog1p(num.values), columns=num.columns, index=num.index)
        num["label"], num["file_id"], num["t_order"] = label.values, file_offset + i, np.arange(len(num))
        num = num.dropna()
        tec_cols = [c for c in TEC_BASE if c in num.columns]
        parts.append(pd.concat([num, pp.tec(num, tec_cols, tau)], axis=1))
        print(f"  đọc {Path(f).name}: {len(num)} dòng")
    df = pd.concat(parts, ignore_index=True)
    out = []
    for lab, g in df.groupby("label"):
        if not (lab == "BENIGN" and keep_all_benign) and len(g) > cap:
            g = g.sample(cap, random_state=int(rng.integers(1 << 31)))
        out.append(g)
    return pd.concat(out).sort_values(["file_id", "t_order"]).reset_index(drop=True)


def stratified_split(labels, k, rng):
    """Eq.13: X_i = X/k, mỗi phần giữ phân phối nhãn như tập gốc."""
    parts = [[] for _ in range(k)]
    for lab in np.unique(labels):
        idx = rng.permutation(np.where(labels == lab)[0])
        for i, chunk in enumerate(np.array_split(idx, k)):
            parts[i].extend(chunk.tolist())
    return [np.sort(p) for p in parts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-glob", default=str(paths.ROOT / "data/raw/cicddos2019/*-testing.parquet"))
    ap.add_argument("--test-glob", default=str(paths.ROOT / "data/raw/cicddos2019/*-training.parquet"))
    ap.add_argument("--split", choices=["day", "random"], default="day")
    ap.add_argument("--max-per-attack", type=int, default=30_000)
    ap.add_argument("--max-test-per-label", type=int, default=30_000)
    ap.add_argument("--n-clients", type=int, default=3, help="paper: 3 client cho mỗi dataset (Bảng 6)")
    ap.add_argument("--scenario", default="paper")
    ap.add_argument("--afn", choices=["protocol", "global", "label"], default="protocol")
    ap.add_argument("--tec-tau", type=int, default=10)
    ap.add_argument("--cta-ratio", type=float, default=0.2, help="0 = tắt CTA")
    ap.add_argument("--cta-window", type=int, default=10)
    ap.add_argument("--no-dpca", action="store_true")
    ap.add_argument("--n-features", type=int, default=25)
    ap.add_argument("--theta", type=float, default=1e-3, help="ngưỡng relevance tối thiểu (Eq.9)")
    ap.add_argument("--gamma", type=float, default=0.9, help="ngưỡng phụ thuộc giữa hai đặc trưng (Eq.9)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(paths.ROOT / "data_paper"))
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    out = Path(a.out)
    (out / a.scenario).mkdir(parents=True, exist_ok=True)

    print("[1/7] Đọc dữ liệu + TEC (Eq.11)")
    train = load_day(a.train_glob, a.max_per_attack, True, a.tec_tau, 0, rng)
    if a.split == "day":
        test = load_day(a.test_glob, a.max_test_per_label, False, a.tec_tau, 1000, rng)
    else:  # giống paper: chia ngẫu nhiên trong cùng một ngày
        te = stratified_split(train["label"].values, 5, rng)[0]
        test, train = train.loc[te].reset_index(drop=True), train.drop(index=te).reset_index(drop=True)
    tec_cols = [c for c in train.columns if c.startswith("tec_")]
    cand = [c for c in train.columns if c not in META and c not in tec_cols and train[c].nunique() > 1]
    afn_cols = [c for c in cand + tec_cols if c != "protocol"]  # protocol là khóa nhóm, giữ nguyên
    classes = ["BENIGN"] + sorted(set(train["label"]) - {"BENIGN"})
    cidx = {c: i for i, c in enumerate(classes)}
    print(f"  {len(cand)} đặc trưng ứng viên, {len(classes)} lớp: {classes}")

    print(f"[2/7] Chia {a.n_clients} client (Eq.13)")
    clients = [train.iloc[p].reset_index(drop=True) for p in stratified_split(train["label"].values, a.n_clients, rng)]

    print(f"[3/7] AFN theo nhóm '{a.afn}' (Eq.1), thống kê liên kết")
    afn = pp.aggregate_afn([pp.afn_stats(c[afn_cols].values, pp.afn_groups(c, a.afn)) for c in clients])
    for d in clients + [test]:
        d[afn_cols] = pp.apply_afn(d[afn_cols].values, pp.afn_groups(d, a.afn), afn)

    print("[4/7] CTA (Eq.2) + DPCA = WIS/FBSA (Eq.4–6) + MTB (Eq.3), cục bộ tại từng client")
    cols = cand + tec_cols
    summary, mtb, local = {}, {}, []
    for k, c in enumerate(clients, 1):
        x, y, t = c[cols].values, c["label"].map(cidx).values, (c["file_id"] * 1e7 + c["t_order"]).values
        before = np.bincount(y, minlength=len(classes))
        if a.cta_ratio > 0:
            xa, ya, ta = pp.cta(x, y, t, a.cta_ratio, a.cta_window, rng)
            x, y, t = np.concatenate([x, xa]), np.concatenate([y, ya]), np.concatenate([t, ta])
        if not a.no_dpca:
            x, y, t = pp.dpca(x, y, t, rng)
        after = np.bincount(y, minlength=len(classes))
        summary[f"client_{k}_before"], summary[f"client_{k}_after"] = before, after
        mtb[f"client_{k}"] = pp.mtb_weights(y, t, len(classes))
        local.append((pd.DataFrame(x, columns=cols), y, t))

    print("[5/7] DAS = CRA + IDF (Eq.7–9), thống kê liên kết")
    das = pp.aggregate_das([pp.das_stats(d[cand].values, y, len(classes)) for d, y, _ in local],
                           a.n_features, a.theta, a.gamma)
    selected = [cand[i] for i in das["selected"]]
    print("  chọn:", selected)

    print("[6/7] FDP: NDS (Eq.10) + JAA (Eq.12); TEC đã tính ở bước 1")
    frames = [pd.concat([d[selected + tec_cols], pp.fdp(d, selected)], axis=1) for d, _, _ in local]
    test_x = pd.concat([test[selected + tec_cols], pp.fdp(test, selected)], axis=1)
    feats = list(frames[0].columns)

    print("[7/7] FRP = DRA (Eq.14) + LIS (Eq.15), thống kê liên kết")
    dra = pp.aggregate_dra([pp.dra_stats(f.values) for f in frames])
    scaled = [pp.apply_dra(f.values, dra) for f in frames]
    lis = pp.aggregate_lis([pp.lis_stats(s, (y != 0).astype(float)) for s, (_, y, _) in zip(scaled, local)])

    def finish(x, y, labels, t):
        df = pd.DataFrame((x * lis["lambda"]).astype(np.float32), columns=feats)
        df["label"], df["y"], df["binary"], df["t_order"] = labels, y, (labels != "BENIGN").astype(np.int64), t
        return df

    for k, (s, (_, y, t)) in enumerate(zip(scaled, local), 1):
        finish(s, y, np.array(classes)[y], t).to_parquet(out / a.scenario / f"client_{k}.parquet", index=False)
    ty = test["label"].map(cidx).fillna(-100).astype(np.int64).values  # lớp chưa gặp lúc train -> bỏ qua trong loss
    finish(pp.apply_dra(test_x.values, dra), ty, test["label"].values,
           (test["file_id"] * 1e7 + test["t_order"]).values).to_parquet(out / "test_day2.parquet", index=False)

    s = pd.DataFrame(summary, index=classes)
    s.loc["TOTAL"] = s.sum()
    s.to_csv(out / a.scenario / "summary.csv")
    json.dump(mtb, open(out / a.scenario / "mtb_weights.json", "w"), indent=2)
    json.dump({"pipeline": "paper", "features": feats, "classes": classes, "split": a.split, "afn": a.afn,
               "selected": selected, "tec": tec_cols, "derived": feats[len(selected) + len(tec_cols):]},
              open(out / "features.json", "w", encoding="utf-8"), indent=2)
    json.dump({"candidates": cand, "relevance": das["relevance"], "dra_min": dra["min"].tolist(),
               "dra_max": dra["max"].tolist(), "lis_lambda": lis["lambda"].tolist(), "args": vars(a)},
              open(out / "prep_params.json", "w", encoding="utf-8"), indent=2)
    print(f"\n{s.to_string()}\n\n  {len(feats)} đặc trưng cuối -> {out}")
    print("  test:", test["label"].value_counts().to_dict())
    unseen = sorted(set(test["label"]) - set(classes))
    if unseen:
        print(f"  Lớp chỉ có ở test (chỉ tính vào phát hiện nhị phân): {unseen}")


if __name__ == "__main__":
    main()
