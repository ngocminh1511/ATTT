# Federated Learning phát hiện DDoS (theo ResVGG-SwinNet)

Cài đặt lại phương pháp của bài báo trong `docs/futureinternet-17-00088-v2 1.pdf`:

> Alshdadi et al., *Federated Deep Learning for Scalable and Privacy-Preserving DDoS Attack Detection in IoT Networks*, Future Internet 2025, 17, 88.

Mỗi client train mô hình ResVGG-SwinNet trên dữ liệu của mình và chỉ gửi trọng số về server, server gộp bằng FedAvg. Dữ liệu được tiền xử lý theo đúng chuỗi bước của paper (AFN, CTA, MTB, DPCA, DAS, FDP, FRP). Pipeline gốc làm trên **CIC-DDoS2019**. Phần mở rộng **multidataset_v1** (mục 7) chạy FL với 2 client, mỗi client một dataset (CIC-DDoS2019 / UNSW-NB15), 3 lớp BENIGN / DOS_DDOS / OTHER_ATTACK.

Pipeline cũ (FL + Suricata, mô tả trong file `.docx` ở `docs/`) đã bỏ phần Suricata. Phần FL nhị phân với MLP và các kịch bản S1–S4 vẫn giữ lại để so sánh (mục 6).

## Cấu trúc

| Thư mục / file | Mục trong paper | Nội dung |
|---|---|---|
| `fl_ddos/paper_prep.py` | 3.2–3.6 | AFN, TEC, CTA, DPCA (WIS + FBSA), MTB, DAS (CRA + IDF), NDS/JAA, DRA, LIS. Bước nào cần thống kê toàn cục thì client chỉ gửi tổng, server gộp |
| `prepare/paper_pipeline.py` | 3.2–3.6, Eq.13 | CIC-DDoS2019 → `data_paper/` (3 client, đa lớp) |
| `fl_ddos/models.py` | 3.7, Bảng 12 | ResVGG-SwinNet, các biến thể ablation (`resnet`, `resnet_vgg`, `resnet_swin`), baseline `lstm`, `lstm_gru`; MLP dành cho pipeline cũ |
| `fl_ddos/task.py` | 4 | Nạp dữ liệu, train (class weight MTB, FedProx), metric: F1/Recall/FAR/AUC (nhị phân) + MSI, F1-macro, Log Loss, AUC-OvR (đa lớp) |
| `fl_ddos/client_app.py` / `server_app.py` | 3.7.2, Bảng 6, 8 | Flower ClientApp/ServerApp (Flower 1.40), FedAvg hoặc FedTrimmedAvg. Ghi thời gian, bộ nhớ, ‖Δw‖ của từng client |
| `baselines/` | — | Centralized (cận trên), Local-only (cận dưới), chọn được kiến trúc |
| `analysis/plots.py` | 5.2 | `summary.md`, F1 theo vòng, cột F1, ma trận nhầm lẫn nhị phân + đa lớp, ROC, heatmap theo loại tấn công |
| `fl_ddos/features.py` | — | `slog1p`, đọc `features.json`/`scaler.json`, chuẩn hóa tên nhãn CIC |
| `prepare/preprocess_csv.py`, `split_clients.py`, `federated_scaler.py`, `make_synthetic.py` | — | Pipeline cũ (mục 6) |
| `scripts/` | — | `fl_run.*` (bọc `flwr run`), `run_all.*` (ma trận cũ E1–E5) |
| `configs/multidataset.json` | — | multidataset_v1: nguồn tải, bảng nhãn, profile smoke/main, split, AFN, DAS |
| `fl_ddos/dataset_adapters.py` | — | Parser CIC Parquet / UNSW CSV, nhãn 3 lớp, schema 8 trường |
| `fl_ddos/multidataset_prep.py` | 3.2, 3.5 | Reservoir, split theo nhóm, quota, log1p + AFN có missing, DAS pooled, transform, artifacts |
| `fl_ddos/multidataset_server.py`, `multidataset_eval.py` | — | FedAvg 3 nguồn, chọn best bằng validation; đánh giá một checkpoint trên 3 test |
| `prepare/download_datasets.py`, `prepare/multidataset_pipeline.py` | — | Tải/kiểm tra raw; CLI pipeline |
| `analysis/evaluate_multidataset.py`, `baselines/multidataset_baselines.py`, `scripts/run_multidataset.ps1` | — | Đánh giá, baseline local/centralized, ma trận thí nghiệm |
| `tests/` | — | Kiểm thử bằng fixture nhỏ: `python -m unittest discover -s tests` |

