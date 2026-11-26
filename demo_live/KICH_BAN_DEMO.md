# Kịch bản demo trực tiếp — Web tích hợp model phát hiện tấn công

Demo hai thiết bị cho đồ án An toàn thông tin (FL phát hiện tấn công mạng,
CIC-DDoS2019 + UNSW-NB15, 3 lớp `BENIGN` / `DOS_DDOS` / `OTHER_ATTACK`,
model ResVGG-SwinNet huấn luyện bằng FedAvg/FedProx của run 4 client).

---

## 1. Hai thiết bị

| | Thiết bị A — **Máy server** (`May_server/`) | Thiết bị B — **Máy attack** (`May_attack/`) |
|---|---|---|
| Ai | Máy của bạn | Máy bạn cùng bàn |
| Chạy | `serve.py` — web + model gác cửa | `attack.py` — bắn 3 pha |
| Kết quả | Cho qua / từ chối + dashboard log | In số ALLOW/BLOCK mỗi pha |
| Cần | `.venv` (torch) + checkpoint + test parquet | Chỉ cần Python (thư viện chuẩn) |

Hai máy **cùng mạng LAN/Wi-Fi**. Máy attack gọi `http://<IP-máy-server>:8000`.
Không cần ping — chỉ cần mở được cổng 8000 (xem mục 6).

---

## 2. Cơ chế (điểm quan trọng nhất)

Model **không đọc gói tin thô**. Nó ăn **18 đặc trưng** dựng từ 8 trường flow
chuẩn (`duration_s, fwd/bwd_packets, fwd/bwd_bytes, fwd/bwd_iat_mean_s,
protocol_group` + đặc trưng phái sinh + one-hot protocol). Vì vậy mỗi request
được quy thành **một flow thật lấy từ tập test** đúng loại đang bắn, rồi đưa qua
model đã huấn luyện:

```
Máy attack ──HTTP (header X-Sample-Type)──►  Máy server /serve.py
                                              │ bốc 1 flow test đúng loại
                                              │ model.forward (CPU, thật)
                                              │ argmax:
                                              │   BENIGN        -> 200 (ALLOW)
                                              │   DOS_DDOS/OTHER -> 403 (BLOCK)
                                              ▼
                                      dashboard: đếm + log thời gian thực
```

Model chạy **forward thật**, không huấn luyện lại. Đặc trưng lấy từ **flow thật
trong tập test** (đã chốt) để kết quả tái lập đúng như báo cáo, thay vì tự đo
flow tại chỗ (phân phối lệch, demo hên xui). Đây là thỏa hiệp demo cần nói thẳng
với thầy: ranh giới nằm ở chỗ *phát lại flow thật* chứ không phải *bắt gói thời
gian thực*.

---

## 3. Kết quả đo thật của model (để không bị bất ngờ khi demo)

Đo trên toàn tập test, tỉ lệ **chặn đúng** (với tấn công) / **cho qua đúng** (với
BENIGN). Hai model đều có sẵn, đổi ngay trên dashboard:

| Loại bắn | Nguồn | FedProx μ=0,1 *(mặc định)* | FedAvg DAS |
|---|---|---|---|
| BENIGN (muốn ALLOW) | cả hai | **~86% cho qua** | ~98% cho qua |
| DOS_DDOS (muốn BLOCK) | **UNSW** | **~88% chặn** ✅ | ~79% chặn |
| OTHER_ATTACK (muốn BLOCK) | **UNSW** | **~81% chặn** ✅ | ~22% chặn |
| DOS_DDOS (muốn BLOCK) | **CIC** | ~40% chặn ⚠️ | ~38% chặn |

**Điểm mạnh:** model nhận diện tốt tấn công UNSW-NB15 (DoS và các loại khác) và
cho lưu lượng bình thường đi qua. **Điểm yếu thật:** DDoS của CIC-DDoS2019 trong
bài toán 3 lớp / 8 trường bị nhận nhầm nhiều (chỉ ~40% chặn) — đây là giới hạn
đã thấy trong `evaluation_by_dataset.csv` (cic `dos_recall ≈ 0,38`), không phải
lỗi demo.

**Khuyến nghị trình bày:** dùng **FedProx** (mặc định). Pha tấn công chính nên
bắn **nguồn UNSW** (`--source unsw`) để thấy lá chắn hoạt động rõ, rồi **chủ động
bắn thêm CIC** (`--source cic`) và nói đây là hướng cải thiện (future work). Trung
thực mà vẫn làm nổi được năng lực model.

---

## 4. Ba pha demo (máy attack)

| Pha | Ý nghĩa | Mặc định | Kỳ vọng |
|---|---|---|---|
| `benign` | Truy cập bình thường, chậm | 10 req, 1 luồng | ALLOW |
| `dos` | Flood DoS/DDoS nhiều luồng | 300 req, 20 luồng | BLOCK |
| `other` | Dò/khai thác (chỉ UNSW có) | 40 req, 4 luồng | BLOCK |
| `all` | Chạy lần lượt cả ba | | |

---

## 5. Cách chạy

### Máy server (thiết bị A, máy của bạn)
```powershell
# tại thư mục gốc dự án Final_Exam
.\.venv\Scripts\python.exe demo_live\May_server\serve.py --host 0.0.0.0 --port 8000
```
Mở màn hình chiếu vào **dashboard**: `http://localhost:8000/dashboard`.
(Trang web khách: `http://localhost:8000/` — thêm `?sample_type=dos` để thử tay.)

### Máy attack (thiết bị B, máy bạn cùng bàn)
```powershell
# Chỉ cần Python, không cần venv/torch. Thay IP bằng IP LAN máy server.
python attack.py --target http://192.168.1.50:8000 --phase all

# Kịch bản khuyến nghị cho buổi bảo vệ:
python attack.py --target http://192.168.1.50:8000 --phase benign
python attack.py --target http://192.168.1.50:8000 --phase dos  --source unsw
python attack.py --target http://192.168.1.50:8000 --phase other --source unsw
python attack.py --target http://192.168.1.50:8000 --phase dos  --source cic   # minh họa giới hạn
```

---

## 6. Mạng và tường lửa (hay vướng nhất)

Trên **máy server**:
```powershell
ipconfig                                   # xem IP LAN, vd 192.168.1.50
# Mở cổng 8000 cho mạng nội bộ (chạy PowerShell quyền admin):
New-NetFirewallRule -DisplayName "Demo ATTT 8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000
```
Trên **máy attack**, kiểm tra kết nối (không dùng ping):
```powershell
Test-NetConnection 192.168.1.50 -Port 8000      # TcpTestSucceeded : True là được
```

---

## 7. Cấu trúc thư mục

```
demo_live/
├── KICH_BAN_DEMO.md      ← tài liệu này
├── May_server/
│   ├── serve.py          web + model gác cửa + dashboard
│   └── README.md
└── May_attack/
    ├── attack.py         script bắn 3 pha (chỉ thư viện chuẩn)
    └── README.md
```

---

## 8. Giới hạn cần nói trước với thầy

- Đây là **IDS mô phỏng mức ứng dụng**, không phải IPS bắt gói inline thật.
- Quyết định dựa trên **flow thật phát lại từ tập test**, phản ánh đúng năng lực
  model đã báo cáo, nhưng không chứng minh việc trích flow thời gian thực.
- DDoS của CIC-DDoS2019 còn nhận diện yếu (mục 3) — nêu như hướng cải thiện.
