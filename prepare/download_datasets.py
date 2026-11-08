"""Tải và kiểm tra raw data cho pipeline multidataset_v1 (kế hoạch mục 3).

  CIC-DDoS2019  chỉ kiểm tra 17 Parquet đã có trong data/raw/cicddos2019 + SHA-256
  UNSW-NB15     thử URL chính thức (nếu cấu hình có), sau đó bản sao Nir-J/ML-Projects khóa theo commit;
                kiểm tra không phải HTML, header, số dòng 175.341 / 82.332, tập nhãn attack_cat
  IoT-23        iot_23_datasets_small.tar.gz (~8,7 GiB): file .part, tiếp tục bằng HTTP Range,
                kiểm tra dung lượng trống (phần còn lại + 8 GiB), đổi tên khi đủ byte

Mỗi nguồn ghi download_manifest.json cạnh dữ liệu. SHA-256 do script tự tính để khóa artifact đã tải,
không phải checksum do nhà phát hành chứng nhận.

  python prepare/download_datasets.py --config configs/multidataset.json
  python prepare/download_datasets.py --only unsw_nb15            # chỉ UNSW (vài chục MB)
  python prepare/download_datasets.py --only iot23 --check-only   # chỉ kiểm tra dung lượng / kích thước
"""
import argparse
import gzip
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import dataset_adapters as ad  # noqa: E402
from fl_ddos.multidataset_prep import read_json  # noqa: E402
from fl_ddos.multidataset_prep import dump_json, sha256_file  # noqa: E402

UA = {"User-Agent": "fl-ddos-dataset-downloader/1.0"}
GiB = 2 ** 30


def remote_size(url: str, timeout: int) -> int | None:
    """Kích thước qua Range bytes=0-0 (Content-Range: bytes 0-0/TOTAL); None nếu server không báo."""
    req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        cr = r.headers.get("Content-Range", "")
        if "/" in cr and cr.rsplit("/", 1)[1].isdigit():
            return int(cr.rsplit("/", 1)[1])
        cl = r.headers.get("Content-Length")
        return int(cl) if cl and r.status == 200 else None


def download(url: str, dest: Path, timeout: int, chunk: int, expected: int | None = None,
             margin_bytes: int = 0) -> Path:
    """Tải về dest.part, tiếp tục từ byte đã có nếu server hỗ trợ Range; đổi tên sau khi đủ."""
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    total = expected
    if total is None:
        try:
            total = remote_size(url, timeout)
        except Exception:  # noqa: BLE001 - chỉ để ước lượng dung lượng
            total = None
    if total is not None:
        free = shutil.disk_usage(dest.parent).free
        need = max(total - have, 0) + margin_bytes
        if free < need:
            raise SystemExit(f"Không đủ dung lượng tại {dest.parent}: trống {free / GiB:.2f} GiB, cần "
                             f"{need / GiB:.2f} GiB (phần còn lại {max(total - have, 0) / GiB:.2f} + dự phòng "
                             f"{margin_bytes / GiB:.0f}). Thiếu {(need - free) / GiB:.2f} GiB.")
        if have == total:
            part.rename(dest)
            return dest
    headers = dict(UA)
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if have and r.status != 206:  # server bỏ qua Range -> tải lại từ đầu
            print(f"  server không tiếp tục được (HTTP {r.status}); tải lại từ đầu")
            have = 0
        mode = "ab" if have else "wb"
        t0, done = time.time(), have
        with open(part, mode) as fh:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                fh.write(b)
                done += len(b)
                if time.time() - t0 > 10:
                    pct = f"{done / total * 100:5.1f}%" if total else ""
                    print(f"  {dest.name}: {done / 2**20:,.0f} MiB {pct}", flush=True)
                    t0 = time.time()
    size = part.stat().st_size
    if total is not None and size != total:
        raise SystemExit(f"{dest.name}: tải được {size} byte, server báo {total}. Chạy lại để tiếp tục.")
    part.rename(dest)
    return dest


# ---------------------------------------------------------------- CIC
def check_cic(cfg, root: Path):
    src = cfg["sources"]["cicddos2019"]
    d = root / src["dir"]
    files = sorted(d.glob(src["train_glob"])) + sorted(d.glob(src["test_glob"]))
    if len(files) != src["expected_files"]:
        raise SystemExit(f"CIC: tìm thấy {len(files)} file trong {d}, chờ {src['expected_files']}")
    for f in files:
        with open(f, "rb") as fh:
            if fh.read(4) != b"PAR1":
                raise SystemExit(f"CIC: {f} không phải Parquet")
    m = {"dataset_id": "cicddos2019", "source": "local (đã có trong dự án)", "reference": src["reference"],
         "convention": src["note"], "files": [{"name": f.name, "bytes": f.stat().st_size, "sha256": sha256_file(f)}
                                             for f in files], "checked": time.strftime("%Y-%m-%d %H:%M:%S")}
    dump_json(m, d / "download_manifest.json")
    print(f"CIC: {len(files)} Parquet hợp lệ -> {d / 'download_manifest.json'}")


