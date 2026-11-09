# Chạy hai dataset trên Modal

Entrypoint: `modal_multidataset.py`; logic kiểm tra bundle/lệnh/báo cáo: `fl_ddos/modal_multidataset_jobs.py`.
Pipeline CIC cũ trong `modal_app.py` và Volume `fl-ddos` được giữ riêng.

Hệ thống hiện có 2 client: PID 0 = CIC-DDoS2019, PID 1 = UNSW-NB15; 3 lớp BENIGN / DOS_DDOS / OTHER_ATTACK.
IoT-23 đã bị loại ngày 09/11/2026 (xem mục cuối).

## Dữ liệu và tính tái lập

Chuẩn bị đủ `data_paper_multi/{smoke,smoke_all,main,main_all}` trên máy trước khi chạy. Bộ chạy kiểm tra
pipeline, policy `class_quota_v3`, PID 0/1, hash schema/preprocessor/split và cùng subset giữa DAS/all.
Bundle chỉ có 56 artifact cần thiết (14 tệp × 4 thư mục), không chứa raw hoặc dữ liệu cũ.
Từng tệp có SHA-256 và kích thước; digest manifest tạo bundle ID. Upload vào Volume riêng
`fl-ddos-multidataset:/datasets/{bundle_id}/`. Container xác minh lại checksum trước khi train.
Không chia tập, fit tiền xử lý hay lấy subset lại trên Modal.

## Thí nghiệm

GPU A100 (fallback A100-80GB), tối đa 4 experiment container đồng thời, mỗi container 4 CPU/16 GiB RAM.
Mỗi experiment dùng một GPU; hai Flower client chạy lần lượt, mỗi round đều có đủ hai client.

Smoke gồm FL DAS và all (seed 0, 2 vòng × 1 epoch), centralized và local-only (2 epoch).
Chỉ khi tất cả smoke job có đủ best checkpoint, đúng hash và đánh giá đủ hai nguồn mới bắt đầu main.
Một local-only job tạo hai mô hình riêng, mỗi mô hình được đánh giá trên cả hai test.

Main gồm FL DAS và all × seed 0, 30 vòng × 5 epoch; centralized và local-only dùng DAS, seed 0,
150 epoch. Mọi cấu hình chỉ chạy một seed, nên không có độ lệch chuẩn giữa các lần chạy.
FL dùng scenario `multidataset`, chọn checkpoint theo validation; chỉ best checkpoint được đánh giá test.
Baseline gọi `baselines/multidataset_baselines.py`, dùng đúng cùng train/val/test và quy tắc class weight.

## Khởi chạy và theo dõi

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[cloud]"
.\.venv\Scripts\modal.exe profile list
.\.venv\Scripts\modal.exe run --detach modal_multidataset.py
```

`--smoke-only` chỉ chạy smoke. Với `--detach`, controller ở Modal tiếp tục smoke/main dù máy local
ngắt kết nối. Entrypoint ghi `logs/modal_multidataset_{run_id}.json` gồm app ID, function call ID,
bundle ID và lệnh tải kết quả. Mỗi lần khởi chạy tạo run ID mới; không ghi đè kết quả cũ.

Trên Volume:

```text
/datasets/{bundle_id}/bundle_manifest.json
/datasets/{bundle_id}/{smoke,smoke_all,main,main_all}/...
/runs/{run_id}/status.json
/runs/{run_id}/{smoke|main}/{job}/status.json
/runs/{run_id}/{smoke|main}/{job}/artifacts/command_1.log
/runs/{run_id}/{smoke|main}/{job}/artifacts/fl/..._best.pt
/runs/{run_id}/results/{smoke|main}/{das|all}/summary.md
```

Trạng thái mỗi job chuyển running → completed/failed, ghi GPU và thời gian. Controller ghi kết quả
đã nhận và dừng trước main nếu smoke lỗi. Log và artifact dở dang vẫn được lưu khi subprocess lỗi.
SDK không tự retry cả thí nghiệm dài; mỗi experiment có timeout 6 giờ, controller 24 giờ.
Đánh giá kiểm tra đủ checkpoint, hash, đủ round và phản hồi hai client để tránh CLI trả 0 nhưng train lỗi.

```powershell
# Tiến độ của lượt chạy mới nhất và tải các báo cáo smoke đã hoàn tất:
.\.venv\Scripts\python.exe scripts/modal_multidataset_status.py --download smoke
# Khi main hoàn tất, tải toàn bộ kết quả đã gộp:
.\.venv\Scripts\python.exe scripts/modal_multidataset_status.py --download all
.\.venv\Scripts\modal.exe app logs APP_ID
```

Main đang chạy chưa phải kết quả hoàn tất. Chỉ tổng hợp điểm khi status là completed; điểm smoke
được đánh dấu chỉ phục vụ kiểm tra tích hợp.

## Lượt 3 dataset đã dừng (09/11/2026)

Run `20261109_103203_b3c28e` (app `ap-2cOZLkTbpc3JwbxhtZ22Y4`) dùng cấu hình cũ 3 client có IoT-23 và
đã bị dừng thủ công khi main xong 4/8 job. Trên IoT-23, FL DAS seed 0 đạt acc 0,10 và FL all seed 0 đạt
0,05; gần như mọi flow PortScan bị đoán là BENIGN. Nguyên nhân: chia theo capture khiến mỗi tập IoT-23
chỉ do 1–2 capture chi phối, và tỷ lệ thiếu `duration` lệch giữa train/val/test (59% / 98% / 93%).
Kết quả lượt này không dùng cho hệ thống 2 client.