## 1. Môi trường

Venv có sẵn ở `.venv` (Python 3.12, torch 2.14.1+cu126, flwr 1.40.0). Phiên bản đầy đủ nằm trong `requirements.lock.txt`. Nếu cần cài lại:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\Activate.ps1
```

**Lưu ý về Flower 1.40** (`scripts/fl_run.ps1` / `fl_run.sh` đã xử lý sẵn, nên luôn chạy FL qua script):
- Số client truyền bằng `--federation-config "num-supernodes=3"`. Script làm việc này qua tham số `-Clients`.
- Script đặt `FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION=1` để dùng luôn venv có torch CUDA.
- App chạy từ bản sao trong `~/.flwr/apps/`, nên script truyền đường dẫn tuyệt đối qua `data-dir` / `results-dir`. Mặc định là `data_paper/` và `results_paper/`.
- Đổi biến môi trường mà không thấy tác dụng: SuperLink cục bộ vẫn chạy nền với môi trường cũ. Dừng `flower-superlink` rồi chạy lại.

**RAM và GPU.** Mỗi Ray actor nạp torch CUDA, tốn khoảng 0,5–1 GB RAM. Máy 16 GB đang mở nhiều ứng dụng sẽ gặp các lỗi sau:

| Lỗi | Cách xử lý |
|---|---|
| `paging file is too small` (WinError 1455) | Giảm `-Actors` (về 1), đóng bớt ứng dụng |
| `available for tasks and actors (0.03 GB) is less than 0%` | `$env:RAY_DEFAULT_OBJECT_STORE_MEMORY_PROPORTION = "0.15"`, dừng `flower-superlink` rồi chạy lại |
| `CUDA-capable device(s) is/are busy or unavailable` | Ray chỉ cho actor thấy GPU khi được cấp, nên thêm `-Gpus 1` |

Cấu hình gợi ý cho ResVGG-SwinNet: `.\scripts\fl_run.ps1 "..." -Actors 1 -Gpus 1`. Ba client sẽ lần lượt dùng GPU.

## 2. Dữ liệu theo paper (CIC-DDoS2019)

Tải bản đã làm sạch trên Kaggle `dhoogla/cicddos2019` (Parquet) rồi đặt vào `data/raw/cicddos2019/`. **Tên file của bản này bị đảo**: `*-testing.parquet` là ngày 12/01 (DrDoS_*, NTP, TFTP…), `*-training.parquet` là ngày 11/03 (có Portmap). Script đã đặt mặc định theo đúng chiều này.

```powershell
python prepare/paper_pipeline.py                                    # -> data_paper/ (mặc định: test = ngày 11/03)
python prepare/paper_pipeline.py --split random --out data_paper_random   # test = 20% ngày 12/01, giống paper
python prepare/paper_pipeline.py --afn label --out data_paper_leak        # AFN nguyên văn paper, để minh họa rò rỉ nhãn
```

Các bước chạy theo đúng thứ tự trong paper:

| Bước | Paper | Ở đâu | Ghi chú |
|---|---|---|---|
| log1p | — | tại chỗ | `slog1p` cho mọi đặc trưng (CIC rất lệch đuôi). Paper không nói |
| TEC | Eq.11 | trên từng file, trước khi lấy mẫu | `flow_packets_s`, `flow_bytes_s`, `flow_iat_mean`, cửa sổ τ = 10 flow trước đó |
| Chia client | Eq.13 | — | 3 client, mỗi phần giữ phân phối nhãn như tập gốc (paper Bảng 6: 3 client cho mỗi dataset) |
| AFN | Eq.1 | liên kết | z-score theo nhóm **protocol** (TCP/UDP/khác) |
| CTA | Eq.2 | cục bộ | Thêm 20% mẫu bằng cách trộn hai mẫu cùng lớp, gần nhau theo thời gian |
| DPCA | Eq.4–6 | cục bộ | WIS sinh mẫu cho lớp dưới n̄, FBSA bớt lớp trên n̄. Mọi lớp về ≈ n̄ |
| MTB | Eq.3 | cục bộ | Class weight cho loss → `{scenario}/mtb_weights.json` |
| DAS | Eq.7–9 | liên kết | Relevance r² với từng lớp; bỏ đặc trưng tương quan ≥ γ = 0,9; giữ tối đa 25 |
| FDP | Eq.10, 12 | tại chỗ | NDS cho các cặp trong 4 đặc trưng đầu, JAA cho 2 bộ ba |
| FRP | Eq.14–15 | liên kết | DRA (min-max về [0, 1]), sau đó nhân hệ số LIS |

Output trong `data_paper/`:
- `features.json`: đặc trưng cuối, danh sách lớp, các đặc trưng được DAS chọn.
- `prep_params.json`: relevance DAS của mọi đặc trưng, min/max của DRA, hệ số LIS. Dùng để vẽ hình 11–12 của paper.
- `paper/client_1..3.parquet`.
- `paper/summary.csv`: số mẫu mỗi lớp trước/sau DPCA (hình 6).
- `paper/mtb_weights.json`.
- `test_day2.parquet`.

Tập test chỉ đi qua các phép biến đổi đã fit trên train, không bị sinh hay bớt mẫu.

### Những chỗ khác paper (và lý do)

1. **AFN không nhóm theo nhãn.** Eq.1 chuẩn hóa riêng nhóm attack và nhóm normal, tức là phải biết nhãn mới chọn được μ, σ. Lúc test không có nhãn, nên nếu dùng nhãn thật thì đó là rò rỉ nhãn. Code nhóm theo protocol vì protocol đọc được từ header. `--afn label` giữ đúng cách của paper để so sánh, và tập test khi đó dùng nhãn thật.
2. **Thời gian = thứ tự dòng trong file.** Bản Kaggle không có cột Timestamp. TEC, CTA và MTB dùng `t_order` (thứ tự dòng trong file) thay cho thời gian. TEC tính trên toàn bộ file trước khi lấy mẫu, chỉ nhìn về phía trước.
3. **Eq.3 (MTB)** cho trọng số lớn với lớp xuất hiện nhiều. Code dùng nghịch đảo của nó làm class weight (chuẩn hóa về trung bình 1, cắt trong [0,1; 10]).
4. **Cách đưa dữ liệu vào CNN/Swin.** Paper không nói cách đưa vector đặc trưng vào CNN/Swin. Code chiếu F đặc trưng thành lưới 8×8 bằng một lớp Linear, sau đó là 2 ResBlock (32 kênh), 2 conv VGG 3×3 (64 kênh), 2 khối Swin (cửa sổ 4, dịch 2) và softmax. Code dùng GroupNorm thay BatchNorm, vì FedAvg trung bình hóa running-stats của BatchNorm sẽ làm lệch mô hình.
5. **Chia train/test.** Mặc định test trên **ngày khác** (11/03). Đây là cách chặt chẽ hơn paper: paper không nêu cách chia, và số 99% thường đến từ việc chia ngẫu nhiên trong cùng ngày. `--split random` cho phép so sánh hai cách chia.
6. **Lớp chỉ có ở test.** PortScan chỉ có ở ngày test và mô hình chưa từng thấy lớp này. Nó chỉ được tính vào phần phát hiện nhị phân (tấn công / BENIGN), không tính vào MSI hay F1-macro.
7. **OES (Optimisation Efficiency Score)** không có công thức trong paper. Server ghi thời gian, bộ nhớ đỉnh và ‖Δw‖ của từng client (`*_clients.csv`) để định nghĩa OES sau.

## 3. Huấn luyện liên kết

Mặc định trong `pyproject.toml` lấy theo paper mục 5.1: 30 vòng, 5 epoch cục bộ, lr 0.001, dropout 0.3, batch 64, FedAvg, `arch = "resvgg_swin"`.

```powershell
.\scripts\fl_run.ps1 "" -Actors 1 -Gpus 1                                  # ResVGG-SwinNet, 3 client, 30 vòng
.\scripts\fl_run.ps1 "num-server-rounds=2 local-epochs=1" -Actors 1 -Gpus 1  # chạy thử nhanh
.\scripts\fl_run.ps1 "arch='resnet'" -Actors 1 -Gpus 1                     # ablation: resnet | resnet_vgg | resnet_swin
.\scripts\fl_run.ps1 "arch='lstm'" -Actors 1 -Gpus 1                       # baseline: lstm | lstm_gru
.\scripts\fl_run.ps1 "tag-suffix='_random'" -DataDir data_paper_random -ResultsDir results_paper -Actors 1 -Gpus 1

