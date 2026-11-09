r"""Modal: upload artifact đã chốt -> smoke gate -> 2 FL (DAS/all, seed 0) + 2 baseline main.

  .venv\Scripts\modal.exe run --detach modal_multidataset.py
  .venv\Scripts\modal.exe run --detach modal_multidataset.py --smoke-only

App/Volume riêng: fl-ddos-multidataset. Không chuẩn bị raw hoặc đổi split trên cloud.
Kết quả: /runs/{run_id}/results/{smoke|main}/{das|all}, tiến độ /runs/{run_id}/status.json.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import modal

from fl_ddos.modal_multidataset_jobs import (build_bundle, commands, data_name, make_specs, merge_results,
                                           read_json, validate_results, verify_bundle)

ROOT = Path(__file__).resolve().parent
REMOTE = "/root/project"
VOL = "/vol"
VOLUME_NAME = "fl-ddos-multidataset"
MAX_GPU_CONTAINERS = 4
GPU = "A10G"
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("torch==2.14.1", "flwr[simulation]==1.40.0", "ray==2.55.1", "numpy==2.5.4",
                    "pandas==3.0.6", "pyarrow==26.0.0", "scikit-learn==1.9.1", "scipy==1.18.1",
                    "matplotlib==3.11.2")
    .env({"FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION": "1", "PYTHONIOENCODING": "utf-8",
          "PYTHONUNBUFFERED": "1", "PYTHONPATH": REMOTE, "OMP_NUM_THREADS": "2",
          "MPLBACKEND": "Agg"})
    .add_local_dir(ROOT, REMOTE, copy=True,
                   ignore=[".venv", ".git", "data", "data_*", "results", "results_*", "docs", "notebooks",
                           "logs", "**/__pycache__", "*.pt", "*.pdf", "*.docx"])
)
app = modal.App("fl-ddos-multidataset", image=image)
vol = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)


def save_json(path: Path, body: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")


def run_command(command: list[str], log_file: Path):
    print("$", " ".join(command), flush=True)
    with log_file.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=REMOTE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        rc = process.wait()
    if rc:
        raise RuntimeError(f"Command failed ({rc}); xem {log_file.name}")


@app.function(gpu=GPU, cpu=4, memory=16384, volumes={VOL: vol}, timeout=6 * 3600,
              max_containers=MAX_GPU_CONTAINERS, retries=0, scaledown_window=30)
def experiment(spec: dict, bundle: dict, run_id: str) -> dict:
    vol.reload()
    bundle_root = Path(VOL, "datasets", bundle["bundle_id"])
    name = data_name(spec["profile"], spec["variant"])
    dest = Path(VOL, "runs", run_id, spec["profile"], spec["name"])
    status = {**spec, "state": "running", "bundle_id": bundle["bundle_id"], "started_at": time.time()}
    save_json(dest / "status.json", status)
    vol.commit()
    with tempfile.TemporaryDirectory(prefix="multidataset_") as tmp:
        output = Path(tmp)
        try:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError("Modal container không thấy GPU CUDA")
            status["gpu"] = torch.cuda.get_device_name(0)
            verify_bundle(bundle_root, bundle, name)
            for i, command in enumerate(commands(spec, str(bundle_root / name), str(output), sys.executable)):
                run_command(command, output / f"command_{i + 1}.log")
            validate_results(output, spec, bundle["datasets"][name]["hashes"])
            status["state"] = "completed"
        except Exception as exc:
            status.update(state="failed", error=repr(exc))
            print(f"[experiment] FAILED {spec['name']}: {exc}", flush=True)
        finally:
            shutil.copytree(output, dest / "artifacts", dirs_exist_ok=True)
            status["minutes"] = round((time.time() - status["started_at"]) / 60, 2)
            save_json(dest / "status.json", status)
            vol.commit()
    return status


@app.function(cpu=2, memory=4096, volumes={VOL: vol}, timeout=3600)
def report(run_id: str, statuses: list[dict], profile: str):
    vol.reload()
    merge_results(Path(VOL, "runs", run_id), statuses, profile)
    vol.commit()


@app.function(cpu=.5, memory=2048, volumes={VOL: vol}, timeout=24 * 3600, retries=0)
def run_all(bundle: dict, cfg: dict, run_id: str, smoke_only: bool = False, only: list | None = None):
    vol.reload()
    run_root = Path(VOL, "runs", run_id)
    verify_bundle(Path(VOL, "datasets", bundle["bundle_id"]), bundle)
    if (run_root / "status.json").exists():
        raise RuntimeError(f"Run ID đã tồn tại: {run_id}")
    state = {"run_id": run_id, "bundle_id": bundle["bundle_id"], "state": "starting", "jobs": [],
             "max_gpu_containers": MAX_GPU_CONTAINERS, "started_at": time.time(), "config": cfg}
    save_json(run_root / "bundle_manifest.json", bundle)

    def persist():
        save_json(run_root / "status.json", state)
        vol.commit()

    persist()
    try:
        for profile in (["smoke"] if smoke_only else ["smoke", "main"]):
            specs = make_specs(cfg, profile, set(only) if only else None)
            state.update(state=f"{profile}_running", current_profile=profile, planned_jobs=specs)
            persist()
            results = []
            for index, result in enumerate(experiment.map(specs, kwargs={"bundle": bundle, "run_id": run_id},
                                                           return_exceptions=True)):
                spec = specs[index]
                if isinstance(result, BaseException):
                    result = {**spec, "state": "failed", "error": repr(result)}
                results.append(result)
                state["jobs"].append(result)
                persist()
                print(f"[run_all] {profile}/{spec['name']}: {result['state']}", flush=True)
            report.remote(run_id, results, profile)
            vol.reload()
            if any(r["state"] != "completed" for r in results):
                raise RuntimeError(f"{profile} có thí nghiệm lỗi; không bắt đầu giai đoạn kế tiếp")
        state.update(state="completed", finished_at=time.time())
    except Exception as exc:
        state.update(state="failed", error=repr(exc), finished_at=time.time())
        print(f"[run_all] FAILED: {exc}", flush=True)
    persist()
    return state


@app.local_entrypoint()
def main(smoke_only: bool = False, only: str = ""):
    """--only fl_das_fedprox_seed0[,tên khác]: chỉ chạy các job đó (smoke rồi main)."""
    only_jobs = [s for s in only.split(",") if s]
    cfg = read_json(ROOT / "configs/multidataset.json")
    for profile in ("smoke", "main"):
        make_specs(cfg, profile, set(only_jobs) or None)  # báo lỗi sớm nếu tên job sai
    data_root = ROOT / cfg["paths"]["out"]
    bundle = build_bundle(data_root)
    remote_manifest = f"/datasets/{bundle['bundle_id']}/bundle_manifest.json"
    try:
        uploaded = json.loads(b"".join(vol.read_file(remote_manifest)))
        if uploaded != bundle:
            raise RuntimeError("Bundle ID trên Volume đã tồn tại nhưng nội dung khác")
        print(f"Bundle {bundle['bundle_id']} đã có trên Volume.")
    except (FileNotFoundError, modal.exception.NotFoundError):
        print(f"Upload {sum(f['bytes'] for f in bundle['files'].values()) / 2**20:.1f} MiB artifact đã chốt.")
        with vol.batch_upload(force=True) as batch:
            for relative in bundle["files"]:
                batch.put_file(data_root / relative, f"/datasets/{bundle['bundle_id']}/{relative}")
        with vol.batch_upload() as batch:
            batch.put_file(io.BytesIO(json.dumps(bundle, ensure_ascii=False).encode()), remote_manifest)
    run_id = datetime.now(timezone(timedelta(hours=7))).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    call = run_all.spawn(bundle, cfg, run_id, smoke_only, only_jobs)
    launch = {"run_id": run_id, "bundle_id": bundle["bundle_id"], "app_id": app.app_id,
              "call_id": call.object_id, "volume": VOLUME_NAME, "smoke_only": smoke_only, "only": only_jobs,
              "remote_status": f"/runs/{run_id}/status.json",
              "download": f"modal volume get {VOLUME_NAME} /runs/{run_id} ./results_modal_multidataset/{run_id}"}
    save_json(ROOT / "logs" / f"modal_multidataset_{run_id}.json", launch)
    print(json.dumps(launch, indent=2), flush=True)
    result = call.get()
    print(f"Run {run_id}: {result['state']}", flush=True)
    if result["state"] != "completed":
        raise RuntimeError(result.get("error", "Modal run failed"))
