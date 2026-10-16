# Federated Learning + Suricata phân tán phát hiện DDoS

Cài đặt pipeline mô tả trong `docs/Federated Learning + Suricata phân tán phát hiện DDoS — Pipeline đồ án cuối kỳ.docx`:
nhiều sensor Suricata, mỗi sensor là một FL client, chỉ gửi trọng số mô hình về server. Server gộp bằng FedAvg/FedProx,
sau đó mô hình toàn cục được triển khai ngược về sensor để phát hiện DDoS thời gian thực.

## Cấu trúc

| Thư mục / file | Mục trong tài liệu | Nội dung |
|---|---|---|
| `fl_ddos/features.py` | 4.3, 7.2 | Tiền xử lý **dùng chung** cho train và realtime: slog1p, đặc trưng flow eve.json, cửa sổ 1 giây theo `dest_ip`, chuẩn hóa nhãn CIC |
| `fl_ddos/task.py` | 6.3 | `DDoSNet` (MLP ~10–12k tham số), nạp dữ liệu, train (class weight + FedProx), metric |
| `fl_ddos/client_app.py` / `server_app.py` | 6.4, 6.5 | Flower ClientApp/ServerApp (Message API, Flower 1.40), FedAvg hoặc FedTrimmedAvg |
| `prepare/make_synthetic.py` | — | Sinh dữ liệu **giả** (CSV kiểu CIC + eve.json) để chạy thử khi chưa có dataset |
| `prepare/preprocess_csv.py` | 4.2 | Nhánh A: CSV/Parquet CIC-DDoS2019 → `train_pool.parquet`, `test_day2.parquet`, `features.json` |
| `prepare/suricata_to_features.py` | 4.3 | Nhánh B: eve.json + file khoảng tấn công → đặc trưng Suricata |
| `prepare/split_clients.py` | 4.4 | Chia S1 (IID), S2a/S2b (Dirichlet α = 0,5 / 0,1), S3 (theo loại tấn công), S4 (lệch kích thước) |
| `prepare/federated_scaler.py` | 4.5 | Chuẩn hóa liên kết: client chỉ gửi n, Σx, Σx² → `scaler.json` |
| `baselines/` | 6.7 | Centralized (cận trên), Local-only (cận dưới) |
| `detector/realtime.py` | 7.2, 7.3 | Theo dõi eve.json, chấm điểm từng flow, cảnh báo theo cửa sổ, tuỳ chọn chế độ IPS (`--drop-rules`) |
| `analysis/plots.py` | 8.3, 8.4 | `results/summary.md` + các hình F1 theo vòng, cột F1, ma trận nhầm lẫn/ROC, heatmap recall, boxplot độ trễ |
| `lab/` | 5, 7, E6 | Docker Compose: fl-server, 3 chi nhánh (victim + sensor), attacker; `measure_latency.py` |
| `scripts/` | 6.6 | `fl_run.*` (bọc `flwr run`), `run_all.*` (ma trận E1–E5 × 3 seed) |

## 1. Môi trường

