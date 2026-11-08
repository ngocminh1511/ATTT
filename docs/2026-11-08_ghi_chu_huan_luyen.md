# Ghi chú về huấn luyện và đánh giá mô hình — 08/11/2026

Ngày ghi: **08/11/2026** (Asia/Saigon). Mã nguồn tham chiếu: commit `27d72ce`.

Tài liệu lưu lại trao đổi để xử lý sau. Các đề xuất bên dưới **chưa được áp dụng vào code và chưa có lượt train lại**.

## 1. Nhận định về mức độ hoàn thiện

Bộ kết quả hiện có đủ để trình bày một đồ án thực nghiệm ban đầu: đã có 22 thí nghiệm, nhiều kiến trúc, các baseline và đối chứng về cách chia dữ liệu/rò rỉ nhãn. Tuy nhiên, nên sửa quy trình validation và cách chọn mô hình trước khi chốt kết quả chính thức.

Chưa có cơ sở để khẳng định ResVGG-SwinNet tốt hơn các mô hình đơn giản hơn trong thiết lập hiện tại. Cũng chưa thể suy ra rằng chỉ tăng số epoch hoặc số vòng FL sẽ cải thiện khả năng phát hiện trên ngày khác.

## 2. Cách huấn luyện hiện tại

| Thành phần | Thiết lập |
|---|---|
| Dữ liệu | CIC-DDoS2019 |
| Đầu vào sau tiền xử lý của bản `main` trên máy | 36 đặc trưng |
| Đầu ra | 12 lớp đã biết khi train; lớp 0 là BENIGN |
| Mô hình chính | ResVGG-SwinNet |
| Số client | 3, chia dữ liệu giữ tỷ lệ nhãn gần giống nhau |
| Thuật toán gộp | FedAvg, có trọng số theo số mẫu train của client |
| Số vòng FL | 30 |
| Epoch cục bộ mỗi vòng | 5 |
| Optimizer | Adam |
| Learning rate | `0.001` |
| Batch size | `64` |
| Dropout | `0.3` |
| Loss trong FL | Cross-entropy có trọng số lớp MTB |
| Validation hiện tại | Tách 10% mỗi client sau khi dữ liệu đã qua tiền xử lý và sinh/cân bằng mẫu |
| Mô hình được lưu | Mô hình toàn cục ở vòng cuối |

Đây là mô phỏng FL bằng Flower/Ray. Trên Modal, ba client trong một thí nghiệm dùng chung GPU của container. Chưa phải triển khai ba máy độc lập, và các client hiện có phân phối nhãn gần IID.

### “30 vòng × 5 epoch” nghĩa là gì?

- **Một epoch:** mô hình đi qua toàn bộ phần dữ liệu train của một client một lần.
- **Một vòng FL (round):** server gửi mô hình, các client học cục bộ, rồi server nhận và gộp trọng số.

Trong mỗi vòng:

1. Server gửi cùng mô hình toàn cục cho cả ba client.
2. Mỗi client học 5 epoch trên dữ liệu riêng.
3. Các client gửi trọng số và số mẫu về server.
4. Server dùng FedAvg tạo mô hình chung mới.
5. Vòng tiếp theo bắt đầu từ mô hình chung vừa gộp.

Lặp 30 vòng có nghĩa mỗi client đi qua phần train của mình tổng cộng **30 × 5 = 150 lượt**, còn server gộp mô hình **30 lần**. Đây là 150 lượt học cục bộ có các lần gộp xen kẽ; không hoàn toàn tương đương train tập trung liên tục 150 epoch.

Ví dụ: client có 1.000 mẫu train sẽ học qua 1.000 mẫu đó 5 lần trong một vòng, rồi gửi trọng số về server. Các vòng sau tiếp tục sử dụng phần dữ liệu train đó.

## 3. Kết quả đang có và cách diễn giải

Các số dưới đây là kết quả ở vòng cuối của ResVGG-SwinNet; F1 là điểm phát hiện nhị phân BENIGN/attack, không phải accuracy.

