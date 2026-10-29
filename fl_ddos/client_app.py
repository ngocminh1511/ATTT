"""Mục 6.4: FL client (một chi nhánh / bên giữ dữ liệu; client ảo khi simulation).

Chỉ trọng số mô hình và số mẫu được gửi lên server; dữ liệu cục bộ không rời node.
Kèm theo các số đo chi phí cục bộ cho bảng 6/8 của paper: thời gian train, bộ nhớ đỉnh, ‖Δw‖.
"""
import time

import torch
from flwr.app import ArrayRecord, Context, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp

from fl_ddos import paths
from fl_ddos.task import evaluate as eval_fn, load_local, make_model, mtb_weights, set_seed, train as train_fn

app = ClientApp()
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _setup(msg: Message, context: Context):
    rc = context.run_config
    paths.configure(str(rc.get("data-dir", "")), str(rc.get("results-dir", "")))
    pid = int(context.node_config["partition-id"])
    model = make_model(str(rc.get("arch", "mlp")), float(rc.get("dropout", 0.3)))
    model.load_state_dict(msg.content["arrays"].to_torch_state_dict())  # nhận model toàn cục
    return rc, pid, model


@app.train()
def train(msg: Message, context: Context):
    rc, pid, model = _setup(msg, context)
    poisoned = str(pid) in str(rc.get("poison-clients", "")).split(",")
    set_seed(int(rc["seed"]) + pid)
    trainloader, _ = load_local(pid, rc["scenario"], rc["batch-size"], int(rc["seed"]), poison=poisoned)
    w0 = torch.cat([p.detach().flatten() for p in model.parameters()])
    if DEVICE.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    loss = train_fn(model, trainloader, rc["local-epochs"], msg.content["config"]["lr"],
                    rc["proximal-mu"], DEVICE, mtb_weights(pid, rc["scenario"]))
    elapsed = time.perf_counter() - t0
    w1 = torch.cat([p.detach().flatten().cpu() for p in model.parameters()])
    reply = RecordDict({
        "arrays": ArrayRecord(model.state_dict()),  # chỉ gửi trọng số
        "metrics": MetricRecord({
            "train_loss": loss, "num-examples": len(trainloader.dataset), "partition-id": pid,
            "train_time_s": elapsed, "update_norm": float((w1 - w0.cpu()).norm()),
            "peak_mem_MB": torch.cuda.max_memory_allocated() / 2**20 if DEVICE.type == "cuda" else 0.0}),
    })
    return Message(content=reply, reply_to=msg)


@app.evaluate()
def evaluate(msg: Message, context: Context):
    rc, pid, model = _setup(msg, context)
    _, valloader = load_local(pid, rc["scenario"], rc["batch-size"], int(rc["seed"]))
    m = eval_fn(model, valloader, DEVICE)
    metrics = MetricRecord({"eval_f1": m["f1"], "eval_acc": m["acc"], "eval_recall": m["recall"],
                            "eval_f1_macro": m["f1_macro"], "eval_msi": m["msi"],
                            "partition-id": pid, "num-examples": len(valloader.dataset)})
    return Message(content=RecordDict({"metrics": metrics}), reply_to=msg)
