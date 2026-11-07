"""Chạy toàn bộ thí nghiệm của pipeline paper trên Modal (GPU đám mây).

Bộ điều phối (run_all) chạy TRÊN Modal, không chạy trên máy local: với `modal run --detach`,
tắt máy / mất mạng thì app vẫn chạy tiếp. Mỗi thí nghiệm là một container GPU riêng, chạy song song;
một thí nghiệm lỗi không làm dừng các thí nghiệm khác. Mọi kết quả ghi vào Volume "fl-ddos":
  /raw/cicddos2019/            parquet gốc (tải lên một lần)
  /data/{variant}/             output của prepare/paper_pipeline.py (main | random | leak)
  /runs/{group}/{variant}/{tên}/   kết quả thô của từng thí nghiệm (+ status.json)
  /results/{group}/{variant}/  kết quả đã gộp + figures/ + summary.md   (group = full | quick)
  /results/{group}/status.json danh sách thí nghiệm thành công / lỗi, thời gian chạy

Một lần đầu: chỉ cần đăng nhập (`modal setup`, hoặc `modal profile activate <tên>` nếu đã có token).
Volume "fl-ddos" được tạo tự động, và lần chạy đầu tự tải data/raw/cicddos2019 lên nếu volume chưa có.

Chạy:
  modal run modal_app.py --quick              # thử nhanh 2 vòng × 1 epoch, nên chạy trước khi đi ngủ
  modal run --detach modal_app.py             # chạy đầy đủ -> tắt máy được
  modal run --detach modal_app.py --seeds 0 --archs resvgg_swin,resnet --variants main
  modal run modal_app.py::report              # gộp + vẽ lại từ /runs (không train)

Theo dõi và lấy kết quả:
  https://modal.com/apps  (log từng container) hoặc: modal app logs fl-ddos-paper
  modal volume ls fl-ddos /results/full
  modal volume get fl-ddos /results/full ./results_modal
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent
REMOTE = "/root/project"
VOL = "/vol"
GPU = ["L4", "A10G", "T4"]  # thử lần lượt, loại nào trống thì dùng (L4/A10G 24 GB, T4 16 GB)
MAX_GPU_CONTAINERS = 8  # số thí nghiệm chạy song song (giới hạn chi phí theo giờ)
ARCHS = ["resvgg_swin", "resnet", "resnet_vgg", "resnet_swin", "lstm", "lstm_gru"]
VARIANTS = {"main": [], "random": ["--split", "random"], "leak": ["--afn", "label"]}

image = (
    modal.Image.debian_slim(python_version="3.12")
    # Cùng phiên bản với requirements.lock.txt; torch trên PyPI cho Linux đã kèm CUDA
    .uv_pip_install("torch==2.14.1", "flwr[simulation]==1.40.0", "ray==2.55.1", "numpy==2.5.4",
                    "pandas==3.0.6", "pyarrow==26.0.0", "scikit-learn==1.9.1", "scipy==1.18.1",
                    "matplotlib==3.11.2")
    .env({"FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION": "1", "PYTHONIOENCODING": "utf-8",
          "PYTHONUNBUFFERED": "1", "PYTHONPATH": REMOTE})
    .add_local_dir(ROOT, REMOTE, copy=True,
                   ignore=[".venv", ".git", "data", "data_*", "results", "results_*", "docs", "notebooks",
                           "**/__pycache__", "*.pt", "*.pdf", "*.docx"])
)
app = modal.App("fl-ddos-paper", image=image)
vol = modal.Volume.from_name("fl-ddos", create_if_missing=True)


def sh(cmd: list, env: dict | None = None) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=REMOTE, env={**os.environ, **(env or {})}).returncode


# ---------------------------------------------------------------- dữ liệu
@app.function(cpu=4, memory=16384, volumes={VOL: vol}, timeout=3600)
def prepare(variants: list, force: bool = False):
    vol.reload()
    raw = Path(VOL, "raw", "cicddos2019")
    if not list(raw.glob("*.parquet")):
        raise RuntimeError("Volume chưa có dữ liệu: modal volume put fl-ddos data/raw/cicddos2019 /raw/cicddos2019")
    for v in variants:
        out = Path(VOL, "data", v)
        if (out / "features.json").exists() and not force:
            print(f"[prepare] {v}: đã có, bỏ qua (dùng --force-prepare để tạo lại)")
            continue
        shutil.rmtree(out, ignore_errors=True)
        rc = sh([sys.executable, "prepare/paper_pipeline.py", "--train-glob", f"{raw}/*-testing.parquet",
                 "--test-glob", f"{raw}/*-training.parquet", "--out", str(out), *VARIANTS[v]])
        if rc:
            raise RuntimeError(f"paper_pipeline.py lỗi ở biến thể {v}")
        vol.commit()


# ---------------------------------------------------------------- một thí nghiệm
@app.function(gpu=GPU, cpu=8, memory=32768, volumes={VOL: vol}, timeout=6 * 3600,
              max_containers=MAX_GPU_CONTAINERS, retries=modal.Retries(max_retries=1, initial_delay=30.0))
def experiment(spec: dict) -> dict:
    """spec: {group, variant, kind (fl|centralized|local), arch, seed, rounds, epochs, name}."""
    vol.reload()
    data = f"{VOL}/data/{spec['variant']}"
    tmp = Path("/tmp/results")  # ghi ra đĩa container trước, xong mới chép vào Volume (tránh ghi đè lẫn nhau)
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    t0 = time.time()
    if spec["kind"] == "fl":
        cfg = (f"data-dir='{data}' results-dir='{tmp}' num-clients=3 arch='{spec['arch']}' seed={spec['seed']} "
               f"num-server-rounds={spec['rounds']} local-epochs={spec['epochs']}")
        # 3 client dùng chung 1 GPU (0.33 mỗi client) -> chạy song song như 3 chi nhánh
        fed = ("num-supernodes=3 client-resources-num-cpus=2 client-resources-num-gpus=0.33 "
               "init-args-num-cpus=8 init-args-num-gpus=1")
        rc = sh(["flwr", "run", ".", "--stream", "--federation-config", fed, "--run-config", cfg])
    else:
        script = {"centralized": "baselines/centralized.py", "local": "baselines/local_only.py"}[spec["kind"]]
        rc = sh([sys.executable, script, "--scenario", "paper", "--arch", spec["arch"],
                 "--epochs", str(spec["rounds"] * spec["epochs"]), "--seed", str(spec["seed"])],
                env={"FL_DDOS_DATA": data, "FL_DDOS_RESULTS": str(tmp)})
    status = {**spec, "returncode": rc, "minutes": round((time.time() - t0) / 60, 1)}
    (tmp / "status.json").write_text(json.dumps(status, indent=2))
    dest = Path(VOL, "runs", spec["group"], spec["variant"], spec["name"])
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(tmp, dest)
    vol.commit()
    if rc:
        raise RuntimeError(f"{spec['name']} lỗi (returncode {rc}); log xem trên modal.com/apps")
    return status


# ---------------------------------------------------------------- gộp + vẽ
def merge_and_plot(group: str, variant: str):
    import pandas as pd
    src, dst = Path(VOL, "runs", group, variant), Path(VOL, "results", group, variant)
    if not src.exists():
        return
    shutil.rmtree(dst, ignore_errors=True)
    (dst / "fl").mkdir(parents=True)
    tables = {}
    for run in sorted(p for p in src.iterdir() if p.is_dir()):
        status_file = run / "status.json"
        status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}
        if status.get("arch") == "mlp" or run.name.startswith("fl_mlp_"):
            continue  # MLP thuộc pipeline cũ; bỏ cả các lượt chạy còn lưu từ trước trên Volume
        for f in (run / "fl").glob("*") if (run / "fl").exists() else []:
            shutil.copy2(f, dst / "fl" / f.name)
        for f in run.glob("*.pt"):
            shutil.copy2(f, dst / f.name)
        for name in ("baselines.csv", "per_attack.csv", "per_class.csv"):
            if (run / name).exists():
                tables.setdefault(name, []).append(pd.read_csv(run / name))
    for name, dfs in tables.items():
        pd.concat(dfs, ignore_index=True).to_csv(dst / name, index=False)
    sh([sys.executable, "analysis/plots.py", "--data-dir", f"{VOL}/data/{variant}", "--results-dir", str(dst)])


@app.function(cpu=4, memory=16384, volumes={VOL: vol}, timeout=3600)
def report(group: str = "full", variants: list | None = None):
    vol.reload()
    for v in variants or list(VARIANTS):
        merge_and_plot(group, v)
    vol.commit()


@app.function(cpu=2, memory=4096, volumes={VOL: vol}, timeout=24 * 3600)
def run_all(specs: list, variants: list, group: str, force_prepare: bool = False):
    """Điều phối chạy trên Modal: chuẩn bị dữ liệu -> mọi thí nghiệm song song -> gộp + vẽ."""
    prepare.remote(variants, force_prepare)
    out = []
    for spec, r in zip(specs, experiment.map(specs, return_exceptions=True)):
        out.append(r if isinstance(r, dict) else {**spec, "error": repr(r)})
        print(f"[run_all] {'OK ' if 'error' not in out[-1] else 'LỖI'} {spec['variant']}/{spec['name']}", flush=True)
    report.remote(group, variants)
    vol.reload()
    Path(VOL, "results", group).mkdir(parents=True, exist_ok=True)
    Path(VOL, "results", group, "status.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    vol.commit()
    failed = [s["name"] for s in out if "error" in s]
    print(f"[run_all] xong: {len(out) - len(failed)}/{len(out)} thành công" + (f"; lỗi: {failed}" if failed else ""))
    return out


# ---------------------------------------------------------------- gọi từ máy local
@app.local_entrypoint()
def main(quick: bool = False, seeds: str = "0,1,2", archs: str = ",".join(ARCHS),
         variants: str = "main,random,leak", baselines: bool = True, force_prepare: bool = False):
    group = "quick" if quick else "full"
    rounds, epochs = (2, 1) if quick else (30, 5)  # paper mục 5.1: 30 vòng × 5 epoch
    if quick:
        seeds, archs, variants = "0", "resvgg_swin,lstm", "main"
    seed_list, arch_list = [int(s) for s in seeds.split(",")], archs.split(",")
    var_list = [v for v in variants.split(",") if v]
    unknown = sorted(set(arch_list) - set(ARCHS)) + sorted(set(var_list) - set(VARIANTS))
    if unknown:
        raise SystemExit(f"Không hợp lệ: {unknown}")

    base = {"group": group, "rounds": rounds, "epochs": epochs}
    specs = [{**base, "variant": "main", "kind": "fl", "arch": a, "seed": s, "name": f"fl_{a}_seed{s}"}
             for s in seed_list for a in arch_list] if "main" in var_list else []
    # random (chia ngẫu nhiên như paper) và leak (AFN theo nhãn): chỉ mô hình chính, seed đầu
    specs += [{**base, "variant": v, "kind": "fl", "arch": "resvgg_swin", "seed": seed_list[0],
               "name": f"fl_resvgg_swin_seed{seed_list[0]}"} for v in var_list if v != "main"]
    if baselines and "main" in var_list:
        specs += [{**base, "variant": "main", "kind": k, "arch": "resvgg_swin", "seed": seed_list[0],
                   "name": f"{k}_resvgg_swin_seed{seed_list[0]}"} for k in ("centralized", "local")]

    # Volume gắn với từng tài khoản Modal: tài khoản mới (hoặc volume trống) -> tự tải dữ liệu gốc lên
    try:
        have_raw = any(e.path.endswith(".parquet") for e in vol.listdir("/raw/cicddos2019"))
    except Exception:  # thư mục chưa tồn tại
        have_raw = False
    if not have_raw:
        local_raw = ROOT / "data" / "raw" / "cicddos2019"
        if not list(local_raw.glob("*.parquet")):
            raise SystemExit(f"Volume chưa có dữ liệu và không tìm thấy {local_raw}")
        print(f"Tải {local_raw} lên volume fl-ddos:/raw/cicddos2019 ...")
        with vol.batch_upload() as batch:
            batch.put_directory(str(local_raw), "/raw/cicddos2019")

    print(f"[{group}] {len(specs)} thí nghiệm, {rounds} vòng × {epochs} epoch, GPU {GPU}, "
          f"tối đa {MAX_GPU_CONTAINERS} chạy song song:")
    for s in specs:
        print(f"  {s['variant']:7s} {s['name']}")
    call = run_all.spawn(specs, var_list, group, force_prepare)
    print(f"\nĐã gửi lên Modal (call id {call.object_id}). Theo dõi: https://modal.com/apps")
    print(f"Lấy kết quả khi xong: modal volume get fl-ddos /results/{group} ./results_modal")
    # Không --detach: Ctrl+C / tắt máy sẽ dừng cả app. Có --detach: app chạy tiếp trên Modal.
    out = call.get()
    print(f"Xong: {sum('error' not in s for s in out)}/{len(out)} thành công")
