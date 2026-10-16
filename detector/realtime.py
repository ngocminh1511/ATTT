"""Mục 7.2: phát hiện DDoS thời gian thực trên sensor bằng mô hình FL toàn cục.

Đọc liên tục eve.json (giống `tail -f`), dự đoán từng flow, gom theo cửa sổ 1 giây
theo dest_ip và phát ml_alert khi có >= MIN_FLOWS flow bị chấm độc dồn về một đích.
Tiền xử lý dùng chung FlowFeaturizer + scaler.json với lúc huấn luyện (Nhánh B).

  python detector/realtime.py --model results/S3_mu0.0_seed0_global.pt --eve /var/log/suricata/eve.json
  # Kiểm tra offline trên một file có sẵn (đọc từ đầu, dừng ở cuối file):
  python detector/realtime.py --model ... --eve data/raw/synthetic_eve/day2/eve.json --replay
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos.features import FlowFeaturizer, load_meta, load_scaler, parse_ts, standardize  # noqa: E402
from fl_ddos.task import DDoSNet  # noqa: E402


def follow(path: str, replay: bool):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        if not replay:
            fh.seek(0, 2)  # đọc từ cuối file
        while True:
            line = fh.readline()
            if not line:
                if replay:
                    return
                time.sleep(0.05)
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


class Detector:
    def __init__(self, model_path, thresh, min_flows, drop_rules=None):
        meta = load_meta()
        if meta.get("branch") != "B":
            sys.exit("features.json không phải Nhánh B (eve.json). Mô hình Nhánh A cần CICFlowMeter chạy song song.")
        self.feats = meta["features"]
        self.mean, self.std = load_scaler()
        self.model = DDoSNet(len(self.feats))
        self.model.load_state_dict(torch.load(model_path, map_location="cpu"))
        self.model.eval()
        self.fz = FlowFeaturizer()
        self.thresh, self.min_flows = thresh, min_flows
        self.drop_rules = drop_rules
        self.window = {}
        self.infer_ms = []
        self.n_flows = 0
        self.sid = 2_000_000

    def score(self, ev) -> float:
        x = standardize(self.fz.vector(ev, self.feats), self.mean, self.std)
        t = time.perf_counter()
        with torch.no_grad():
            p = torch.softmax(self.model(torch.tensor(x, dtype=torch.float32)[None]), 1)[0, 1].item()
        self.infer_ms.append((time.perf_counter() - t) * 1000)
        return p

    def handle(self, ev):
        if ev.get("event_type") != "flow":
            return None
        self.n_flows += 1
        p = self.score(ev)
        bucket = math.floor(parse_ts(ev["flow"]["end"]))  # cửa sổ theo thời gian sự kiện
        w = self.window.get(ev["dest_ip"])
        if w is None or w["bucket"] != bucket:
            w = self.window[ev["dest_ip"]] = {"bucket": bucket, "bad": 0, "srcs": set()}
        if p >= self.thresh:
            w["bad"] += 1
            w["srcs"].add(ev["src_ip"])
        if w["bad"] == self.min_flows:  # báo động một lần mỗi cửa sổ
            return {"timestamp": ev["timestamp"], "event_type": "ml_alert", "dest_ip": ev["dest_ip"],
                    "n_bad_flows": w["bad"], "n_sources": len(w["srcs"]), "score": round(p, 3),
                    "detected_at": time.time(), "event_time": parse_ts(ev["flow"]["end"]),
                    "sources": sorted(w["srcs"])[:50]}
        return None

    def block(self, alert):
        """Chế độ IPS (7.3): sinh luật drop rồi nạp lại luật của Suricata."""
        with open(self.drop_rules, "a", encoding="utf-8") as fh:
            for src in alert["sources"]:
                self.sid += 1
                fh.write(f'drop ip {src} any -> {alert["dest_ip"]} any '
                         f'(msg:"ML DDoS source"; sid:{self.sid}; rev:1;)\n')
        subprocess.run(["suricatasc", "-c", "reload-rules"], check=False, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--eve", default="/var/log/suricata/eve.json")
    ap.add_argument("--alerts", default=None, help="mặc định: ml_alerts.json cạnh eve.json")
    ap.add_argument("--thresh", type=float, default=0.5)
    ap.add_argument("--min-flows", type=int, default=50)
    ap.add_argument("--replay", action="store_true", help="đọc file từ đầu và dừng ở cuối (test offline)")
    ap.add_argument("--drop-rules", default=None, help="file ml.rules để bật chế độ IPS")
    a = ap.parse_args()
    alerts_path = Path(a.alerts or Path(a.eve).with_name("ml_alerts.json"))
    det = Detector(a.model, a.thresh, a.min_flows, a.drop_rules)
    n_alerts = 0
    print(f"Theo dõi {a.eve} -> {alerts_path}", flush=True)
    try:
        for ev in follow(a.eve, a.replay):
            alert = det.handle(ev)
            if alert:
                n_alerts += 1
                print(json.dumps({k: v for k, v in alert.items() if k != "sources"}), flush=True)
                with open(alerts_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(alert) + "\n")
                if a.drop_rules:
                    det.block(alert)
    except KeyboardInterrupt:
        pass
    if det.infer_ms:
        ms = np.array(det.infer_ms)
        print(f"{det.n_flows} flow, {n_alerts} cảnh báo; suy luận {ms.mean():.3f} ms/flow "
              f"(p95 {np.percentile(ms, 95):.3f} ms) ~ {1000 / ms.mean():.0f} flow/giây", flush=True)


if __name__ == "__main__":
    main()