$env:FL_DDOS_DATA = "$PWD\data_paper"; $env:FL_DDOS_RESULTS = "$PWD\results_paper"
python baselines/centralized.py --scenario paper --epochs 150    # = 30 vòng × 5 epoch
python baselines/local_only.py  --scenario paper --epochs 150
python analysis/plots.py                                          # results_paper/figures/*.png + summary.md
```

Kết quả nằm trong `results_paper/fl/`:

| File | Nội dung |
|---|---|
| `{scenario}_{arch}_mu{μ}_{strategy}_seed{n}.csv` | Mỗi vòng một dòng: F1/Recall/FAR/AUC (nhị phân), MSI, F1-macro, Log Loss, AUC-OvR, `comm_MB`, F1 cục bộ TB và độ lệch giữa client |
| `*_clients.csv` | Mỗi vòng × client: loss, số mẫu, thời gian train, bộ nhớ GPU đỉnh, ‖Δw‖ |
| `*_global.pt` | `{"arch", "dropout", "state_dict"}` của mô hình cuối |

Ngoài ra có `results_paper/per_attack.csv` (tỉ lệ bị gắn là tấn công theo từng loại) và `per_class.csv` (recall đúng loại tấn công).

FedProx (`proximal-mu`), FedTrimmedAvg (`strategy='trimmed'`) và đầu độc nhãn (`poison-clients`) vẫn có, nhưng paper chỉ dùng FedAvg.

### Chạy trên Modal (tắt máy vẫn chạy)

`modal_app.py` đẩy toàn bộ thí nghiệm lên GPU đám mây của Modal. Bộ điều phối cũng chạy trên Modal, nên với `--detach` có thể tắt máy. Mỗi thí nghiệm là một container GPU L4 riêng (3 client dùng chung một GPU), tối đa 8 container chạy song song. Kết quả nằm trong Volume `fl-ddos`.

```powershell
# một lần đầu
modal volume create fl-ddos
modal volume put fl-ddos data/raw/cicddos2019 /raw/cicddos2019