| Biến thể | Thiết lập | F1 nhị phân | Recall tấn công | Tỷ lệ báo nhầm | Số seed |
|---|---|---:|---:|---:|---:|
| `main` | AFN theo protocol, train/test khác ngày | 70,15% | 55,89% | 6,75% | 3 |
| `random` | AFN theo protocol, chia ngẫu nhiên cùng ngày | 99,91% | 99,98% | 0,30% | 1 |
| `leak` | AFN dùng nhãn thật của test, train/test khác ngày | 99,63% | 99,30% | 0,08% | 1 |

`main` là trung bình ba seed. Những điểm cần trình bày trung thực:

- Recall 55,89% tương ứng bỏ sót khoảng 44,11% mẫu tấn công trên tập test này.
- Trong `main`, tỷ lệ phát hiện mẫu SYN là tấn công chỉ khoảng **12,31%**; recall phân loại đúng lớp SYN khoảng **0,19%**. Hai số này đo hai nhiệm vụ khác nhau.
- F1-macro của ResVGG-SwinNet trong `main` khoảng **56,37%**.
- ResNet-only có F1 nhị phân trung bình khoảng **78,96%**, cao hơn mức trung bình của mô hình kết hợp trong các lượt chạy đã có. Chưa có kiểm định để kết luận ưu thế thống kê.
- Điểm cao của `random` và `leak` cho thấy kết quả phụ thuộc mạnh vào điều kiện đánh giá. `leak` phục vụ minh họa rò rỉ nhãn, không đại diện cho cách dự đoán khi chưa biết nhãn thật.
- PortScan chỉ xuất hiện trong test: được tính vào đánh giá phát hiện nhị phân, nhưng bị loại khỏi loss và metric đa lớp. F1-macro hiện tính trên các lớp đã biết có mặt trong tập đánh giá.

Báo cáo gốc:

- [Kết quả `main`](../results_modal/full/main/summary.md).
- [Kết quả `random`](../results_modal/full/random/summary.md).
- [Kết quả `leak`](../results_modal/full/leak/summary.md).
- [Trạng thái 22 thí nghiệm](../results_modal/full/status.json).

## 4. Những vấn đề đã xác định

### Validation chưa độc lập với quá trình chuẩn bị train

Hiện các file client đã qua AFN, CTA, DPCA, DAS, DRA và LIS trước khi `load_local()` tách 10% validation. Vì vậy, phần validation đã tham gia vào việc tính tham số tiền xử lý hoặc quá trình sinh/chọn mẫu.

Kiểm tra trên **bản `data_paper` cục bộ**, dùng cách tách hiện tại với seed 0, cho kết quả:

| Client | Số mẫu validation | Số mẫu validation có vector đặc trưng trùng mẫu train | Tỷ lệ |
|---|---:|---:|---:|
| 1 | 5.846 | 776 | 13,27% |
| 2 | 5.845 | 762 | 13,04% |
| 3 | 5.834 | 756 | 12,96% |

Đối chiếu dựa trên 36 đặc trưng đầu vào, bỏ qua index và nhãn. Đây là kiểm tra trùng hoàn toàn, chưa đo các mẫu gần giống nhau. Số liệu này thuộc bản dữ liệu cục bộ, chưa phải kiểm tra độc lập mọi bản dữ liệu trên Modal.

Không nên xem validation F1 gần 100% hiện tại là bằng chứng chắc chắn về khả năng tổng quát. Phát hiện này liên quan đến validation; bản thân nó chưa chứng minh test khác ngày của `main` bị rò rỉ nhãn như biến thể `leak`.

### Chưa chọn checkpoint bằng validation

Server đang đánh giá test mỗi vòng và chỉ lưu mô hình cuối. Việc ghi điểm test không tự cập nhật trọng số; tuy nhiên, dùng điểm test để chọn vòng, ngưỡng hoặc cấu hình sẽ làm thiên lệch đánh giá.

Cột “F1 tốt nhất (vòng)” nên được xem là phân tích mô tả. Trong báo cáo tổng hợp nhiều seed, số vòng hiển thị là trung bình các vòng tốt nhất của từng seed, không nhất thiết là một vòng chung có thể chọn để triển khai.