# ---------------------------------------------------------------- UNSW
def validate_unsw(path: Path, expected_rows: int, cfg) -> dict:
    df = ad.read_unsw_csv(path)  # báo lỗi nếu là HTML hoặc thiếu cột
    if len(df) != expected_rows:
        raise ValueError(f"{path.name}: {len(df)} dòng, chờ {expected_rows}")
    known = ad.build_label_lookup(cfg["label_map"], "unsw_nb15")
    cats = sorted(df["attack_cat"].fillna("Normal").astype(str).str.strip().unique())
    unknown = [c for c in cats if ad._norm_key(c or "Normal") not in known]
    if unknown:
        raise ValueError(f"{path.name}: attack_cat lạ {unknown}")
    return {"rows": len(df), "columns": list(df.columns), "attack_cat": cats}


def get_unsw(cfg, root: Path, dl):
    src = cfg["sources"]["unsw_nb15"]
    d = root / src["dir"]
    mf = d / "download_manifest.json"
    old = read_json(mf) if mf.exists() else {"files": {}}
    mir = src["mirror"]
    base = mir["repository"].replace("https://github.com/", "https://raw.githubusercontent.com/")
    entries = {}
    for split, spec in src["files"].items():
        dest = d / spec["name"]
        prev = old["files"].get(split)
        if dest.exists() and prev and prev.get("sha256") == sha256_file(dest):
            print(f"UNSW {spec['name']}: đã có, checksum khớp manifest")
            entries[split] = prev
            continue
        urls = [("official", u) for u in src.get("official_urls", {}).get(split, [])] + \
               [("mirror", f"{base}/{mir['commit']}/{mir['path']}/{spec['name']}")]
        errors = []
        for kind, url in urls:
            try:
                if dest.exists():
                    dest.unlink()
                print(f"UNSW {spec['name']}: tải từ {kind} {url}")
                download(url, dest, dl["timeout_s"], dl["chunk_bytes"])
                info = validate_unsw(dest, spec["rows"], cfg)
                entries[split] = {"name": spec["name"], "source": kind, "url": url, "bytes": dest.stat().st_size,
                                  "sha256": sha256_file(dest), **info,
                                  "note": "SHA-256 tự tính; không phải checksum được UNSW chứng nhận" +
                                          (f"; bản sao {mir['repository']} @ {mir['commit']}" if kind == "mirror" else "")}
                break
            except (urllib.error.URLError, OSError, ValueError) as e:
                errors.append(f"{kind}: {e}")
                if dest.exists():
                    dest.rename(dest.with_suffix(".invalid"))
        else:
            raise SystemExit(f"UNSW {spec['name']}: mọi nguồn đều lỗi -> {errors}. Không thay bằng bản khác.")
    dump_json({"dataset_id": "unsw_nb15", "official_page": src["official_page"], "files": entries,
               "checked": time.strftime("%Y-%m-%d %H:%M:%S")}, mf)
    print(f"UNSW: xong -> {mf}")


# ---------------------------------------------------------------- IoT-23
def get_iot(cfg, root: Path, dl, check_only: bool):
    src = cfg["sources"]["iot23"]
    d = root / src["dir"]
    dest = d / src["archive"]
    mf = d / "download_manifest.json"
    d.mkdir(parents=True, exist_ok=True)
    total = remote_size(src["url"], dl["timeout_s"]) if not dest.exists() else dest.stat().st_size
    part = dest.with_name(dest.name + ".part")
    have = dest.stat().st_size if dest.exists() else (part.stat().st_size if part.exists() else 0)
    free = shutil.disk_usage(d).free
    print(f"IoT: server báo {total} byte ({(total or 0) / GiB:.2f} GiB; cấu hình ghi {src['expected_bytes']}), "
          f"đã có {have / GiB:.2f} GiB, ổ trống {free / GiB:.2f} GiB")
    if check_only:
        return
    if not dest.exists():
        download(src["url"], dest, dl["timeout_s"], dl["chunk_bytes"], expected=total,
                 margin_bytes=int(dl["free_space_margin_gib"] * GiB))
    with gzip.open(dest, "rb") as fh:
        fh.read(1024)  # gzip hợp lệ ở phần đầu (toàn bộ được kiểm tra khi pipeline đọc luồng)
    if mf.exists():
        old = read_json(mf)
        if old.get("bytes") == dest.stat().st_size and old.get("sha256"):
            print(f"IoT: archive đã có trong manifest ({old['sha256'][:12]}…)")
            return
    print("IoT: tính SHA-256 (có thể mất vài phút)…")
    dump_json({"dataset_id": "iot23", "url": src["url"], "name": dest.name, "bytes": dest.stat().st_size,
               "server_reported_bytes": total, "sha256": sha256_file(dest), "reference": src["reference"],
               "note": "SHA-256 tự tính để khóa artifact đã tải", "downloaded": time.strftime("%Y-%m-%d %H:%M:%S")}, mf)
    print(f"IoT: xong -> {mf}")


def main():
    for s in (sys.stdout, sys.stderr):  # console Windows (cp1252) không in được tiếng Việt
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/multidataset.json")
    ap.add_argument("--only", default="cicddos2019,unsw_nb15,iot23")
    ap.add_argument("--check-only", action="store_true", help="IoT: chỉ báo kích thước/dung lượng, không tải")
    a = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    cfg = read_json(root / a.config if not Path(a.config).is_absolute() else a.config)
    only = set(a.only.split(","))
    dl = cfg["download"]
    if "cicddos2019" in only:
        check_cic(cfg, root)
    if "unsw_nb15" in only:
        get_unsw(cfg, root, dl)
    if "iot23" in only:
        get_iot(cfg, root, dl, a.check_only)


if __name__ == "__main__":
    main()
