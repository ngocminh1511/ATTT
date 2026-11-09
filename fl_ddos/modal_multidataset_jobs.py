"""Chuẩn bị bundle và lệnh chạy Modal cho multidataset; không cần kết nối Modal khi kiểm thử."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

DATASETS = {0: "cicddos2019", 1: "unsw_nb15"}
VARIANTS = ("das", "all")
POLICY = "class_quota_v3"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_name(profile, variant):
    if profile not in ("smoke", "main") or variant not in VARIANTS:
        raise ValueError(f"Profile/variant không hợp lệ: {profile}/{variant}")
    return profile + ("_all" if variant == "all" else "")


def safe_relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError(f"Đường dẫn artifact không hợp lệ: {name}")
    return path


def build_bundle(data_root: Path) -> dict:
    """Bundle là đúng các artifact đã chốt, không tải raw hoặc chuẩn bị lại trên cloud."""
    datasets, files = {}, {}
    for profile in ("smoke", "main"):
        for variant in VARIANTS:
            name = data_name(profile, variant)
            folder = data_root / name
            md, manifest, quality = (read_json(folder / f) for f in
                                     ("features.json", "dataset_manifest.json", "quality_report.json"))
            if md.get("pipeline") != "multidataset_v1" or md.get("sampling_policy") != POLICY:
                raise ValueError(f"{folder}: cần pipeline multidataset_v1 với policy {POLICY}")
            if md.get("profile") != profile or md.get("feature_set") != variant:
                raise ValueError(f"{folder}: profile/feature_set không khớp")
            if {c["partition_id"]: c["dataset_id"] for c in manifest["clients"]} != DATASETS:
                raise ValueError(f"{folder}: PID không khớp hai nguồn")
            if md["hashes"] != manifest["hashes"]:
                raise ValueError(f"{folder}: hashes trong manifest khác features.json")
            if quality.get("status") == "failed":
                raise ValueError(f"{folder}: kiểm tra độc lập không đạt")
            required = {"features.json", "dataset_manifest.json", "quality_report.json", "prep_params.json",
                        "split_manifest.parquet", "sampling_report.md", "feature_selection.csv",
                        "multidataset/class_weights.json"}
            for c in manifest["clients"]:
                required.update(c[k] for k in ("train_file", "val_file", "test_file"))
            for relative in sorted(required):
                safe_relative(relative)
                f = folder / relative
                if f.is_symlink() or not f.is_file():
                    raise ValueError(f"Thiếu artifact hoặc gặp symlink: {f}")
                files[f"{name}/{relative}"] = {"sha256": sha256_file(f), "bytes": f.stat().st_size}
            datasets[name] = {"hashes": md["hashes"], "profile": profile, "feature_set": variant}
        if datasets[profile]["hashes"]["split"] != datasets[profile + "_all"]["hashes"]["split"]:
            raise ValueError(f"{profile}: DAS/all không cùng subset")
    body = {"version": 1, "policy": POLICY, "datasets": datasets, "files": files}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return {**body, "bundle_id": digest[:24], "manifest_sha256": digest}


def verify_bundle(root: Path, bundle: dict, name: str | None = None):
    body = {k: v for k, v in bundle.items() if k not in ("bundle_id", "manifest_sha256")}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if bundle["manifest_sha256"] != digest or bundle["bundle_id"] != digest[:24]:
        raise ValueError("Bundle manifest digest không hợp lệ")
    for relative, expected in bundle["files"].items():
        path = safe_relative(relative)
        if name is not None and path.parts[0] != name:
            continue
        file = root / relative
        if not file.is_file() or file.stat().st_size != expected["bytes"] or sha256_file(file) != expected["sha256"]:
            raise ValueError(f"Artifact không khớp SHA-256: {relative}")


def make_specs(cfg: dict, profile: str) -> list[dict]:
    p = cfg["profiles"][profile]
    common = {"profile": profile, "arch": cfg["fl"]["arch"], "rounds": p["rounds"],
              "epochs": p["local_epochs"], "lr": cfg["fl"]["lr"],
              "batch_size": cfg["fl"]["batch_size"], "dropout": cfg["fl"]["dropout"]}
    specs = [{**common, "variant": v, "kind": "fl", "seed": seed, "name": f"fl_{v}_seed{seed}"}
             for v in VARIANTS for seed in p["seeds"]]
    baseline_epochs = p["rounds"] * p["local_epochs"] if profile == "smoke" else cfg["fl"]["baseline_epochs"]
    specs += [{**common, "variant": "das", "kind": kind, "seed": p["seeds"][0],
               "baseline_epochs": baseline_epochs, "name": f"{kind}_das_seed{p['seeds'][0]}"}
              for kind in ("centralized", "local")]
    return specs


def commands(spec: dict, data: str, output: str, python: str) -> list[list[str]]:
    if spec["kind"] == "fl":
        config = (f"scenario='multidataset' data-dir='{data}' results-dir='{output}' num-clients={len(DATASETS)} "
                  f"arch='{spec['arch']}' seed={spec['seed']} num-server-rounds={spec['rounds']} "
                  f"local-epochs={spec['epochs']} lr={spec['lr']} batch-size={spec['batch_size']} "
                  f"dropout={spec['dropout']} strategy='fedavg' proximal-mu=0.0")
        # Một GPU/experiment, các client chạy lần lượt như smoke đã xác minh trên local.
        federation = (f"num-supernodes={len(DATASETS)} client-resources-num-cpus=2 client-resources-num-gpus=1 "
                      "init-args-num-cpus=2 init-args-num-gpus=1")
        return [["flwr", "run", ".", "--stream", "--federation-config", federation, "--run-config", config],
                [python, "analysis/evaluate_multidataset.py", "--data-dir", data, "--results-dir", output,
                 "--checkpoint", f"{output}/fl/*_best.pt"]]
    if spec["kind"] not in ("centralized", "local"):
        raise ValueError(f"Loại thí nghiệm không hợp lệ: {spec['kind']}")
    return [[python, "baselines/multidataset_baselines.py", "--mode", spec["kind"], "--data-dir", data,
             "--results-dir", output, "--epochs", str(spec["baseline_epochs"]), "--seed", str(spec["seed"]),
             "--arch", spec["arch"], "--lr", str(spec["lr"]), "--batch-size", str(spec["batch_size"]),
             "--dropout", str(spec["dropout"])]]


def validate_results(output: Path, spec: dict, hashes: dict):
    import pandas as pd
    import torch

    expected = len(DATASETS) if spec["kind"] == "local" else 1
    checkpoints = list(output.rglob("*_best.pt"))
    if len(checkpoints) != expected:
        raise RuntimeError(f"Cần {expected} best checkpoint, tìm thấy {len(checkpoints)}")
    for f in checkpoints:
        ck = torch.load(f, map_location="cpu", weights_only=False)
        if ck.get("hashes") != hashes or ck.get("kind") != "best" or ck.get("seed") != spec["seed"]:
            raise RuntimeError(f"Checkpoint không khớp dữ liệu/spec: {f}")
    table = pd.read_csv(output / "evaluation_by_dataset.csv")
    if table["checkpoint_sha256"].nunique() != expected:
        raise RuntimeError("Số checkpoint đánh giá không khớp")
    for _, rows in table.groupby("checkpoint_sha256"):
        actual = rows[rows.dataset_id.isin(DATASETS.values())]
        if len(actual) != len(DATASETS) or set(actual.dataset_id) != set(DATASETS.values()):
            raise RuntimeError("Checkpoint chưa được đánh giá đủ các tập test")
    if spec["kind"] == "fl":
        rounds = pd.read_csv(next((output / "fl").glob("*_rounds.csv")))
        clients = pd.read_csv(next((output / "fl").glob("*_clients.csv")))
        if set(rounds["round"]) != set(range(1, spec["rounds"] + 1)):
            raise RuntimeError("FL chưa hoàn tất đủ số vòng")
        for (_, _), rows in clients.groupby(["round", "phase"]):
            if len(rows) != len(DATASETS) or set(rows["partition-id"]) != set(DATASETS):
                raise RuntimeError("FL thiếu/trùng phản hồi client")


def merge_results(run_root: Path, statuses: list[dict], profile: str):
    import shutil
    import pandas as pd
    from fl_ddos.multidataset_eval import write_summary

    for variant in VARIANTS:
        selected = [s for s in statuses if s["profile"] == profile and s["variant"] == variant
                    and s["state"] == "completed"]
        if not selected:
            continue
        dst = run_root / "results" / profile / variant
        dst.mkdir(parents=True, exist_ok=True)
        tables = {}
        for spec in selected:
            src = run_root / profile / spec["name"] / "artifacts"
            for f in src.rglob("*"):
                if not f.is_file():
                    continue
                if f.parent == src and f.suffix == ".csv":
                    tables.setdefault(f.name, []).append(pd.read_csv(f))
                elif f.name != "summary.md":
                    target = dst / f.relative_to(src)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
        for name, parts in tables.items():
            pd.concat(parts, ignore_index=True).to_csv(dst / name, index=False)
        write_summary(dst)
