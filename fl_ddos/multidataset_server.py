"""Server FL cho pipeline multidataset_v1 (kế hoạch mục 8): 3 client = 3 nguồn, FedAvg theo số mẫu train thật.

Mỗi vòng: train cục bộ -> kiểm tra đủ đúng PID 0/1/2, cùng round -> FedAvg -> gửi model đã gộp về ba
client đánh giá trên validation riêng -> điểm chọn model = TB đều F1-macro-present của ba validation.
evaluate_fn chỉ đọc điểm validation đã gộp của đúng vòng đó (Flower gọi aggregate_evaluate trước
evaluate_fn); không có lượt đọc test nào ở đây. Vòng 0 chỉ ghi trạng thái khởi tạo.

Output trong {results}/fl/:
  {tag}_best.pt / {tag}_last.pt   checkpoint + metadata (round, điểm validation, seed, run config, hash)
  {tag}_rounds.csv                mỗi vòng: điểm validation từng nguồn, metric train đã gộp
  {tag}_clients.csv               mỗi vòng × client: train (loss, số mẫu, thời gian…) và validation
  {tag}_pid_map.json              partition-id -> dataset
"""
from __future__ import annotations

import csv
import json
import math

import numpy as np
import torch
from flwr.app import ArrayRecord, ConfigRecord, Context, MetricRecord, RecordDict
from flwr.serverapp import Grid
from flwr.serverapp.strategy import FedAvg

from fl_ddos import paths
from fl_ddos.multidataset_prep import dump_json, read_json
from fl_ddos.task import classes, features, make_model, meta, set_seed

EXPECTED_PIDS = (0, 1, 2)


class FLRunError(RuntimeError):
    pass


def _rows(replies) -> list[dict]:
    return [dict(m.content["metrics"]) for m in replies]


class MultiSourceFedAvg(FedAvg):
    """FedAvg + kiểm tra đủ phản hồi và lưu điểm validation theo vòng."""

    def __init__(self, expected_pids=EXPECTED_PIDS, **kw):
        super().__init__(**kw)
        self.expected = sorted(expected_pids)
        self.val_by_round: dict[int, dict] = {}
        self.client_log: list[dict] = []

    def _require_complete(self, server_round: int, replies: list, kind: str):
        valid, errors = self._check_and_log_replies(replies, is_train=(kind == "train"))
        if errors:
            raise FLRunError(f"Vòng {server_round} ({kind}): {len(errors)} client trả lỗi -> dừng, không ghi kết quả")
        ms = _rows(valid)
        pids = sorted(int(m["partition-id"]) for m in ms)
        if pids != self.expected:
            raise FLRunError(f"Vòng {server_round} ({kind}): PID nhận được {pids}, cần đúng {self.expected}")
        rounds = {int(m.get("server-round", -1)) for m in ms}
        if rounds != {server_round}:
            raise FLRunError(f"Vòng {server_round} ({kind}): phản hồi mang round {sorted(rounds)}")
        return ms

    def aggregate_train(self, server_round, replies):
        replies = list(replies)
        ms = self._require_complete(server_round, replies, "train")
        for m in ms:
            self.client_log.append({"round": server_round, "phase": "train", **m})
        return super().aggregate_train(server_round, replies)

    def aggregate_evaluate(self, server_round, replies):
        replies = list(replies)
        ms = self._require_complete(server_round, replies, "evaluate")
        per = {int(m["partition-id"]): float(m["eval_f1_macro_present"]) for m in ms}
        if not all(math.isfinite(v) for v in per.values()):
            raise FLRunError(f"Vòng {server_round}: F1-macro-present validation không hữu hạn {per}")
        score = float(np.mean([per[p] for p in self.expected]))
        self.val_by_round[server_round] = {"val_score": score, **{f"val_f1mp_pid{p}": per[p] for p in self.expected}}
        for m in ms:
            self.client_log.append({"round": server_round, "phase": "val", **m})
        out = dict(self.val_by_round[server_round])
        out["val_acc_mean"] = float(np.mean([float(m["eval_acc"]) for m in ms]))
        return MetricRecord(out)


def _train_aggr(replies: list[RecordDict], weighting_key: str) -> MetricRecord:
    ms = [dict(r["metrics"]) for r in replies]
    w = np.array([m[weighting_key] for m in ms], dtype=float)
    keys = ("train_loss", "train_time_s", "update_norm", "peak_mem_MB")
    return MetricRecord({k: float(np.average([m[k] for m in ms], weights=w)) for k in keys} |
                        {"num_examples_total": float(w.sum())})


def _write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def pid_map() -> dict:
    f = paths.DATA / "dataset_manifest.json"
    if not f.exists():
        raise FLRunError(f"Thiếu {f}")
    clients = read_json(f)["clients"]
    m = {int(c["partition_id"]): c["dataset_id"] for c in clients}
    if sorted(m) != list(EXPECTED_PIDS) or len(set(m.values())) != len(m):
        raise FLRunError(f"dataset_manifest.json phải khóa PID 0/1/2 với ba nguồn khác nhau: {m}")
    return m