### So sánh với baseline còn khác điều kiện

- FL học trên 90% dữ liệu của mỗi file client, giữ 10% để validation.
- Centralized và Local-only hiện học toàn bộ file client.
- FL dùng trọng số lớp MTB; hai baseline dùng cách tính trọng số theo tần suất khi không truyền MTB.
- Các kiến trúc FL trong `main` có ba seed, còn `random`, `leak` và hai thí nghiệm baseline mới dùng một seed cấu hình.

Các khác biệt này cần được kiểm soát hoặc mô tả rõ trước khi kết luận về lợi ích của FL hay kiến trúc.

## 5. Thứ tự xử lý đề xuất khi quay lại

1. **Sửa cách chia train/validation:** giữ validation từ các mẫu gốc trước khi fit tham số tiền xử lý và trước CTA/DPCA. Kiểm tra trùng lặp; nếu có các mẫu thuộc cùng flow/phiên thì cân nhắc giữ cùng một phía của phép chia.
2. **Chỉ học tham số trên train:** fit AFN, DAS, DRA, LIS và tính trọng số lớp từ train; validation/test chỉ áp dụng các phép biến đổi đã học. Chỉ sinh/cân bằng mẫu trong train.
3. **Dùng validation để chọn mô hình:** xác định trước metric lựa chọn, lưu checkpoint tốt nhất; nếu mục tiêu chính là phân loại đa lớp thì cân nhắc F1-macro. Test dùng để đánh giá mô hình sau khi đã chốt.
4. **Đồng bộ baseline:** dùng cùng phần dữ liệu train và cách tính loss/class weight phù hợp với mục tiêu so sánh; ghi rõ ngân sách huấn luyện.
5. **Chạy lại các thí nghiệm trọng tâm:** bắt đầu với ResVGG-SwinNet và ResNet-only trong `main`, cùng ba seed. Hoàn thiện các đối chứng và baseline với cùng bộ seed để đánh giá độ biến động.
6. **Sau đó mới chỉnh siêu tham số:** giữ 30 vòng × 5 epoch làm mốc ban đầu; lựa chọn learning rate, số epoch cục bộ, checkpoint hoặc ngưỡng phát hiện dựa trên validation đã làm sạch. Không mặc định tăng số vòng để tìm điểm test cao hơn.

Tập test hiện đã được xem trong quá trình phân tích. Cần mô tả trung thực điều này nếu tiếp tục dùng kết quả của tập đó để định hướng thử nghiệm.

## 6. File cần xem khi thực hiện

| Công việc | File |
|---|---|
| Chia dữ liệu và điều phối tiền xử lý | [`prepare/paper_pipeline.py`](../prepare/paper_pipeline.py) |
| Các phép AFN, CTA, DPCA, MTB, DAS, DRA, LIS | [`fl_ddos/paper_prep.py`](../fl_ddos/paper_prep.py) |
| Tách validation, DataLoader, hàm train và metric | [`fl_ddos/task.py`](../fl_ddos/task.py) |
| Train/evaluate ở client | [`fl_ddos/client_app.py`](../fl_ddos/client_app.py) |
| Gộp trọng số, đánh giá và lưu checkpoint | [`fl_ddos/server_app.py`](../fl_ddos/server_app.py) |
| Train hai baseline | [`baselines/common.py`](../baselines/common.py) |
| Cấu hình FL mặc định | [`pyproject.toml`](../pyproject.toml) |
| Điều phối thí nghiệm trên Modal | [`modal_app.py`](../modal_app.py) |
| Giải thích pipeline chi tiết | [`pipeline_hien_tai.md`](pipeline_hien_tai.md) |

Tài liệu tham khảo cho các đề xuất đánh giá:

- [imbalanced-learn: rò rỉ dữ liệu do resampling trước khi chia tập](https://imbalanced-learn.org/stable/common_pitfalls.html).
- [scikit-learn: giữ riêng validation và test khi lựa chọn mô hình](https://scikit-learn.org/stable/modules/cross_validation.html).
