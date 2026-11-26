# May_attack — Thiết bị B (bắn lưu lượng theo kịch bản)

Script tấn công của **thiết bị B**. Chỉ dùng thư viện chuẩn Python (urllib) —
không cần cài gì, không cần venv/torch. Copy thư mục này sang máy bạn cùng bàn
là chạy được.

## Chạy
```powershell
python attack.py --target http://<IP-máy-server>:8000 --phase all
```

## Tham số
- `--phase benign|dos|other|all` — pha tấn công (mặc định `all`).
- `--source both|cic|unsw` — lấy mẫu tấn công từ nguồn nào (pha benign luôn lấy cả hai).
- `--count N` / `--threads N` / `--rate R` — ghi đè số request / số luồng / req/s mỗi luồng (0 = hết tốc độ).
- `--timeout S` — timeout mỗi request.

Mỗi request gắn header `X-Sample-Type` (+ `X-Source`) để máy server phát lại đúng
loại flow thật từ tập test. Script đọc header `X-Decision` máy server trả về và in
tổng ALLOW/BLOCK mỗi pha, đối chiếu với dashboard.

Kết quả đo thật và kịch bản trình bày: [`../KICH_BAN_DEMO.md`](../KICH_BAN_DEMO.md).