Venv đã được tạo sẵn tại `.venv` (Python 3.12, torch 2.14.1+cu126, flwr 1.40.0). Danh sách phiên bản đầy đủ nằm trong `requirements.lock.txt`. Nếu cần cài lại:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\Activate.ps1
```

**Lưu ý về Flower 1.40** (đã được xử lý trong `scripts/fl_run.ps1` / `fl_run.sh`, nên hãy luôn chạy FL qua script này):
- Mục `[tool.flwr.federations]` trong pyproject đã bị bỏ. Số client được truyền bằng `--federation-config "num-supernodes=5"`.
- Mặc định Flower tạo một môi trường riêng và cài lại dependency cho mỗi run. Script đặt `FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION=1` để dùng luôn venv có torch CUDA.
- App chạy từ bản sao trong `~/.flwr/apps/`, nên script truyền đường dẫn tuyệt đối qua run-config `data-dir` / `results-dir`.
- Mỗi Ray actor nạp torch (khoảng 0,5 GB RAM). Với máy 16 GB, script giới hạn 3 actor chạy song song (`-Actors 3`). Lỗi `MemoryError: Unable to allocate internal buffer` nghĩa là cần giảm số này.
- Nếu đổi biến môi trường mà không thấy tác dụng: SuperLink cục bộ vẫn chạy nền với môi trường cũ. Dừng tiến trình `flower-superlink` rồi chạy lại.

## 2. Dữ liệu (Nhánh A — CSV CIC-DDoS2019)

Tải bản đã làm sạch trên Kaggle `dhoogla/cicddos2019` (Parquet), hoặc CSV gốc từ UNB, rồi đặt vào `data/raw/`.

```powershell
# CSV gốc: data/raw/01-12/*.csv (ngày train) và data/raw/03-11/*.csv (ngày test)
python prepare/preprocess_csv.py
# hoặc bản Kaggle (parquet):
#   CHÚ Ý: tên file của bản Kaggle bị đảo so với tài liệu: *-testing = ngày 12/01 (DrDoS_*, NTP, TFTP…),
#   *-training = ngày 11/03 (có Portmap). Bản này không có SSDP, WebDDoS chỉ 51 mẫu.
python prepare/preprocess_csv.py --train-glob "data/raw/cicddos2019/*-testing.parquet" --test-glob "data/raw/cicddos2019/*-training.parquet"

python prepare/split_clients.py          # data/S1 S2a S2b S3 S4/client_1..5.parquet + summary.csv
python prepare/federated_scaler.py       # data/scaler.json
```

Các bước này đảm bảo theo tài liệu: bỏ các cột định danh (IP, Flow ID, Timestamp, port nguồn…); train lấy ngày 12/01, test lấy ngày 11/03 (không chia ngẫu nhiên trong cùng một ngày); PortScan chỉ có ở tập test; scaler không fit trên dữ liệu gộp.

**Chưa có dataset?** Chạy `python prepare/make_synthetic.py`, sau đó chạy `preprocess_csv.py` với `--train-glob "data/raw/synthetic/01-12/*.csv" --test-glob "data/raw/synthetic/03-11/*.csv"`. Dữ liệu giả chỉ để kiểm tra code chạy được, **không dùng làm kết quả báo cáo** (F1 ≈ 0,99 vì dữ liệu dễ).

## 3. Huấn luyện liên kết + baseline (E1–E5, E7)

```powershell
.\scripts\fl_run.ps1 "scenario='S3'"                                  # FedAvg, 30 vòng
.\scripts\fl_run.ps1 "scenario='S3' proximal-mu=0.1 seed=1"            # FedProx
.\scripts\fl_run.ps1 "scenario='S1' poison-clients='0' strategy='trimmed'"   # E7
python baselines/centralized.py --scenario S1 --epochs 60
python baselines/local_only.py  --scenario S3 --epochs 60

.\scripts\run_all.ps1                                                 # toàn bộ ma trận × 3 seed (rất lâu)
.\scripts\run_all.ps1 -Rounds 2 -Seeds 0 -Epochs 2 -Scenarios S1,S3 -Mus 0.0,0.1   # chạy thử nhanh
python analysis/plots.py                                              # results/figures/*.png + results/summary.md
```

Kết quả FL nằm trong `results/fl/{scenario}_mu{μ}_{strategy}_seed{n}.csv`, mỗi dòng là một vòng. Mỗi dòng gồm F1/Recall/FPR/AUC/PR-AUC trên test ngày 2, `comm_MB`, F1 cục bộ trung bình và độ lệch F1 giữa các client. Mô hình cuối được lưu ở `*_global.pt`.

## 4. Nhánh B — đặc trưng Suricata (cần cho phát hiện realtime)

```bash
# Trong WSL/Docker: phát lại PCAP qua Suricata
suricata -c lab/sensor/suricata.yaml -r attack.pcap -l out/day1 -k none
```
```powershell
python prepare/suricata_to_features.py --train-eve out/day1/eve.json --train-labels day1_attacks.csv `
    --test-eve out/day2/eve.json --test-labels day2_attacks.csv --out data_eve
$env:FL_DDOS_DATA = "$PWD\data_eve"
python prepare/split_clients.py --n-clients 3 --scenarios S1; python prepare/federated_scaler.py
Remove-Item Env:FL_DDOS_DATA
.\scripts\fl_run.ps1 "scenario='S1'" -Clients 3 -DataDir data_eve -ResultsDir results_eve
```
Nhãn lấy từ file CSV `label,start,end,dest_ip,src_ip` (cùng định dạng `attack_log.csv` của lab). Có thể thử ngay bằng `data/raw/synthetic_eve/day{1,2}/`.

