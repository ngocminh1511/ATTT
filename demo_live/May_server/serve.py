r"""Máy server (thiết bị A): web có model ResVGG-SwinNet gác cửa.

Mỗi request tới trang web được quy thành MỘT flow 8 đặc trưng (phát lại một flow
thật trong tập test đúng loại `sample_type`), đưa qua model đã huấn luyện của run
4 client. Dự đoán BENIGN -> cho xem trang (200); DOS_DDOS / OTHER_ATTACK -> chặn
(403). Model chạy forward thật trên CPU, không huấn luyện lại.

Chạy:
    .\.venv\Scripts\python.exe demo_live/May_server/serve.py --host 0.0.0.0 --port 8000

Trang:
    GET /            trang web, có model gác cửa (đọc ?sample_type=benign|dos|other)
    GET /dashboard   màn hình vận hành: đếm cho qua/chặn + log thời gian thực
    GET /api/events  JSON cho dashboard
    POST /api/switch model=prox|das  đổi checkpoint

Mặc định đọc checkpoint FedProx (μ=0,1) và FedAvg DAS của run 4 client trong
results_modal_multidataset. Dữ liệu test: data_paper_multi_4c/main/test.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # .../Final_Exam
sys.path.insert(0, str(ROOT))
from fl_ddos import paths  # noqa: E402
from fl_ddos.multidataset_eval import load_checkpoint  # noqa: E402

DATA = ROOT / "data_paper_multi_4c/main"
RUN = ROOT / "results_modal_multidataset/20261122_152058_5ec64a/main/das/fl"
CHECKPOINTS = {
    "prox": RUN / "multidataset_resvgg_swin_seed0_fedprox_mu0.1_best.pt",
    "das": RUN / "multidataset_resvgg_swin_seed0_best.pt",
}
CLASSES = ["BENIGN", "DOS_DDOS", "OTHER_ATTACK"]
# sample_type -> chỉ số lớp thật cần bốc mẫu
TYPE_TO_Y = {"benign": 0, "dos": 1, "other": 2}
SOURCE_NODE = {"cicddos2019": "Node A · CIC (client 1–2)", "unsw_nb15": "Node B · UNSW (client 3–4)"}


class Engine:
    """Nạp model + kho mẫu test, chạy dự đoán cho một sample_type."""

    def __init__(self) -> None:
        paths.configure(str(DATA), str(HERE / "_tmp"))
        self.models: dict[str, tuple[torch.nn.Module, dict]] = {}
        for key, ck in CHECKPOINTS.items():
            if not ck.exists():
                raise FileNotFoundError(f"Thiếu checkpoint: {ck}")
            model, meta = load_checkpoint(ck)
            self.models[key] = (model.eval(), meta)
        self.active = "prox"
        self.features = self.models["prox"][1]["features"]
        # Kho mẫu: pool[sample_type][source] = list flow test có nhãn thật tương ứng.
        # "both" gộp cả hai nguồn (dùng chung object, không nhân đôi bộ nhớ).
        self.pool: dict[str, dict[str, list[dict]]] = {
            t: {"both": [], "cicddos2019": [], "unsw_nb15": []} for t in TYPE_TO_Y}
        for source in ("cicddos2019", "unsw_nb15"):
            fp = DATA / "test" / f"{source}.parquet"
            if not fp.exists():
                continue
            test = pd.read_parquet(fp)
            feats = test[self.features].to_numpy(dtype=np.float32)
            ys = test["y"].to_numpy()
            labels = test["original_label"].astype(str).to_numpy()
            for t, y in TYPE_TO_Y.items():
                for i in np.flatnonzero(ys == y):
                    e = {"x": feats[i], "source": source,
                         "original_label": labels[i], "y": int(y)}
                    self.pool[t][source].append(e)
                    self.pool[t]["both"].append(e)
        self.rng = np.random.default_rng()
        self.counts = {"allow": 0, "block": 0}
        self.log: deque[dict] = deque(maxlen=200)
        self.lock = threading.Lock()

    def available_types(self) -> list[str]:
        return [t for t in TYPE_TO_Y if self.pool[t]["both"]]

    def model_info(self) -> dict:
        _, meta = self.models[self.active]
        name = "FedProx μ=0,1" if self.active == "prox" else "FedAvg (DAS)"
        return {"active": self.active, "name": name, "arch": meta.get("arch", "resvgg_swin"),
                "round": meta.get("round"), "classes": CLASSES}

    def check(self, sample_type: str, client_ip: str, source: str = "both") -> dict:
        """Bốc một flow test đúng loại (lọc theo nguồn nếu có), chạy model, ghi log."""
        if sample_type not in self.pool or not self.pool[sample_type]["both"]:
            sample_type = "benign"
        if source not in ("both", "cicddos2019", "unsw_nb15") or not self.pool[sample_type][source]:
            source = "both"
        bucket = self.pool[sample_type][source]
        s = bucket[int(self.rng.integers(len(bucket)))]
        model, _ = self.models[self.active]
        with torch.no_grad():
            logits = model(torch.tensor(s["x"]).unsqueeze(0))
            prob = torch.softmax(logits, 1).numpy()[0]
        pred = int(prob.argmax())
        allow = pred == 0  # chỉ BENIGN mới cho qua
        event = {
            "ts": time.strftime("%H:%M:%S"), "ip": client_ip, "sent": sample_type,
            "source": s["source"], "node": SOURCE_NODE.get(s["source"], s["source"]),
            "original_label": s["original_label"], "true": CLASSES[s["y"]],
            "pred": CLASSES[pred], "prob": round(float(prob[pred]), 4),
            "decision": "ALLOW" if allow else "BLOCK", "allow": allow,
            "model": self.active,
        }
        with self.lock:
            self.counts["allow" if allow else "block"] += 1
            self.log.appendleft(event)
        return event

    def snapshot(self) -> dict:
        with self.lock:
            return {"counts": dict(self.counts), "log": list(self.log),
                    "model": self.model_info(), "types": self.available_types()}


ENGINE: Engine | None = None


# ----------------------------------------------------------------- trang web
def page_site(event: dict) -> bytes:
    allow = event["allow"]
    color = "#16a34a" if allow else "#dc2626"
    verdict = "Được phép truy cập" if allow else "Truy cập bị từ chối"
    html = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cổng web demo</title>
<style>body{{font-family:system-ui,Segoe UI,sans-serif;background:#0b1220;color:#e5e7eb;
margin:0;display:grid;place-items:center;height:100vh}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:32px 40px;
max-width:520px;text-align:center;box-shadow:0 10px 40px rgba(0,0,0,.4)}}
.badge{{display:inline-block;padding:6px 14px;border-radius:999px;font-weight:700;
background:{color}22;color:{color};border:1px solid {color}}}
h1{{font-size:20px;margin:16px 0 8px}} .muted{{color:#9ca3af;font-size:14px;line-height:1.6}}
code{{background:#0b1220;padding:2px 6px;border-radius:6px;color:#93c5fd}}</style></head>
<body><div class="card">
<div class="badge">{verdict}</div>
<h1>Lá chắn model ResVGG-SwinNet</h1>
<p class="muted">Model dự đoán luồng này là <code>{event['pred']}</code>
(xác suất {event['prob']:.2%}).<br>
Nhãn thật của mẫu: <code>{event['true']}</code> · nguồn {event['node']}.<br>
{'Không có dấu hiệu bất thường — cho truy cập.' if allow else 'Có dấu hiệu tấn công — chặn (HTTP 403).'}</p>
</div></body></html>"""
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # tắt log mặc định cho gọn
        pass

    def _send(self, code: int, body: bytes, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _ip(self) -> str:
        return self.client_address[0]

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            q = parse_qs(u.query)
            stype = (self.headers.get("X-Sample-Type") or q.get("sample_type", ["benign"])[0]).lower()
            src = (self.headers.get("X-Source") or q.get("source", ["both"])[0]).lower()
            ev = ENGINE.check(stype, self._ip(), src)
            code = 200 if ev["allow"] else 403
            hdr = {"X-Decision": ev["decision"], "X-Pred-Label": ev["pred"],
                   "X-Prob": f"{ev['prob']}", "X-True-Label": ev["true"]}
            self._send(code, page_site(ev), extra=hdr)
        elif u.path == "/dashboard":
            self._send(200, DASHBOARD_HTML.encode("utf-8"))
        elif u.path == "/api/events":
            body = json.dumps(ENGINE.snapshot(), ensure_ascii=False).encode("utf-8")
            self._send(200, body, ctype="application/json; charset=utf-8")
        else:
            self._send(404, b"not found")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/switch":
            q = parse_qs(u.query)
            m = q.get("model", ["prox"])[0]
            if m in ENGINE.models:
                ENGINE.active = m
            self._send(200, json.dumps(ENGINE.model_info()).encode("utf-8"),
                       ctype="application/json; charset=utf-8")
        else:
            self._send(404, b"not found")


DASHBOARD_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bảng điều khiển — Máy server</title>
<style>
:root{--bg:#0b1220;--card:#111827;--line:#1f2937;--muted:#9ca3af;--green:#16a34a;--red:#dc2626}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:var(--bg);color:#e5e7eb}
header{padding:16px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:16px;flex-wrap:wrap}
h1{font-size:18px;margin:0}.pill{font-size:12px;color:var(--muted);border:1px solid var(--line);padding:4px 10px;border-radius:999px}
.wrap{padding:20px 24px;display:grid;gap:20px;grid-template-columns:1fr 1fr 2fr}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.big{font-size:44px;font-weight:800;line-height:1}.lbl{color:var(--muted);font-size:13px;margin-bottom:8px}
.allow .big{color:var(--green)}.block .big{color:var(--red)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}.tag{padding:2px 8px;border-radius:999px;font-weight:700;font-size:12px}
.ok{background:#16a34a22;color:var(--green)}.no{background:#dc262622;color:var(--red)}
.full{grid-column:1 / -1}.miss{color:#f59e0b}
button{background:#1f2937;color:#e5e7eb;border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer}
button.on{background:#2563eb;border-color:#2563eb}
</style></head><body>
<header>
  <h1>Máy server — Lá chắn model</h1>
  <span class="pill" id="model">model …</span>
  <span style="flex:1"></span>
  <button id="b-prox" onclick="sw('prox')">FedProx</button>
  <button id="b-das" onclick="sw('das')">FedAvg DAS</button>
</header>
<div class="wrap">
  <div class="card allow"><div class="lbl">Đã cho qua (BENIGN)</div><div class="big" id="allow">0</div></div>
  <div class="card block"><div class="lbl">Đã chặn (tấn công)</div><div class="big" id="block">0</div></div>
  <div class="card"><div class="lbl">Tỉ lệ chặn</div><div class="big" id="rate">0%</div>
    <div class="lbl" style="margin-top:10px">Tổng lượt: <span id="total">0</span></div></div>
  <div class="card full"><div class="lbl">Nhật ký thời gian thực (mới nhất ở trên)</div>
    <table><thead><tr><th>Giờ</th><th>IP</th><th>Gửi</th><th>Node nguồn</th>
    <th>Nhãn thật</th><th>Model đoán</th><th>Xác suất</th><th>Kết quả</th></tr></thead>
    <tbody id="log"></tbody></table></div>
</div>
<script>
async function tick(){
  try{
    const r = await fetch('/api/events'); const d = await r.json();
    const a=d.counts.allow, b=d.counts.block, t=a+b;
    document.getElementById('allow').textContent=a;
    document.getElementById('block').textContent=b;
    document.getElementById('total').textContent=t;
    document.getElementById('rate').textContent = t? Math.round(100*b/t)+'%':'0%';
    document.getElementById('model').textContent = 'Model: '+d.model.name+' · vòng '+(d.model.round??'?');
    document.getElementById('b-prox').className = d.model.active==='prox'?'on':'';
    document.getElementById('b-das').className = d.model.active==='das'?'on':'';
    const rows = d.log.map(e=>{
      const wrong = e.true!==e.pred ? ' miss':'';
      const tag = e.allow? '<span class="tag ok">ALLOW</span>':'<span class="tag no">BLOCK</span>';
      return `<tr><td>${e.ts}</td><td>${e.ip}</td><td>${e.sent}</td><td>${e.node}</td>
        <td>${e.true}</td><td class="${wrong}">${e.pred}</td><td>${(e.prob*100).toFixed(1)}%</td><td>${tag}</td></tr>`;
    }).join('');
    document.getElementById('log').innerHTML = rows;
  }catch(err){}
}
async function sw(m){ await fetch('/api/switch?model='+m,{method:'POST'}); tick(); }
tick(); setInterval(tick, 800);
</script></body></html>"""


def main():
    global ENGINE
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("Đang nạp model + kho mẫu test …")
    ENGINE = Engine()
    info = ENGINE.model_info()
    sizes = {t: len(ENGINE.pool[t]["both"]) for t in ENGINE.available_types()}
    print(f"OK. Model {info['name']} (vòng {info['round']}). Kho mẫu: {sizes}")
    print(f"  Trang web  : http://{args.host}:{args.port}/           (?sample_type=benign|dos|other)")
    print(f"  Dashboard  : http://{args.host}:{args.port}/dashboard")
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDừng server.")


if __name__ == "__main__":
    main()
