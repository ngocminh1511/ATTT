"""Mục 6.5: FL server — gộp mô hình (FedAvg hoặc FedTrimmedAvg) và ghi log từng vòng.

FedProx được cài ở phía client (số hạng phạt trong train); phía server vẫn gộp như FedAvg.
Output trong results/fl/:
  {tag}.csv            mỗi vòng: metric trên test ngày 2 + F1 cục bộ TB/độ lệch giữa client + MB truyền
  {tag}_global.pt      mô hình toàn cục cuối cùng
và một dòng recall theo loại tấn công trong results/per_attack.csv.
"""
import csv

import numpy as np
import torch
from flwr.app import ArrayRecord, ConfigRecord, Context, MetricRecord, RecordDict
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg, FedTrimmedAvg

from fl_ddos import paths
from fl_ddos.task import (DDoSNet, load_global_test, method_label, metrics, per_attack_recall,
                          predict, set_seed, test_labels)

app = ServerApp()


def aggregate_client_eval(replies: list[RecordDict], weighting_key: str) -> MetricRecord:
    """TB có trọng số các metric cục bộ + độ lệch F1 giữa các chi nhánh (công bằng, mục 8)."""
    ms = [r["metrics"] for r in replies]
    w = np.array([m[weighting_key] for m in ms], dtype=float)
    f1 = np.array([m["eval_f1"] for m in ms], dtype=float)
    out = {k: float(np.average([m[k] for m in ms], weights=w)) for k in ("eval_f1", "eval_acc", "eval_recall")}
    out.update({"client_f1_std": float(f1.std()), "client_f1_min": float(f1.min())})
    return MetricRecord(out)


def make_evaluate_fn(test, n_params, n_clients):
    def global_evaluate(server_round: int, arrays: ArrayRecord) -> MetricRecord:
        model = DDoSNet()
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
    seed, mu, sc = int(rc["seed"]), float(rc["proximal-mu"]), str(rc["scenario"])
    strategy_name, poison = str(rc["strategy"]), str(rc.get("poison-clients", ""))
    n_clients = int(rc["num-clients"])
    tag = f"{sc}_mu{mu}_{strategy_name}_seed{seed}" + (f"_poison{poison.replace(',', '-')}" if poison else "")
    out_dir = paths.RESULTS / "fl"
    out_dir.mkdir(parents=True, exist_ok=True)

    set_seed(seed)
    model = DDoSNet()
    n_params = sum(p.numel() for p in model.parameters())
    test = load_global_test()
    common = dict(fraction_train=1.0, fraction_evaluate=1.0,
                  min_train_nodes=n_clients, min_evaluate_nodes=n_clients, min_available_nodes=n_clients,
                  evaluate_metrics_aggr_fn=aggregate_client_eval)
    strategy = FedTrimmedAvg(beta=0.2, **common) if strategy_name == "trimmed" else FedAvg(**common)
    print(f"[server] {tag}: {n_params} tham số, {n_clients} client, {rc['num-server-rounds']} vòng")

    result = strategy.start(
        grid=grid,
        initial_arrays=ArrayRecord(model.state_dict()),
        train_config=ConfigRecord({"lr": rc["lr"]}),
        num_rounds=int(rc["num-server-rounds"]),
        evaluate_fn=make_evaluate_fn(test, n_params, n_clients),
    )

    # Ghi log từng vòng (có header) = metric server-side + metric client-side đã gộp
    rows = []
    for rnd, m in sorted(result.evaluate_metrics_serverapp.items()):
        row = {"scenario": sc, "mu": mu, "strategy": strategy_name, "seed": seed, "poison": poison,
               "round": rnd, **dict(m)}
        row.update(dict(result.evaluate_metrics_clientapp.get(rnd, {})))
        rows.append(row)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(out_dir / f"{tag}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    state = result.arrays.to_torch_state_dict()
    torch.save(state, out_dir / f"{tag}_global.pt")

    model.load_state_dict(state)
    _, p, _ = predict(model, test, "cpu")
    rec = per_attack_recall(test_labels(), p)
    pa = paths.RESULTS / "per_attack.csv"
    new = not pa.exists()
    with open(pa, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["method", "scenario", "client", "seed", *rec.keys()])
        if new:
            w.writeheader()
        w.writerow({"method": method_label(mu, strategy_name, poison), "scenario": sc,
                    "client": "global", "seed": seed, **rec})
    print(f"[server] Đã lưu {out_dir / tag}.csv và {tag}_global.pt; F1 cuối = {rows[-1]['f1']:.4f}")
