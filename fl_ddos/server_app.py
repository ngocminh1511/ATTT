"""Mục 6.5: FL server — gộp mô hình (FedAvg hoặc FedTrimmedAvg) và ghi log từng vòng.

FedProx được cài ở phía client (số hạng phạt trong train); phía server vẫn gộp như FedAvg.
Output trong results/fl/:
  {tag}.csv            mỗi vòng: metric trên test ngày 2 + F1 cục bộ TB/độ lệch giữa client + MB truyền
  {tag}_clients.csv    mỗi vòng × client: loss, số mẫu, thời gian train, bộ nhớ đỉnh, ‖Δw‖ (paper Bảng 6, 8)
  {tag}_global.pt      {"arch", "dropout", "state_dict"} của mô hình toàn cục cuối cùng
và một dòng recall theo loại tấn công trong results/per_attack.csv
(đa lớp: thêm results/per_class.csv, recall đúng LOẠI tấn công).
"""
import csv

import numpy as np
import torch
from flwr.app import ArrayRecord, ConfigRecord, Context, MetricRecord, RecordDict
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg, FedTrimmedAvg

from fl_ddos import paths
from fl_ddos.multidataset_server import run_multidataset
from fl_ddos.task import (classes, is_multi, load_global_test, make_model, method_label, metrics, p_attack,
                          per_attack_recall, per_class_recall, predict, set_seed, test_labels)

app = ServerApp()


def append_csv(file, row: dict):
    file.parent.mkdir(parents=True, exist_ok=True)
    new = not file.exists()
    with open(file, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)


def aggregate_client_eval(replies: list[RecordDict], weighting_key: str) -> MetricRecord:
    """TB có trọng số các metric cục bộ + độ lệch F1 giữa các chi nhánh (công bằng, mục 8)."""
    ms = [r["metrics"] for r in replies]
    w = np.array([m[weighting_key] for m in ms], dtype=float)
    f1 = np.array([m["eval_f1"] for m in ms], dtype=float)
    out = {k: float(np.average([m[k] for m in ms], weights=w)) for k in ("eval_f1", "eval_acc", "eval_recall")}
    out.update({"client_f1_std": float(f1.std()), "client_f1_min": float(f1.min())})
    return MetricRecord(out)


def make_train_aggr(log: list):
    """Gộp metric train như mặc định của Flower, đồng thời giữ lại số liệu từng client."""
    def aggr(replies: list[RecordDict], weighting_key: str) -> MetricRecord:
        rnd = 1 + max((r["round"] for r in log), default=0)
        ms = [dict(r["metrics"]) for r in replies]
        log.extend({"round": rnd, **m} for m in ms)
        w = np.array([m[weighting_key] for m in ms], dtype=float)
        keys = ("train_loss", "train_time_s", "update_norm", "peak_mem_MB")
        return MetricRecord({k: float(np.average([m[k] for m in ms], weights=w)) for k in keys})
    return aggr


def make_evaluate_fn(test, n_params, n_clients, arch, dropout):
    def global_evaluate(server_round: int, arrays: ArrayRecord) -> MetricRecord:
        model = make_model(arch, dropout)
        model.load_state_dict(arrays.to_torch_state_dict())
        y, p, loss = predict(model, test, "cpu")
        m = metrics(y, p, loss)
        m["comm_MB"] = server_round * 2 * n_clients * n_params * 4 / 1e6  # lên + xuống, float32
        return MetricRecord(m)
    return global_evaluate


@app.main()
def main(grid: Grid, context: Context) -> None:
    rc = context.run_config
    paths.configure(str(rc.get("data-dir", "")), str(rc.get("results-dir", "")))
    if is_multi():  # 2 client × 2 nguồn: chọn checkpoint bằng validation, không đánh giá test trong lúc train
        return run_multidataset(grid, context)
    seed, mu, sc =int(rc["seed"]), float(rc["proximal-mu"]), str(rc["scenario"])
    strategy_name, poison = str(rc["strategy"]), str(rc.get("poison-clients", ""))
    n_clients = int(rc["num-clients"])
    arch, dropout = str(rc.get("arch", "mlp")), float(rc.get("dropout", 0.3))
    tag = (f"{sc}_{arch}_mu{mu}_{strategy_name}_seed{seed}" + (f"_poison{poison.replace(',', '-')}" if poison else "")
           + str(rc.get("tag-suffix", "")))
    out_dir = paths.RESULTS / "fl"
    out_dir.mkdir(parents=True, exist_ok=True)

    set_seed(seed)
    model = make_model(arch, dropout)
    n_params = sum(p.numel() for p in model.parameters())
    test = load_global_test()
    client_log = []
    common = dict(fraction_train=1.0, fraction_evaluate=1.0,
                  min_train_nodes=n_clients, min_evaluate_nodes=n_clients, min_available_nodes=n_clients,
                  evaluate_metrics_aggr_fn=aggregate_client_eval, train_metrics_aggr_fn=make_train_aggr(client_log))
    strategy = FedTrimmedAvg(beta=0.2, **common) if strategy_name == "trimmed" else FedAvg(**common)
    print(f"[server] {tag}: {arch}, {len(classes())} lớp, {n_params} tham số, {n_clients} client, {rc['num-server-rounds']} vòng")

    result = strategy.start(
        grid=grid,
        initial_arrays=ArrayRecord(model.state_dict()),
        train_config=ConfigRecord({"lr": rc["lr"]}),
        num_rounds=int(rc["num-server-rounds"]),
        evaluate_fn=make_evaluate_fn(test, n_params, n_clients, arch, dropout),
    )

    # Client lỗi (vd. MemoryError khi nạp torch) -> không có trọng số để gộp; không ghi kết quả rỗng
    done = max(result.evaluate_metrics_serverapp, default=0)
    if len(result.arrays) == 0 or done < int(rc["num-server-rounds"]):
        raise RuntimeError(f"[server] {tag}: chỉ hoàn tất {done}/{rc['num-server-rounds']} vòng — "
                           "client lỗi (xem log phía trên, thường do thiếu RAM). Không ghi kết quả.")

    # Ghi log từng vòng (có header) = metric server-side + metric client-side đã gộp
    rows = []
    for rnd, m in sorted(result.evaluate_metrics_serverapp.items()):
        row = {"scenario": sc, "arch": arch, "mu": mu, "strategy": strategy_name, "seed": seed, "poison": poison,
               "round": rnd, **dict(m)}
        row.update({f"train_{k}" if not k.startswith("train_") else k: v
                    for k, v in dict(result.train_metrics_clientapp.get(rnd, {})).items()})
        row.update(dict(result.evaluate_metrics_clientapp.get(rnd, {})))
        rows.append(row)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(out_dir / f"{tag}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    if client_log:
        with open(out_dir / f"{tag}_clients.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in client_log for k in r)))
            w.writeheader()
            w.writerows(client_log)

    state = result.arrays.to_torch_state_dict()
    torch.save({"arch": arch, "dropout": dropout, "state_dict": state}, out_dir / f"{tag}_global.pt")

    model.load_state_dict(state)
    y, P, _ = predict(model, test, "cpu")
    key = {"method": method_label(mu, strategy_name, poison, arch), "scenario": sc, "client": "global", "seed": seed}
    append_csv(paths.RESULTS / "per_attack.csv", {**key, **per_attack_recall(test_labels(), p_attack(P))})
    if len(classes()) > 2:
        append_csv(paths.RESULTS / "per_class.csv", {**key, **per_class_recall(y, P)})
    print(f"[server] Đã lưu {out_dir / tag}.csv và {tag}_global.pt; F1 cuối = {rows[-1]['f1']:.4f}")