def checkpoint(state, arch, dropout, rnd, score, seed, rc: dict, kind: str) -> dict:
    md = meta()
    return {"arch": arch, "dropout": dropout, "state_dict": state, "kind": kind, "pipeline": md["pipeline"],
            "classes": classes(), "features": features(), "round": rnd, "val_score": score,
            "val_metric": "mean over sources of F1-macro-present (validation)", "seed": seed,
            "run_config": rc, "hashes": md.get("hashes", {}), "profile": md.get("profile")}


def run_multidataset(grid: Grid, context: Context) -> None:
    rc = {k: v for k, v in context.run_config.items()}
    seed, arch, dropout = int(rc["seed"]), str(rc.get("arch", "resvgg_swin")), float(rc.get("dropout", 0.3))
    n_clients, n_rounds = int(rc["num-clients"]), int(rc["num-server-rounds"])
    if n_clients != len(EXPECTED_PIDS):
        raise FLRunError(f"multidataset_v1 cần đúng 3 client, run config có num-clients={n_clients}")
    if float(rc.get("proximal-mu", 0)) or str(rc.get("strategy", "fedavg")) != "fedavg" or rc.get("poison-clients"):
        raise FLRunError("multidataset_v1 chỉ hỗ trợ FedAvg không poison/FedProx trong v1")
    pmap = pid_map()
    tag = f"multidataset_{arch}_seed{seed}" + str(rc.get("tag-suffix", ""))
    out = paths.RESULTS / "fl"
    out.mkdir(parents=True, exist_ok=True)
    dump_json({"pid_to_dataset": pmap, "data_dir": str(paths.DATA)}, out / f"{tag}_pid_map.json")

    set_seed(seed)
    model = make_model(arch, dropout)
    n_params = sum(p.numel() for p in model.parameters())
    strategy = MultiSourceFedAvg(
        fraction_train=1.0, fraction_evaluate=1.0, min_train_nodes=n_clients, min_evaluate_nodes=n_clients,
        min_available_nodes=n_clients, train_metrics_aggr_fn=_train_aggr)
    best = {"round": None, "score": -math.inf, "state": None}

    def select_fn(server_round: int, arrays: ArrayRecord) -> MetricRecord:
        if server_round == 0:
            return MetricRecord({"initial": 1.0})  # chỉ ghi trạng thái khởi tạo, không tham gia chọn best
        v = strategy.val_by_round.get(server_round)
        if v is None:
            raise FLRunError(f"Vòng {server_round}: chưa có điểm validation đã gộp")
        if v["val_score"] > best["score"]:  # hòa -> giữ vòng sớm hơn
            best.update(round=server_round, score=v["val_score"],
                        state={k: t.clone() for k, t in arrays.to_torch_state_dict().items()})
        return MetricRecord({"val_score": v["val_score"], "best_round": float(best["round"]),
                             "comm_MB": server_round * 2 * n_clients * n_params * 4 / 1e6})

    print(f"[server] {tag}: {arch}, {len(classes())} lớp, {len(features())} đặc trưng, {n_params} tham số, "
          f"PID->nguồn {pmap}, {n_rounds} vòng")
    result = strategy.start(grid=grid, initial_arrays=ArrayRecord(model.state_dict()),
                            train_config=ConfigRecord({"lr": rc["lr"]}), num_rounds=n_rounds, evaluate_fn=select_fn)
    done = max(result.evaluate_metrics_serverapp, default=0)
    if len(result.arrays) == 0 or done < n_rounds or best["state"] is None:
        raise FLRunError(f"[server] {tag}: chỉ hoàn tất {done}/{n_rounds} vòng -> không ghi kết quả")

    rows = []
    for rnd in range(1, n_rounds + 1):
        rows.append({"tag": tag, "seed": seed, "arch": arch, "round": rnd, **strategy.val_by_round[rnd],
                     **{f"train_{k}" if not k.startswith("train_") else k: v
                        for k, v in dict(result.train_metrics_clientapp.get(rnd, {})).items()},
                     "comm_MB": dict(result.evaluate_metrics_serverapp[rnd]).get("comm_MB")})
    _write_csv(out / f"{tag}_rounds.csv", rows)
    _write_csv(out / f"{tag}_clients.csv",
               [{**r, "dataset_id": pmap[int(r["partition-id"])]} for r in strategy.client_log])
    last = result.arrays.to_torch_state_dict()
    torch.save(checkpoint(best["state"], arch, dropout, best["round"], best["score"], seed, rc, "best"),
               out / f"{tag}_best.pt")
    torch.save(checkpoint(last, arch, dropout, n_rounds, strategy.val_by_round[n_rounds]["val_score"], seed, rc,
                          "last"), out / f"{tag}_last.pt")
    print(f"[server] Best vòng {best['round']} (validation {best['score']:.4f}) -> {out / tag}_best.pt; "
          f"đánh giá test bằng analysis/evaluate_multidataset.py")