## 5. Phát hiện thời gian thực

```powershell
$env:FL_DDOS_DATA = "$PWD\data_eve"     # features.json phải là Nhánh B
python detector/realtime.py --model results_eve/fl/S1_mu0.0_fedavg_seed0_global.pt `
    --eve data/raw/synthetic_eve/day2/eve.json --replay
```
Lệnh trên in các `ml_alert`, ghi `ml_alerts.json` cạnh eve.json, và cuối cùng in thời gian suy luận theo ms/flow. Khi chạy thật thì bỏ `--replay` (đọc tiếp eve.json giống `tail -f`). Thêm `--drop-rules ml.rules` để chuyển sang chế độ IPS.

## 6. Lab Docker (E6)

```powershell
# 1) Dữ liệu cục bộ cho 3 chi nhánh (Nhánh B) + đặt data/features.json, data/scaler.json, data/test_day2.parquet của Nhánh B
python prepare/split_clients.py --n-clients 3 --scenarios S1 --tag lab      # -> data/lab/client_1..3.parquet
# 2) Dựng lab (Docker Desktop + WSL2)
docker compose -f lab/docker-compose.yml up -d --build
# 3) Khai báo SuperLink của lab cho CLI: thêm vào %USERPROFILE%\.flwr\config.toml
#    [superlink.lab]
#    address = "127.0.0.1:9093"
#    insecure = true
.\.venv\Scripts\flwr.exe run . lab --stream --run-config "scenario='lab' num-clients=3"
# 4) Triển khai mô hình: copy results\fl\lab_..._global.pt thành results\global.pt (sensor tự nạp)
# 5) Tấn công trong mạng cô lập + đo
docker compose -f lab/docker-compose.yml exec attacker bash /lab/traffic.sh site1-victim all
python lab/measure_latency.py            # results/lab_latency.csv; sau đó chạy analysis/plots.py
```
Trong lab, mạng `mgmt` chỉ chở trọng số mô hình, còn các mạng `siteN` chở traffic và đều có `internal: true`. Sensor dùng chung network namespace với victim để Suricata thấy được traffic. Attacker dùng `hping3 -i u100` thay cho `--flood` và bị giới hạn CPU để tránh treo laptop.

**Chưa kiểm chứng:** file compose đã được kiểm tra cú pháp bằng `docker compose config`, nhưng các image chưa được build và lab chưa được chạy thật. Nên chạy `suricata -T` trong container sensor trước. Tên cờ của `flower-supernode` / `flower-superlink` cũng nên đối chiếu với trang "How to run Flower locally" của bản 1.40.

## Lỗi thường gặp (mục 9.3)

- F1 = 0,999 ngay từ vòng 1 trên dữ liệu thật: khả năng cao bị rò rỉ dữ liệu. Kiểm tra lại cột định danh và kiểm tra đúng là đang test trên ngày 2.
- Detector báo động loạn: `features.json`/`scaler.json` của detector không cùng Nhánh B với mô hình.
- `UnicodeEncodeError` trên Windows: đặt `$env:PYTHONIOENCODING="utf-8"` (các script trong `scripts/` đã đặt sẵn).
