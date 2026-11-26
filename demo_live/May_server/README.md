# May_server — Thiết bị A (web + model gác cửa)

Web app của **thiết bị A**. Nạp checkpoint ResVGG-SwinNet của run 4 client, mỗi
request quy thành một flow test rồi chạy model để quyết định cho qua / chặn.

## Chạy
```powershell
# tại thư mục gốc dự án Final_Exam (cần .venv có torch)
.\.venv\Scripts\python.exe demo_live\May_server\serve.py --host 0.0.0.0 --port 8000
```

## Các đường dẫn
- `GET /`            trang web khách, model gác cửa (đọc `?sample_type=benign|dos|other`, `?source=cic|unsw`).
- `GET /dashboard`   màn hình vận hành: đếm ALLOW/BLOCK + log thời gian thực, đổi model FedProx/FedAvg.
- `GET /api/events`  JSON cho dashboard.
- `POST /api/switch?model=prox|das`  đổi checkpoint.

## Nguồn dữ liệu (cố định trong `serve.py`)
- Checkpoint: `results_modal_multidataset/20261122_152058_5ec64a/main/das/fl/`
  (`..._fedprox_mu0.1_best.pt` và `..._best.pt`).
- Test parquet: `data_paper_multi_4c/main/test/{cicddos2019,unsw_nb15}.parquet`.

Xem kết quả đo thật và kịch bản trình bày ở [`../KICH_BAN_DEMO.md`](../KICH_BAN_DEMO.md).
