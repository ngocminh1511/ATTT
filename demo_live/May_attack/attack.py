"""Máy attack (thiết bị B): bắn lưu lượng tới máy server theo kịch bản.

Chỉ dùng thư viện chuẩn của Python (urllib) — không cần cài thêm gì.
Mỗi request gắn loại mẫu qua header X-Sample-Type để máy server phát lại đúng
loại flow thật từ tập test. Máy server trả quyết định qua header X-Decision /
X-Pred-Label, script in ra để đối chiếu với dashboard.

Ví dụ:
    python attack.py --target http://192.168.1.50:8000 --phase all
    python attack.py --target http://192.168.1.50:8000 --phase dos --count 300 --threads 20 --rate 0

Các pha:
    benign  truy cập bình thường, chậm (kỳ vọng: ALLOW)
    dos     flood DoS/DDoS nhiều luồng, nhanh (kỳ vọng: BLOCK, DOS_DDOS)
    other   tấn công loại khác: dò/khai thác (kỳ vọng: BLOCK, OTHER_ATTACK)
    all     chạy lần lượt benign -> dos -> other
"""
from __future__ import annotations

import argparse
import threading
import time
import urllib.request
from collections import Counter

# (count, threads, rate req/s mỗi luồng, 0 = hết tốc độ) cho từng pha
PHASES = {
    "benign": {"count": 10, "threads": 1, "rate": 1.5, "desc": "Truy cập bình thường"},
    "dos":    {"count": 300, "threads": 20, "rate": 0, "desc": "Flood DoS/DDoS"},
    "other":  {"count": 40, "threads": 4, "rate": 5, "desc": "Tấn công loại khác (dò/khai thác)"},
}


def one_request(target: str, stype: str, timeout: float, source: str = "both") -> tuple[str, str, str]:
    """Gửi 1 request, trả (decision, pred_label, prob). 403 không phải lỗi -> vẫn đọc header."""
    req = urllib.request.Request(target + "/",
                                 headers={"X-Sample-Type": stype, "X-Source": source})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            h = r.headers
            return h.get("X-Decision", "?"), h.get("X-Pred-Label", "?"), h.get("X-Prob", "?")
    except urllib.error.HTTPError as e:  # 403 khi bị chặn
        h = e.headers
        return h.get("X-Decision", "BLOCK"), h.get("X-Pred-Label", "?"), h.get("X-Prob", "?")
    except Exception as e:
        return "ERR", type(e).__name__, "-"


def run_phase(target: str, name: str, cfg: dict, timeout: float, source: str) -> None:
    src_txt = "" if source == "both" else f" · nguồn {source}"
    print(f"\n=== Pha {name.upper()} · {cfg['desc']}{src_txt} · "
          f"{cfg['count']} request, {cfg['threads']} luồng ===")
    stats = Counter()
    lock = threading.Lock()
    per_thread = cfg["count"] // cfg["threads"]
    extra = cfg["count"] % cfg["threads"]
    t0 = time.time()

    def worker(n: int):
        for _ in range(n):
            decision, pred, prob = one_request(target, name, timeout, source)
            with lock:
                stats[decision] += 1
            if cfg["rate"] > 0:
                time.sleep(1.0 / cfg["rate"])

    threads = []
    for i in range(cfg["threads"]):
        n = per_thread + (1 if i < extra else 0)
        th = threading.Thread(target=worker, args=(n,))
        th.start()
        threads.append(th)
    for th in threads:
        th.join()
    dt = time.time() - t0
    total = sum(stats.values())
    allow, block, err = stats.get("ALLOW", 0), stats.get("BLOCK", 0), stats.get("ERR", 0)
    rps = total / dt if dt > 0 else 0
    print(f"  Xong {total} request trong {dt:.1f}s ({rps:.0f} req/s): "
          f"ALLOW={allow}  BLOCK={block}  ERR={err}")
    if err:
        print(f"  (ERR: không kết nối được tới {target} — kiểm tra IP/cổng/tường lửa)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="vd http://192.168.1.50:8000")
    ap.add_argument("--phase", default="all", choices=["benign", "dos", "other", "all"])
    ap.add_argument("--source", default="both", choices=["both", "cic", "unsw"],
                    help="lấy mẫu tấn công từ nguồn nào (cic/unsw) để demo tương phản")
    ap.add_argument("--count", type=int, help="ghi đè số request của pha")
    ap.add_argument("--threads", type=int, help="ghi đè số luồng của pha")
    ap.add_argument("--rate", type=float, help="ghi đè req/s mỗi luồng (0=hết tốc độ)")
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args()

    target = args.target.rstrip("/")
    source = {"both": "both", "cic": "cicddos2019", "unsw": "unsw_nb15"}[args.source]
    order = ["benign", "dos", "other"] if args.phase == "all" else [args.phase]
    print(f"Mục tiêu: {target}")
    for name in order:
        cfg = dict(PHASES[name])
        if args.count is not None:
            cfg["count"] = args.count
        if args.threads is not None:
            cfg["threads"] = args.threads
        if args.rate is not None:
            cfg["rate"] = args.rate
        cfg["threads"] = max(1, min(cfg["threads"], cfg["count"]))
        # BENIGN luôn lấy cả hai nguồn; chỉ pha tấn công mới lọc theo --source
        run_phase(target, name, cfg, args.timeout, "both" if name == "benign" else source)
        if len(order) > 1:
            time.sleep(1.5)
    print("\nHoàn tất. Xem dashboard máy server để đối chiếu.")


if __name__ == "__main__":
    main()