modal run modal_app.py --quick           # thử 2 vòng × 1 epoch (resvgg_swin + lstm): chạy trước để chắc không lỗi
modal run --detach modal_app.py          # chạy đầy đủ rồi tắt máy
modal volume get fl-ddos /results/full ./results_modal   # sáng dậy lấy kết quả
```

Bản đầy đủ mặc định gồm:
- 6 kiến trúc × 3 seed trên `main` (không có baseline MLP).
- ResVGG-SwinNet trên `random` (chia như paper) và `leak` (AFN theo nhãn).
- Centralized và Local-only.

Tổng cộng 22 thí nghiệm. Thu hẹp lại bằng `--seeds 0 --archs resvgg_swin,resnet --variants main --no-baselines`. `results_modal/full/status.json` ghi thí nghiệm nào lỗi; log từng container xem ở https://modal.com/apps. Nếu cần gộp và vẽ lại mà không train: `modal run modal_app.py::report`.

### Xem kết quả đã chạy

Kết quả đầy đủ được lưu trong Git tại [`results_modal/full/`](results_modal/full/), gồm báo cáo, biểu đồ trong `figures/`, metric CSV và trọng số mô hình `.pt`. Có thể xem trực tiếp các báo cáo dưới đây mà không cần tải dataset hoặc chạy train:

| Biến thể | Cấu hình | Báo cáo |
|---|---|---|
| `main` | AFN theo protocol; train/test khác ngày | [Kết quả chính](results_modal/full/main/summary.md) |
| `random` | AFN theo protocol; chia ngẫu nhiên 80/20 trong cùng ngày | [Kết quả chia cùng ngày](results_modal/full/random/summary.md) |
| `leak` | AFN theo nhãn, dùng nhãn thật của test để chọn nhóm chuẩn hóa; train/test khác ngày | [Kết quả minh họa rò rỉ nhãn](results_modal/full/leak/summary.md) |

Cột F1 trong báo cáo đánh giá phát hiện nhị phân BENIGN/attack; F1-macro đánh giá phân loại đa lớp. [`status.json`](results_modal/full/status.json) ghi trạng thái và thời gian của 22 thí nghiệm. [Tài liệu pipeline hiện tại](docs/pipeline_hien_tai.md) giải thích các bước xử lý và huấn luyện.

Dữ liệu gốc `data/raw/cicddos2019/`, dữ liệu đã xử lý `data_paper*/`, môi trường ảo, log và các lượt chạy thử được bỏ qua trong `.gitignore`.

## 4. Phân tích

`analysis/plots.py` sinh ra:
- `f1_vs_round.png`, `bar_f1.png`.
- `confusion_roc.png`: nhị phân + ROC.
- `confusion_multiclass.png`: hàng là nhãn thật trên test, kể cả PortScan; chuẩn hóa theo hàng.
- `heatmap_recall_{scenario}.png`.
- `summary.md`: thêm cột MSI và F1-macro.

Mặc định đọc `data_paper/` + `results_paper/`. Với pipeline cũ thì thêm `--data-dir data --results-dir results`.

Chưa làm: kiểm định thống kê (paper Bảng 11), phân tích độ nhạy lr × dropout (Hình 15), OES.

## 5. Notebook

| Notebook | Nội dung |
|---|---|
| `notebooks/01_hieu_dataset.ipynb` | Giải thích CIC-DDoS2019: flow, từng loại tấn công, ý nghĩa đặc trưng, mất cân bằng, khác biệt giữa hai ngày, cách chia client S1–S4 |
| `notebooks/02_phan_tich_ket_qua.ipynb` | Đọc kết quả E1–E7 của **pipeline cũ** (`results/`) |
| `notebooks/03_tien_xu_ly_hai_dataset.ipynb` | multidataset_v1: nguồn, ánh xạ nhãn/đặc trưng, chất lượng, split, DAS, kết quả theo nguồn |

Mở bằng kernel **Python (fl-ddos)**: `pip install -e .[notebook]` rồi `python -m ipykernel install --user --name fl-ddos`.

## 6. Pipeline cũ (MLP nhị phân, S1–S4)

Mã hỗ trợ MLP với 5 client vẫn được giữ để tham khảo. Dữ liệu đã chia S1–S4, dữ liệu giả lập, kết quả `results/` và hai script `run_all.*` đã được dọn. Muốn chạy lại luồng cũ cần tạo lại dữ liệu; các lệnh dưới đây mô tả cách thực hiện từng bước:

```powershell
python prepare/preprocess_csv.py --train-glob "data/raw/cicddos2019/*-testing.parquet" --test-glob "data/raw/cicddos2019/*-training.parquet"
python prepare/split_clients.py          # data/S1 S2a S2b S3 S4/client_1..5.parquet
python prepare/federated_scaler.py       # data/scaler.json
.\scripts\fl_run.ps1 "scenario='S3' arch='mlp' local-epochs=2 batch-size=256 dropout=0.2" -Clients 5 -DataDir data -ResultsDir results
python analysis/plots.py --data-dir data --results-dir results
```

Chưa có dataset thì chạy `python prepare/make_synthetic.py` rồi `preprocess_csv.py --train-glob "data/raw/synthetic/01-12/*.csv" --test-glob "data/raw/synthetic/03-11/*.csv"`. Dữ liệu giả chỉ để kiểm tra code chạy được, **không dùng làm kết quả**.

## 7. Hai dataset: 2 client × 3 lớp (multidataset_v1)

| Client | partition-id | Dataset | Test |
|---|---:|---|---|
| 1 | 0 | CIC-DDoS2019 | `*-training.parquet` (quy ước hiện tại) |
| 2 | 1 | UNSW-NB15 | testing-set chính thức |

Đầu ra 0 = BENIGN, 1 = DOS_DDOS (gộp DoS của UNSW và DDoS của CIC), 2 = OTHER_ATTACK (chỉ có ở UNSW; client CIC
có class weight = 0 cho lớp này). Đầu vào: dữ liệu gốc có 77 (CIC) và 42 (UNSW) đặc trưng; schema chung giữ
8 trường có ở cả hai (`duration_s`, gói / byte / IAT trung bình theo từng chiều, `protocol_group`) -> 17 cột liên tục
(log1p + AFN theo protocol, missing -> 0) qua DAS (θ = 0,001, γ = 0,9, tối đa 12) + 6 cột cố định (one-hot protocol,
cờ duration thiếu/bằng 0), nên F = 7–18. Byte của CICFlowMeter và Argus lệch nhau phần header. Không sinh mẫu.
Best checkpoint chọn bằng TB đều F1-macro-present của hai validation (không đọc test trong lúc train).

Train/val tách bằng 5-fold theo nhóm fingerprint (vector trùng nhau không nằm ở cả train và val); test là tập
riêng của từng nguồn. Policy lấy mẫu `class_quota_v3`: bản main tối đa 100.000 train/nguồn, đặt sàn
10.000 mẫu/lớp có mặt (nguồn thiếu thì giữ toàn bộ và ghi cảnh báo, không nhân bản). Validation bắt đầu
20.000, test bắt đầu 50.000, tự tăng để mỗi lớp có mặt đạt 200 / 500 mẫu; giữ tỷ lệ lớp tự nhiên, không đủ
mẫu thật thì dừng. Xem `sampling_report.md`, `quality_report.json`. Smoke chỉ kiểm tra tích hợp.

IoT-23 từng là client thứ 3 và đã bị loại ngày 09/11/2026: chia theo capture làm phân phối train/val/test
lệch nặng, mô hình gần như không phát hiện được tấn công trên test IoT-23 (xem [docs/modal_hai_dataset.md](docs/modal_hai_dataset.md)).

```powershell
# 1. Dữ liệu: CIC kiểm tra checksum; UNSW (bản sao Nir-J/ML-Projects khóa commit nếu không có URL chính thức)
.\.venv\Scripts\python.exe prepare/download_datasets.py
# 2. Pipeline
.\.venv\Scripts\python.exe prepare/multidataset_pipeline.py --profile smoke
# 3. FL smoke + đánh giá
.\scripts\fl_run.ps1 "scenario='multidataset' num-server-rounds=2 local-epochs=1 seed=0" -Clients 2 -Actors 1 -DataDir data_paper_multi/smoke -ResultsDir results_multidataset/smoke
.\.venv\Scripts\python.exe analysis/evaluate_multidataset.py --data-dir data_paper_multi/smoke --results-dir results_multidataset/smoke --checkpoint "results_multidataset/smoke/fl/*_best.pt"
# Toàn bộ ma trận (FL DAS và đối chứng toàn bộ cột × seed 0, local-only, centralized, đánh giá):
.\scripts\run_multidataset.ps1 -Profile main -Gpus 1
```

Artifacts: `data_paper_multi/{smoke|main}[_all]/` (features.json, prep_params.json, dataset_manifest.json,
split_manifest.parquet, quality_report.json, sampling_report.md, feature_selection.csv, `multidataset/client_k|val_client_k.parquet`,
class_weights.json, `test/{dataset}.parquet`). Kết quả: `results_multidataset/{profile}/` (`fl/*_best.pt`, `*_last.pt`,
`*_rounds.csv`, `*_clients.csv`, evaluation_by_dataset.csv, per_class.csv, per_original_label.csv, confusion.csv,
figures/, summary.md). Notebook giải thích: `notebooks/03_tien_xu_ly_hai_dataset.ipynb`.

Pipeline dừng (không xuất artifacts) khi có nhãn lạ/mâu thuẫn, split vi phạm ràng buộc nhóm, hoặc DAS không chọn
được cột nào. Server dừng khi thiếu/trùng PID, round lệch hoặc metric validation không hữu hạn.
Chạy trên Modal bằng `modal_multidataset.py` (file `modal_app.py` dành cho pipeline CIC cũ):

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[cloud]"
# Upload đúng artifact smoke/main và DAS/all đã chuẩn bị, kiểm tra SHA-256 trên cloud.
# Smoke đạt mới tự chạy main: 2 FL (DAS/all × seed 0) + 2 baseline, tối đa 4 GPU A100 đồng thời.
.\.venv\Scripts\modal.exe run --detach modal_multidataset.py
# Chỉ kiểm tra tích hợp trên Modal:
.\.venv\Scripts\modal.exe run --detach modal_multidataset.py --smoke-only
```

App và Volume riêng tên `fl-ddos-multidataset`. Dữ liệu bất biến ở `/datasets/{bundle_id}/`, trạng thái ở
`/runs/{run_id}/status.json`, log/checkpoint theo từng job; kết quả gộp ở
`/runs/{run_id}/results/{smoke|main}/{das|all}/`. Run ID mới giữ nguyên các lần chạy trước.
Thông tin app/call/run và lệnh tải kết quả được lưu trong `logs/modal_multidataset_{run_id}.json`.
Chi tiết: [chạy hai dataset trên Modal](docs/modal_hai_dataset.md).

## Lỗi thường gặp

- **F1 = 0,999 ngay từ vòng 1 khi test trên ngày khác**: nghi rò rỉ dữ liệu. Kiểm tra cột định danh và chế độ `--afn`.
- **`plots.py` báo thiếu cột / sai số lớp**: `--data-dir` không khớp với `--results-dir`, ví dụ mô hình train trên `data_paper` nhưng lại vẽ với `data`.
- **`UnicodeEncodeError` trên Windows**: đặt `$env:PYTHONIOENCODING="utf-8"`. Các script trong `scripts/` đã đặt sẵn.
