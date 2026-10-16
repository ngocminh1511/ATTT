"""Thí nghiệm E6 (mục 8): so sánh luật Suricata, mô hình FL và kết hợp cả hai trong lab.

Đầu vào:
  lab/logs/attack_log.csv           thời điểm bắt đầu/kết thúc mỗi đợt tấn công (traffic.sh ghi)
  lab/logs/site*/eve.json           cảnh báo luật (event_type=alert, sid 1000001-1000003)
  lab/logs/site*/ml_alerts.json     cảnh báo của detector/realtime.py
Đầu ra: results/lab_latency.csv (mỗi đợt × mỗi phương pháp) và bảng tổng hợp in ra màn hình.
  Độ trễ = thời điểm cảnh báo đầu tiên − thời điểm bắt đầu tấn công.
  Recall (mức đợt tấn công) = tỉ lệ đợt có cảnh báo trong [start, end + grace].
  Cảnh báo giả = số cảnh báo nằm ngoài mọi đợt tấn công.
"""
import argparse
import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fl_ddos.features import parse_ts  # noqa: E402

RULE_SIDS = {1000001, 1000002, 1000003}


def read_jsonl(pattern, keep):
    out = []
    for f in glob.glob(pattern):
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if keep(ev):
                    out.append(ev)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default=str(ROOT / "lab" / "logs"))
    ap.add_argument("--grace", type=float, default=10.0, help="giây cho phép sau khi đợt tấn công kết thúc")
    ap.add_argument("--event-time", action="store_true",
                    help="dùng thời gian sự kiện thay cho detected_at (khi chạy detector --replay)")
    a = ap.parse_args()
    attacks = pd.read_csv(Path(a.logs) / "attack_log.csv", dtype=str).fillna("")
    attacks["t0"] = attacks["start"].map(parse_ts)
    attacks["t1"] = attacks["end"].map(parse_ts)

    rule = [(parse_ts(e["timestamp"]), e.get("dest_ip")) for e in read_jsonl(
        f"{a.logs}/site*/eve.json",
        lambda e: e.get("event_type") == "alert" and e.get("alert", {}).get("signature_id") in RULE_SIDS)]
    ml = [(e["event_time"] if a.event_time else e["detected_at"], e.get("dest_ip")) for e in read_jsonl(
        f"{a.logs}/site*/ml_alerts.json", lambda e: e.get("event_type") == "ml_alert")]
    methods = {"Chỉ luật Suricata": rule, "Chỉ ML (FL model)": ml, "Luật + FL model": rule + ml}

    rows = []
    for name, alerts in methods.items():
        for _, at in attacks.iterrows():
            hits = [t for t, d in alerts if at.t0 <= t <= at.t1 + a.grace and (not at.dest_ip or d == at.dest_ip)]
            rows.append({"method": name, "label": at.label, "dest_ip": at.dest_ip,
                         "detected": bool(hits), "latency_s": (min(hits) - at.t0) if hits else None})
        false = sum(1 for t, _ in alerts
                    if not any(r.t0 <= t <= r.t1 + a.grace for r in attacks.itertuples()))
        rows.append({"method": name, "label": "__false_alarms__", "dest_ip": "", "detected": False,
                     "latency_s": None, "false_alarms": false})
    df = pd.DataFrame(rows)
    out = ROOT / "results" / "lab_latency.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    real = df[df.label != "__false_alarms__"]
    summary = real.groupby("method").agg(recall=("detected", "mean"), latency_mean=("latency_s", "mean"),
                                         latency_median=("latency_s", "median"))
    summary["false_alarms"] = df[df.label == "__false_alarms__"].set_index("method")["false_alarms"]
    print(summary.round(2).to_string())
    print(f"Đã ghi {out}")


if __name__ == "__main__":
    main()
