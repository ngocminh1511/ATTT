r"""Máy attack (thiết bị B): trang web điều khiển tấn công.

Mở một server nhỏ ngay trên máy attack (chỉ thư viện chuẩn). Trình duyệt vào
trang này để: nhập IP + cổng máy server, chỉnh số request / luồng / tốc độ,
chọn pha (benign / dos / other) rồi bấm Chạy. Mỗi request gọi lại hàm
`one_request` trong attack.py, kết quả ALLOW/BLOCK đổ về trang theo thời gian thực.

Chạy:
    python demo_live/May_attack/attack_gui.py            # mở http://localhost:9000
    python demo_live/May_attack/attack_gui.py --port 9000

Sau đó mở http://localhost:9000, điền IP/cổng của máy server (vd 192.168.1.50 / 8000).
File attack.py vẫn dùng được độc lập qua dòng lệnh như cũ.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from attack import one_request, PHASES  # noqa: E402

# nhãn nguồn trên giao diện -> giá trị X-Source mà máy server hiểu
SOURCE_MAP = {"both": "both", "cic": "cicddos2019", "unsw": "unsw_nb15"}


def run_stream(target: str, phase: str, count: int, threads: int, rate: float,
               source: str, timeout: float):
    """Chạy một pha, yield từng dòng JSON (bytes) tiến độ rồi dòng tổng kết."""
    target = target.rstrip("/")
    threads = max(1, min(threads, count))
    stats: Counter = Counter()
    lock = threading.Lock()
    per_thread = count // threads
    extra = count % threads
    t0 = time.time()

    def worker(n: int):
        for _ in range(n):
            decision, _pred, _prob = one_request(target, phase, timeout, source)
            with lock:
                stats[decision] += 1
            if rate > 0:
                time.sleep(1.0 / rate)

    pool = []
    for i in range(threads):
        n = per_thread + (1 if i < extra else 0)
        th = threading.Thread(target=worker, args=(n,), daemon=True)
        th.start()
        pool.append(th)

    def snapshot(done_flag: bool) -> bytes:
        with lock:
            allow = stats.get("ALLOW", 0)
            block = stats.get("BLOCK", 0)
            err = stats.get("ERR", 0)
        total = allow + block + err
        dt = time.time() - t0
        ev = {"type": "done" if done_flag else "progress",
              "done": total, "total": count, "allow": allow, "block": block,
              "err": err, "secs": round(dt, 1),
              "rps": round(total / dt, 0) if dt > 0 else 0}
        return (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")

    while any(th.is_alive() for th in pool):
        time.sleep(0.15)
        yield snapshot(False)
    for th in pool:
        th.join()
    yield snapshot(True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"))
        elif u.path == "/run":
            self._run(parse_qs(u.query))
        else:
            self._send(404, b"not found")

    def _run(self, q):
        def g(name, default):
            return q.get(name, [default])[0]
        ip = g("ip", "").strip()
        port = g("port", "8000").strip()
        phase = g("phase", "benign").lower()
        if phase not in PHASES:
            phase = "benign"
        cfg = PHASES[phase]
        try:
            count = max(1, int(g("count", cfg["count"])))
            threads = max(1, int(g("threads", cfg["threads"])))
            rate = max(0.0, float(g("rate", cfg["rate"])))
            timeout = max(0.5, float(g("timeout", "5")))
        except ValueError:
            self._send(400, b'{"error":"tham so khong hop le"}',
                       ctype="application/json; charset=utf-8")
            return
        src_sel = g("source", "both").lower()
        source = SOURCE_MAP.get(src_sel, "both")
        if phase == "benign":           # benign luôn lấy cả hai nguồn như attack.py
            source = "both"
        if not ip:
            self._send(400, b'{"error":"thieu IP"}',
                       ctype="application/json; charset=utf-8")
            return
        target = f"http://{ip}:{port}"

        # phát trực tiếp (chunked) để trang thấy tiến độ ngay
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            for line in run_stream(target, phase, count, threads, rate, source, timeout):
                self.wfile.write(f"{len(line):X}\r\n".encode() + line + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


PAGE = r"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Máy tấn công — Bảng điều khiển</title>
<style>
:root{--bg:#0b1220;--card:#111827;--line:#1f2937;--muted:#9ca3af;--green:#16a34a;
--red:#dc2626;--blue:#2563eb;--amber:#f59e0b}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;
background:var(--bg);color:#e5e7eb}
header{padding:16px 24px;border-bottom:1px solid var(--line)}
h1{font-size:18px;margin:0}.sub{color:var(--muted);font-size:13px;margin-top:4px}
.wrap{padding:20px 24px;display:grid;gap:20px;grid-template-columns:360px 1fr}
@media(max-width:820px){.wrap{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
label{display:block;font-size:12px;color:var(--muted);margin:12px 0 4px}
input,select{width:100%;background:#0b1220;color:#e5e7eb;border:1px solid var(--line);
border-radius:8px;padding:8px 10px;font-size:14px}
.row{display:flex;gap:10px}.row>div{flex:1}
.phases{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:6px}
.ph{background:#1f2937;border:1px solid var(--line);border-radius:8px;padding:8px;
cursor:pointer;text-align:center;font-size:13px}
.ph.on{background:var(--blue);border-color:var(--blue);color:#fff}
.run{margin-top:16px;width:100%;background:var(--red);color:#fff;border:none;
border-radius:10px;padding:12px;font-size:15px;font-weight:700;cursor:pointer}
.run:disabled{opacity:.5;cursor:default}
.stop{background:#374151}
.big{font-size:40px;font-weight:800;line-height:1}.lbl{color:var(--muted);font-size:13px}
.stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:16px}
.allow .big{color:var(--green)}.block .big{color:var(--red)}.err .big{color:var(--amber)}
.bar{height:10px;background:#0b1220;border-radius:999px;overflow:hidden;margin:6px 0 2px}
.bar>i{display:block;height:100%;background:var(--blue);width:0}
pre{background:#0b1220;border:1px solid var(--line);border-radius:10px;padding:12px;
font-size:12px;height:220px;overflow:auto;margin:0;white-space:pre-wrap}
.hint{color:var(--muted);font-size:12px;margin-top:4px}
code{background:#0b1220;padding:1px 5px;border-radius:5px;color:#93c5fd}
</style></head><body>
<header><h1>Máy tấn công — Bảng điều khiển</h1>
<div class="sub">Nhập IP/cổng máy server, chọn pha và bấm Chạy. Dùng cho demo trong mạng LAN đã được phép.</div></header>
<div class="wrap">
  <div class="card">
    <div class="row">
      <div><label>IP máy server</label><input id="ip" placeholder="192.168.1.50"></div>
      <div style="flex:.5"><label>Cổng</label><input id="port" value="8000"></div>
    </div>
    <label>Pha tấn công</label>
    <div class="phases" id="phases"></div>
    <div class="row">
      <div><label>Số request</label><input id="count" type="number" min="1"></div>
      <div><label>Số luồng</label><input id="threads" type="number" min="1"></div>
    </div>
    <div class="row">
      <div><label>Tốc độ (req/s mỗi luồng, 0 = tối đa)</label><input id="rate" type="number" min="0" step="0.5"></div>
      <div style="flex:.8"><label>Nguồn mẫu</label>
        <select id="source"><option value="both">both</option>
        <option value="cic">cic</option><option value="unsw">unsw</option></select></div>
    </div>
    <div class="hint" id="srcHint"></div>
    <button class="run" id="runBtn" onclick="run()">▶ Chạy</button>
  </div>

  <div class="card">
    <div class="stats">
      <div class="allow"><div class="lbl">ALLOW (cho qua)</div><div class="big" id="sAllow">0</div></div>
      <div class="block"><div class="lbl">BLOCK (bị chặn)</div><div class="big" id="sBlock">0</div></div>
      <div class="err"><div class="lbl">ERR (lỗi mạng)</div><div class="big" id="sErr">0</div></div>
    </div>
    <div class="lbl"><span id="prog">0 / 0</span> · <span id="rps">0</span> req/s · <span id="secs">0</span>s</div>
    <div class="bar"><i id="barFill"></i></div>
    <label style="margin-top:14px">Nhật ký</label>
    <pre id="log">Chưa chạy.</pre>
  </div>
</div>
<script>
const DEF = __PHASES__;
let phase = 'benign', running = false;
const phBox = document.getElementById('phases');
const names = {benign:'Benign (bình thường)', dos:'DoS/DDoS (flood)', other:'Other (dò/khai thác)'};
Object.keys(DEF).forEach(k=>{
  const d=document.createElement('div'); d.className='ph'+(k===phase?' on':''); d.textContent=names[k]||k;
  d.onclick=()=>{phase=k; fillDefaults(); [...phBox.children].forEach(c=>c.classList.remove('on')); d.classList.add('on');};
  phBox.appendChild(d);
});
function fillDefaults(){
  const c=DEF[phase];
  document.getElementById('count').value=c.count;
  document.getElementById('threads').value=c.threads;
  document.getElementById('rate').value=c.rate;
  document.getElementById('srcHint').textContent = phase==='benign'
    ? 'Pha benign luôn lấy cả hai nguồn.' : 'Chọn nguồn để demo tương phản CIC / UNSW.';
}
fillDefaults();
function setRunning(on){
  running=on; const b=document.getElementById('runBtn');
  b.disabled=on; b.textContent = on? '⏳ Đang chạy…' : '▶ Chạy';
}
async function run(){
  if(running) return;
  const ip=document.getElementById('ip').value.trim();
  if(!ip){ alert('Nhập IP máy server'); return; }
  const p=new URLSearchParams({
    ip, port:document.getElementById('port').value.trim()||'8000', phase,
    count:document.getElementById('count').value, threads:document.getElementById('threads').value,
    rate:document.getElementById('rate').value, source:document.getElementById('source').value });
  const log=document.getElementById('log');
  log.textContent='Mục tiêu: http://'+ip+':'+(document.getElementById('port').value||'8000')+'  · pha '+phase+'\n';
  setRunning(true);
  try{
    const resp=await fetch('/run?'+p.toString());
    const reader=resp.body.getReader(); const dec=new TextDecoder(); let buf='';
    while(true){
      const {value,done}=await reader.read(); if(done) break;
      buf+=dec.decode(value,{stream:true}); const lines=buf.split('\n'); buf=lines.pop();
      for(const ln of lines){ if(ln.trim()) update(JSON.parse(ln)); }
    }
  }catch(e){ log.textContent+='\nLỗi: '+e; }
  setRunning(false);
}
function update(e){
  document.getElementById('sAllow').textContent=e.allow;
  document.getElementById('sBlock').textContent=e.block;
  document.getElementById('sErr').textContent=e.err;
  document.getElementById('prog').textContent=e.done+' / '+e.total;
  document.getElementById('rps').textContent=e.rps;
  document.getElementById('secs').textContent=e.secs;
  document.getElementById('barFill').style.width=(100*e.done/e.total)+'%';
  if(e.type==='done'){
    const log=document.getElementById('log');
    log.textContent+='\nXong '+e.done+' request trong '+e.secs+'s ('+e.rps+' req/s): '
      +'ALLOW='+e.allow+'  BLOCK='+e.block+'  ERR='+e.err;
    if(e.err) log.textContent+='\n(ERR: không kết nối được — kiểm tra IP/cổng/tường lửa)';
    log.scrollTop=log.scrollHeight;
  }
}
</script></body></html>"""


def main():
    global PAGE
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    PAGE = PAGE.replace("__PHASES__", json.dumps(PHASES))
    print("Bảng điều khiển máy tấn công đang chạy.")
    print(f"  Mở trình duyệt: http://localhost:{args.port}/")
    print("  (Dùng cho demo trong mạng LAN đã được phép.)")
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDừng bảng điều khiển.")


if __name__ == "__main__":
    main()
