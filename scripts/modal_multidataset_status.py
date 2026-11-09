"""Đọc tiến độ và tải kết quả Modal; tạo đúng cây thư mục trên Windows.

  python scripts/modal_multidataset_status.py
  python scripts/modal_multidataset_status.py --download smoke
  python scripts/modal_multidataset_status.py --download all --launch logs/modal_multidataset_RUN_ID.json
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

import modal
from modal.types import FileEntryType

ROOT = Path(__file__).resolve().parent.parent


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch", help="Mặc định file launch mới nhất trong logs/")
    parser.add_argument("--download", choices=("smoke", "all"))
    args = parser.parse_args()
    launch_file = Path(args.launch) if args.launch else max((ROOT / "logs").glob("modal_multidataset_*.json"))
    launch = json.loads(launch_file.read_text(encoding="utf-8"))
    volume = modal.Volume.from_name(launch["volume"])
    state = json.loads(b"".join(volume.read_file(launch["remote_status"])))
    run_id = launch["run_id"]
    print(f"Run {run_id}: {state['state']}")
    print(f"App: {launch['app_id']}; bundle: {launch['bundle_id']}")
    for spec in state.get("planned_jobs", []):
        try:
            status = json.loads(b"".join(volume.read_file(f"/runs/{run_id}/{spec['profile']}/{spec['name']}/status.json")))
        except FileNotFoundError:
            status = {"state": "pending"}
        print(f"  {spec['name']}: {status['state']}" + (f" — {status['error']}" if status.get("error") else ""))
    dest = ROOT / "results_modal_multidataset" / run_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "status_snapshot.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.download:
        return
    remote = f"/runs/{run_id}/results" + ("/smoke" if args.download == "smoke" else "")
    entries = [entry for entry in volume.iterdir(remote, recursive=True) if entry.type == FileEntryType.FILE]
    base = PurePosixPath(f"runs/{run_id}/results")

    def download(entry):
        relative = PurePosixPath(entry.path.lstrip("/")).relative_to(base)
        if ".." in relative.parts:
            raise ValueError(f"Remote path không hợp lệ: {entry.path}")
        target = dest.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as output:
            for chunk in volume.read_file(entry.path):
                output.write(chunk)
        return str(relative)

    with ThreadPoolExecutor(max_workers=4) as pool:
        saved = list(pool.map(download, entries))
    print(f"Đã tải {len(saved)} tệp kết quả về {dest}")


if __name__ == "__main__":
    main()
