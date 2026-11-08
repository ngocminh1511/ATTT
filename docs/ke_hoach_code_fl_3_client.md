# Kế hoạch chi tiết: FL với 3 client và 3 lớp

Cập nhật: **08/11/2026**, múi giờ Asia/Saigon. Mã nguồn tham chiếu: **27d72ce**.

**Người dùng đã chốt 3 client, mỗi client một dataset, và 3 lớp BENIGN / DOS_DDOS / OTHER_ATTACK.** Người dùng cũng đã chọn tự tải và tích hợp hai nguồn còn thiếu. Tài liệu này thay thế kế hoạch sơ bộ trước đó; các thông số kỹ thuật còn lại được chốt thành mặc định triển khai bên dưới.

Trạng thái: **đã lập kế hoạch; chưa triển khai pipeline, tải toàn bộ dataset hoặc train lại**.

## 1. Mục tiêu và phạm vi phiên bản đầu

| Client | Flower partition-id | Dataset riêng |
|---|---:|---|
| 1 | 0 | CIC-DDoS2019 |
| 2 | 1 | UNSW-NB15 |
| 3 | 2 | IoT-23 |

- Mỗi nguồn được tách train/validation/test. Client chỉ học train của nguồn được gán.
- Cả ba client dùng cùng đặc trưng, thứ tự cột, phép biến đổi và thứ tự lớp; server gộp bằng FedAvg.
- Đầu ra là **0 = BENIGN, 1 = DOS_DDOS, 2 = OTHER_ATTACK**.
- Kết quả dự đoán chỉ đến cấp nhóm. Nhãn gốc được lưu để phân tích, không phải đầu ra phân loại SYN/DNS/Exploits chi tiết.
- Mô hình chính là ResVGG-SwinNet hiện có; DAS là phương pháp chọn đặc trưng.
- Chọn mô hình bằng validation. Đánh giá cùng một checkpoint trên ba tập test, giữ nguyên trọng số và ngưỡng.
- Logic nằm trong Python; notebook gọi lại logic để khảo sát và trình bày.
- Tích hợp từ **bảng flow có sẵn**, tận dụng CIC Parquet hiện tại, UNSW CSV và IoT conn.log.labeled. Trích xuất lại PCAP nằm ngoài v1.

Hình 14, trang 20 của paper hiển thị Normal / SYN Flood / UDP Flood / HTTP GET / Slowloris. Paper chưa cung cấp mapping đủ rõ để tái lập năm lớp đó từ nhãn gốc của cả ba nguồn. Ba lớp và ba client trong kế hoạch là điều chỉnh đã chốt của đồ án; không tuyên bố tái lập nguyên vẹn thiết lập hoặc điểm số của paper.

## 2. Cấu hình triển khai đã chọn

| Thành phần | Giá trị v1 |
|---|---|
| Scenario / pipeline metadata | multidataset / multidataset_v1 |
| Số client và số lớp | 3 / 3 |
| Seed chuẩn bị dữ liệu | 42 |
| Seed huấn luyện chính | 0, 1, 2; dùng lại cùng split và subset dữ liệu |
| Mô hình | resvgg_swin |
| FL | FedAvg theo số mẫu train thực tế, cả ba client tham gia mỗi vòng |
| Optimizer / learning rate | Adam / 0.001 |
| Batch size / dropout | 64 / 0.3 |
| Số vòng / epoch cục bộ | 30 / 5 |
| Cân bằng lớp | Class weight tính riêng từ train mỗi client |
| Chuẩn hóa | log1p biến liên tục, sau đó AFN theo protocol quan sát được, tham số train chung |
| DAS | CRA + IDF hiện có; theta = 0.001, gamma = 0.9, tối đa 8 cột liên tục |
| Chọn checkpoint | Trung bình đều F1-macro trên các lớp có support của validation ba nguồn |
| Quy tắc hòa checkpoint | Giữ vòng sớm hơn; không chọn vòng 0 |
| Ngưỡng metric nhị phân | 0.5, cố định trong v1 |
| Profile smoke | Mỗi nguồn: tối đa 1.000 train / 500 validation / 1.000 test; 2 vòng × 1 epoch, seed 0 |
| Profile main | Mỗi nguồn: tối đa 100.000 train / 20.000 validation / 50.000 test |
| Đầu ra mới | data_paper_multi và results_multidataset |

Các giới hạn mẫu được áp dụng sau khi xác định split, lấy mẫu theo tỷ lệ lớp và giữ ít nhất một mẫu của lớp có mặt nếu ngân sách cho phép. Nếu nguồn/split có ít mẫu hơn giới hạn thì giữ toàn bộ, không nhân bản. Báo cáo ghi số mẫu gốc và số mẫu sử dụng; không gọi subset test là toàn bộ benchmark.

V1 không sinh mẫu. CTA, DPCA, TEC, MTB theo thời gian, NDS/JAA và DRA/LIS không nằm trên đường chạy mặc định mới. Điều này tránh dùng thời gian giả, nội suy protocol hoặc làm tăng mạnh lớp hiếm trước khi có baseline ba nguồn hợp lệ. Các hàm cũ được giữ phục vụ pipeline CIC và các mở rộng sau; không thay chúng bằng Spearman hoặc phương pháp chọn đặc trưng khác.

## 3. Chuẩn bị và tải dữ liệu

### 3.1. Nguồn và định dạng

| Dataset | Nguồn dùng | Cách xử lý |
|---|---|---|
| CIC | 17 Parquet hiện có ở data/raw/cicddos2019 | Dùng nhóm *-testing làm train pool, *-training làm test theo quy ước hiện tại; ghi đúng quy ước trong manifest |
| UNSW | Hai CSV train/test gốc, tham chiếu trang UNSW | Đối chiếu header, 175.341 / 82.332 dòng và tập nhãn trước khi dùng |
| IoT | Bản labeled-flow small của nhà phát hành | Đọc conn.log.labeled theo từng capture từ archive; không cần PCAP |

Tham chiếu: [UNSW](https://research.unsw.edu.au/projects/unsw-nb15-dataset), [IoT-23](https://www.stratosphereips.org/datasets-iot23), [CIC](https://www.unb.ca/cic/datasets/ddos-2019.html).

URL archive IoT:

~~~text
https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/iot_23_datasets_small.tar.gz
~~~

Đã kiểm tra HTTP Range trong lúc lập kế hoạch: server trả gzip, kích thước công bố qua Content-Range là 9.373.916.249 byte, xấp xỉ 8,73 GiB. Kích thước thực tế phải được kiểm tra lại khi tải.

Link nguồn UNSW chính thức trỏ đến SharePoint; lần kiểm tra bằng công cụ web bị timeout. Downloader ưu tiên thử nguồn chính thức. Nếu không lấy được, dùng bản sao công khai của đúng hai CSV tại repository Nir-J/ML-Projects, thư mục UNSW-Network_Packet_Classification. Đã kiểm tra được header và khả năng tải theo Range ở hai file:

~~~text
https://raw.githubusercontent.com/Nir-J/ML-Projects/master/UNSW-Network_Packet_Classification/UNSW_NB15_training-set.csv
https://raw.githubusercontent.com/Nir-J/ML-Projects/master/UNSW-Network_Packet_Classification/UNSW_NB15_testing-set.csv
~~~

Khi dùng bản sao, khóa URL theo commit repository, ghi rõ mirror trong manifest và kiểm tra schema/số dòng/nhãn theo mô tả chính thức. SHA-256 tự tính dùng để khóa artifact đã tải; không tuyên bố nó là checksum được UNSW chứng nhận. Nếu cả hai nguồn lỗi hoặc nội dung sai định dạng thì báo lỗi cụ thể, không thay bằng bản đã binarize hoặc bộ UNSW mở rộng khác.

### 3.2. Dung lượng và khả năng chạy lại

Ổ D tại thời điểm kiểm tra còn khoảng 26 GiB. Vì vậy:

- Tải archive IoT vào cache raw bằng file .part, hỗ trợ HTTP Range và đổi tên sau khi tải hoàn chỉnh.
- Kiểm tra dung lượng trống tối thiểu bằng kích thước tải còn lại cộng 8 GiB cho cache/output; báo trước phần thiếu nếu không đủ.
- Đọc tar.gz theo luồng, chỉ xử lý file nhãn/README cần thiết, không giải nén toàn bộ archive ra ổ D.
- Mỗi capture được đọc theo batch khoảng 100.000 dòng, thống kê đầy đủ và giữ reservoir theo lớp với hash ổn định.
- Giữ tối đa 100.000 ứng viên mỗi capture/lớp, ghi cache Parquet theo capture rồi giải phóng RAM. Mức này đủ để chọn subset main tối đa 100.000 dòng một split.
- Sau khi chọn split, phân bổ quota lớp theo số dòng hợp lệ gốc của split, rồi chọn các hash nhỏ nhất từ reservoir. Cách này không làm các capture lớn và nhỏ có trọng số bằng nhau một cách ngầm định.
- Lưu counts đầy đủ, seed, ID mẫu được giữ, checksum và phiên bản parser. Cache hợp lệ được tái sử dụng; cache sai checksum/schema phải được tạo lại có chỉ dẫn rõ.
- Tải có thể tiếp tục; việc đọc gzip có thể phải đọc lại từ đầu nếu bị ngắt. Không hứa khả năng tiếp tục parser ở byte bất kỳ của gzip.

## 4. Hệ nhãn và metadata

### 4.1. Bảng ánh xạ cố định

| Nguồn | BENIGN = 0 | DOS_DDOS = 1 | OTHER_ATTACK = 2 |
|---|---|---|---|
| CIC | Benign/BENIGN | Các nhãn DDoS gốc đã được xác nhận: DNS, LDAP, MSSQL, NetBIOS, NTP, SNMP, SSDP, SYN, UDP, UDP-Lag, TFTP, WebDDoS, Portmap và alias tương ứng | Chỉ khi file gốc thực sự có nhãn tấn công khác đã xác minh |
| UNSW | Normal, khớp binary label = 0 | DoS, khớp binary label = 1 | Fuzzers, Analysis, Backdoor/Backdoors, Exploits, Generic, Reconnaissance, Shellcode, Worms |
| IoT | Benign trong nhãn nguồn | Detailed-label DDoS và các tổ hợp được xác nhận có thành phần DDoS | Các detailed-label độc hại còn lại đã biết: C&C, quét cổng, FileDownload, Attack, Okiru và các tổ hợp thực tế trong bản phát hành |

- Bảng alias được lưu rõ theo phiên bản; không dùng quy tắc substring tùy ý để biến mọi nhãn thành một trong ba lớp.
- Đọc trực tiếp nhãn raw CIC; không dùng phép đổi Portmap → PortScan của pipeline cũ. Nhãn raw PortScan, nếu xuất hiện, phải có quy tắc theo nguồn được kiểm chứng riêng trước khi xuất dữ liệu.
- IoT parser tách đúng label và detailed-label. Tổ hợp có nhãn DDoS được ưu tiên DOS_DDOS; tổ hợp benign/malicious mâu thuẫn bị đưa vào báo cáo lỗi.
- OTHER_ATTACK là nhóm các nhãn độc hại còn lại theo hệ nhãn nguồn, không phải kết luận rằng mọi flow đó đã được chứng minh không có hành vi DoS.
- Nhãn lạ, thiếu hoặc mâu thuẫn được đưa vào danh sách cần xử lý; pipeline không xuất bản main artifacts khi còn nhãn chưa có quy tắc. Không mặc định gán benign hoặc OTHER_ATTACK cho dữ liệu không rõ.
- CIC có thể không có OTHER_ATTACK. Đây là trường hợp hợp lệ: mô hình ở client CIC vẫn có đủ ba đầu ra.

### 4.2. Metadata không đưa vào mô hình

Giữ dataset_id, capture_id/source_file, row_id, original_label, timestamp nếu có và fingerprint phục vụ kiểm tra trùng. File dữ liệu model có y và binary = (y != 0); metadata chỉ phục vụ truy vết/đánh giá.

Danh sách cột model được khai báo tường minh. Không lấy toàn bộ cột số bằng thao tác tự động vì có thể đưa ID, thời gian tuyệt đối hoặc nhãn vào tensor.

## 5. Đặc trưng chung và tiền xử lý

### 5.1. Bốn trường cơ sở

| Trường chuẩn | CIC | UNSW | IoT-23 |
|---|---|---|---|
| duration_s | Flow Duration / 1e6 | dur | duration |
| fwd_packets | Total Fwd Packets | spkts | orig_pkts |
| bwd_packets | Total Backward Packets | dpkts | resp_pkts |
| protocol_group | Protocol | proto | proto |

Adapter xác minh ý nghĩa chiều truyền, cách đếm và đơn vị của đúng phiên bản file. Các khác biệt quy tắc tạo/đóng flow của extractor được ghi trong báo cáo. Nếu không đạt điều kiện tương thích của trường cơ sở, dừng xuất artifacts và nêu rõ trường nào chưa dùng được.

Schema v1 cố định theo bốn trường này. Byte, IAT, TCP window, flag và cổng không thuộc đầu vào v1 vì chưa xác lập phép đo tương thích trên cả ba bản dữ liệu. Không lấy số cột nhỏ nhất rồi cắt các bộ khác cho đủ số lượng.

### 5.2. Tám cột liên tục ứng viên DAS

1. duration_s.
2. fwd_packets.
3. bwd_packets.
4. total_packets = fwd_packets + bwd_packets.
5. flow_packets_s = total_packets / duration_s.
6. fwd_packets_s = fwd_packets / duration_s.
7. bwd_packets_s = bwd_packets / duration_s.
8. bwd_packet_fraction = bwd_packets / total_packets.

Các rate để missing khi duration không dương hoặc thiếu; không tạo vô cực. Loại dòng có packet count thiếu, âm, không hữu hạn hoặc tổng packet không dương và ghi số dòng bị loại theo nguồn/lớp. Duration âm/sentinel không hợp lệ được coi là missing; dấu '-' trong log được xử lý theo header và kiểu trường, không mặc định đổi thành 0.

Sáu cột cố định bổ sung:

- proto_tcp, proto_udp, proto_icmp, proto_other.
- duration_missing.
- duration_zero.

Protocol dùng cùng mapping: TCP/6, UDP/17, ICMP/1 và ICMPv6/58, còn lại OTHER. Chỉ một cột protocol bằng 1. Các flag và one-hot giữ nguyên 0/1, không nội suy hoặc chuẩn hóa như đại lượng liên tục.

### 5.3. Fit và transform

- Chỉ tám cột liên tục đi qua log1p trên các giá trị hữu hạn không âm.
- AFN theo protocol dùng thống kê train của cả ba nguồn: số giá trị quan sát, tổng và tổng bình phương theo từng cột/nhóm. Cần hỗ trợ số lượng quan sát khác nhau khi có missing, không dùng n của cả nhóm thay cho n_valid của từng cột.
- Tính mean/std chung từ thống kê cục bộ. Missing được thay bằng mean của cột/nhóm trên miền log trước khi z-score, nên thành 0 sau AFN.
- Nhóm chưa gặp dùng tham số global train; phương sai bằng 0 dùng scale = 1. Cột không có quan sát train hợp lệ bị loại khỏi ứng viên và ghi lý do.
- Các cờ duration cho mô hình biết giá trị bị thiếu hoặc bằng 0; không truyền nhãn thật vào lựa chọn nhóm AFN.
- Mọi tham số được lưu. Validation/test chỉ transform; không cập nhật thống kê.
- Chuyển đầu vào cuối thành float32 và kiểm tra hữu hạn trước khi huấn luyện.

Đây là mở rộng xử lý missing của AFN phục vụ ba nguồn, cần tách rõ khỏi hàm CIC cũ để tránh thay đổi kết quả trước đây.

## 6. DAS: một tập đặc trưng cho cả federation

- Tái sử dụng công thức CRA/IDF của paper và code hiện có trên tám cột liên tục sau AFN.
- Dùng nhãn one-hot theo đúng ba lớp. Cột hằng và lớp không có biến thiên được xử lý trước khi chia phương sai.
- Gộp thống kê train ba client để tạo điểm pooled. Báo cáo thêm điểm theo nguồn để nhìn được ảnh hưởng phân phối; không tự đổi sang một thuật toán relevance mới.
- CRA xếp hạng giảm dần; IDF loại cột có |Pearson| >= 0.9 với cột đã chọn. Relevance phải > 0.001, tối đa 8 cột; nếu hòa, dùng thứ tự tên cột để tái lập.
- V1 dùng ngưỡng cố định. Không thêm tìm kiếm siêu tham số DAS. So sánh với cấu hình giữ toàn bộ cột liên tục hợp lệ để đo ảnh hưởng thực tế.
- Nếu không chọn được cột liên tục nào, báo lỗi và xuất bảng điểm để phân tích; không tự chèn cột hoặc hạ ngưỡng ngầm.
- Sáu cột categorical/flag được giữ như một khối cố định. Danh sách và thứ tự đầu vào cuối là cột liên tục đã chọn theo thứ tự DAS, sau đó sáu cột cố định.

Nếu DAS chọn m cột liên tục, mỗi client có **F = m + 6 cột model** giống nhau; m từ 1 đến 8. F vì vậy từ 7 đến 14 trong schema v1, không mặc định 20, 25 hoặc 36. Số dòng của ba client vẫn có thể khác nhau.

feature_selection.csv ghi tên cột, relevance pooled/theo nguồn, thứ hạng, trạng thái chọn/bỏ và lý do dư thừa/hằng/không quan sát được.

## 7. Chia dữ liệu và lấy mẫu

### 7.1. Quy tắc theo nguồn

| Nguồn | Test | Train / validation |
|---|---|---|
| CIC | Toàn bộ nguồn *-training theo quy ước hiện tại, sau kiểm tra chất lượng và lấy subset profile | Nguồn *-testing: khoảng 80/20 theo nhóm fingerprint, phân tầng nhãn |
| UNSW | CSV testing-set chính thức | CSV training-set: khoảng 80/20 theo nhóm fingerprint, phân tầng nhãn |
| IoT | Một fold nhóm capture của StratifiedGroupKFold 5-fold | Một fold validation, ba fold còn lại train; gần 60/20/20 về nhóm, số dòng thực tế phụ thuộc capture |

Với CIC/UNSW, fingerprint dùng các phép đo flow raw sẵn có, loại ID/label và metadata định danh; không chỉ dùng bốn cột chung. Các vector trùng là nhóm để hạn chế trùng giữa train/validation, không được diễn giải thành cùng một phiên mạng thật.

Với IoT, StratifiedGroupKFold chạy trên reservoir ứng viên có capture_id và y, seed 42. Thử các cặp fold test/validation theo thứ tự chỉ số; chọn cặp đầu tiên có đủ ba lớp ở train, validation và test của IoT. Quyết định chỉ dùng nhãn/coverage, không dùng dự đoán hoặc điểm mô hình. Sau đó ghi counts thực tế của toàn bộ các capture thuộc mỗi split. Nếu không tồn tại cặp thỏa coverage thì báo lỗi kèm bảng capture/lớp; không lén chuyển sang random flow split.

Train/validation CIC và UNSW dùng cùng cách chọn fold 5-fold theo nhóm, chọn fold validation đầu tiên có đủ lớp của nguồn trong cả train và validation. Split manifest lưu cặp seed/nhóm/dòng để mọi kiến trúc và seed huấn luyện dùng lại.

### 7.2. Kiểm tra độc lập và profile

- Chia tập trước fit/sinh mẫu. Lấy subset theo quota lớp từ counts gốc của từng split, lựa chọn bằng hash seed 42, cùng ID được tái sử dụng cho các thí nghiệm so sánh.
- Nhóm train/validation không giao nhau; capture IoT không xuất hiện ở nhiều split.
- Các ID trùng của cùng flow phải được phát hiện. Overlap vector với test chính thức được báo riêng; vector giống nhau không tự chứng minh cùng sự kiện hoặc rò rỉ nhãn.
- Không sửa âm thầm test chính thức hoặc chuyển mẫu test sang train để cải thiện coverage.
- Mỗi nguồn phải có validation/test không rỗng. Global train có đủ ba lớp; mỗi nguồn được phép có tập lớp nhỏ hơn.
- Tỷ lệ, số dòng bị loại, số dòng sau sampling và support theo lớp đều có trong quality_report.
- Trong v1 không tạo bản giải nén hoặc full tensor chứa toàn bộ hàng trăm triệu flow IoT. Các lượt main sử dụng subset được công bố; chạy toàn bộ benchmark là mở rộng về tài nguyên sau này.

## 8. Cân bằng lớp, FL và chọn checkpoint

Class weight tại mỗi client lấy nghịch đảo tần suất lớp train có mặt, chuẩn hóa trung bình weight lớp có mặt bằng 1 và clip [0.1, 10]. Lớp vắng được ghi support = 0 và weight = 0, không tạo mẫu giả. Cùng hàm tính weight được dùng cho FL và baseline tương ứng.

Giữ Flower 1.40 hiện tại. FedAvg theo num-examples là số mẫu train thật trong subset. Không dùng kích thước toàn bộ dataset raw làm trọng số vì các dòng đó chưa tham gia học.

### 8.1. Validation chạy tại client

1. Server gửi cùng global arrays cho ba client.
2. Ba client train cục bộ, gửi arrays, PID, số mẫu và chi phí; server chỉ chấp nhận đủ PID 0/1/2 không trùng.
3. Server gộp trọng số.
4. Gửi global arrays sau gộp về ba client để đánh giá trên validation riêng.
5. Server lấy trung bình đều F1-macro-present của ba validation để chọn checkpoint.

F1-macro-present lấy trung bình F1 của các lớp có support thật trong validation nguồn đó; confusion matrix vẫn có ba hàng/cột và ghi support từng lớp. Điều này tránh coi lớp OTHER_ATTACK vắng ở CIC là một lớp có điểm hoàn hảo hoặc cố định phạt 0 vào trung bình. Ghi rõ định nghĩa metric trong báo cáo.

Một lớp FedAvg mở rộng nhỏ ở server giữ validation theo round, kiểm tra đủ ba phản hồi train/evaluate và lưu log PID → nguồn. Callback evaluate_fn(round, arrays) lấy metric đã gộp của đúng round để lưu best arrays; không đọc test. Đã kiểm tra mã Flower cục bộ: aggregate_evaluate chạy trước evaluate_fn trong mỗi vòng. Round 0 chỉ ghi trạng thái khởi tạo; không tham gia chọn best.

Thiếu hoặc trùng phản hồi, round không khớp, metric chọn model không hữu hạn thì dừng lượt chạy có lỗi rõ; không ghi là thí nghiệm hoàn tất.

### 8.2. Checkpoint

Lưu best và last riêng. Best được chọn trên validation từ round 1; hòa thì giữ vòng sớm hơn. Checkpoint gồm arch, dropout, state_dict, thứ tự classes/features, round, score validation, seed, run config, schema/preprocessor/split hash.

Loader mới phải nhận pipeline multidataset_v1, tránh đi nhầm nhánh scaler của pipeline MLP cũ. Khi đổi data directory trong notebook/process, cache metadata được reset hoặc khóa theo đường dẫn để không dùng nhầm schema.

## 9. Đánh giá cuối và thí nghiệm

Lệnh đánh giá nạp best checkpoint một lần, xác minh schema/preprocessor tương ứng rồi chạy ba test với cùng trọng số và ngưỡng. Mỗi hàng kết quả ghi dataset_id, checkpoint hash, selected_round, seed và số mẫu.

Các kết quả bắt buộc:

- Confusion matrix 3 × 3, accuracy, F1-macro-present và precision/recall/F1/support từng lớp.
- Phát hiện mọi tấn công: y != BENIGN, xác suất 1 - P(BENIGN).
- Phát hiện nhóm DoS/DDoS: y == DOS_DDOS, xác suất P(DOS_DDOS).
- Hai nhóm metric nhị phân ghi tên khác nhau; cùng ngưỡng 0.5 trong v1, không chọn ngưỡng theo test.
- FAR trên benign; ROC-AUC và average precision khi có đủ hai nhãn. Metric không xác định ghi null/N/A kèm support, không thay bằng 0 hoặc 1 để làm đẹp bảng.
- Trung bình đều theo nguồn và nguồn kém nhất. Nếu có metric pooled, tính từ dự đoán gộp, không gọi trung bình F1 là F1 pooled.
- Có thể thống kê khả năng phát hiện theo original_label; phải gọi đúng đây là phân tích theo loại gốc, không phải dự đoán loại con.

Thí nghiệm chính được chuẩn bị lệnh chạy:

| Cấu hình | Số seed | Mục đích |
|---|---:|---|
| FL 3 client + ResVGG-SwinNet + DAS | 0, 1, 2 | Kết quả chính |
| FL 3 client + ResVGG-SwinNet + toàn bộ ứng viên hợp lệ | 0, 1, 2 | Đối chứng tác dụng DAS |
| Local-only, mỗi nguồn một mô hình | 0 | Đối chứng học riêng |
| Centralized, gộp train ba nguồn | 0 | Đối chứng nghiên cứu tập trung |

Các cấu hình dùng cùng split/subset, thuật toán tính loss/weight phù hợp dữ liệu train và ngân sách được ghi rõ. Centralized/local lấy mốc 150 epoch, chọn checkpoint theo validation thích hợp, test cuối cùng. Báo cáo không gọi centralized là cận trên được bảo đảm. Hai baseline chỉ một seed phải được công bố, không so sánh độ biến động như có ba seed.

Mục tiêu nghiệm thu là đường chạy đúng và kết quả đo được, không đặt điều kiện phải đạt 99% hoặc phải vượt mọi baseline.

## 10. Cấu trúc code và giao diện

### 10.1. Module và lệnh

| Thành phần | Trách nhiệm |
|---|---|
| fl_ddos/dataset_adapters.py | Parser riêng, nhãn và canonical schema; trả batch cùng metadata |
| fl_ddos/multidataset_prep.py | Reservoir, split, thống kê AFN, DAS, transform và artifacts |
| prepare/download_datasets.py | Download/resume/checksum/cache và kiểm tra định dạng |
| prepare/multidataset_pipeline.py | CLI mỏng gọi module xử lý |
| configs/multidataset.json | Đường dẫn, profile, seeds, schema version, mapping, split, AFN và DAS |
| fl_ddos/task.py, paths.py, features.py | Nạp pipeline/version mới, train/validation riêng, reset cache |
| fl_ddos/client_app.py, server_app.py | Đúng ba nguồn, validation phân tán, FedAvg và best checkpoint |
| analysis/evaluate_multidataset.py | Một checkpoint → ba test và file báo cáo |
| notebooks/03_tien_xu_ly_ba_dataset.ipynb | Giải thích/khảo sát/biểu đồ bằng cùng hàm Python |
| scripts, Modal, baselines, README | Cách chạy tương ứng và hướng dẫn |

Các giao diện chính của module mới:

~~~python
iter_canonical_batches(dataset_id, source, chunksize) -> Iterator[DataFrame]
prepare_multidataset(config, profile) -> dict
transform_canonical(frame, fitted_preprocessor) -> DataFrame
evaluate_checkpoint(checkpoint_path, data_dir, results_dir) -> DataFrame
~~~

CLI dự kiến, chưa phải lệnh đã có:

~~~powershell
.\.venv\Scripts\python.exe prepare/download_datasets.py --config configs/multidataset.json
.\.venv\Scripts\python.exe prepare/multidataset_pipeline.py --config configs/multidataset.json --profile smoke
.\scripts\fl_run.ps1 "scenario='multidataset' num-server-rounds=2 local-epochs=1 seed=0" -Clients 3 -Actors 1 -DataDir data_paper_multi/smoke -ResultsDir results_multidataset/smoke
.\.venv\Scripts\python.exe analysis/evaluate_multidataset.py --data-dir data_paper_multi/smoke --results-dir results_multidataset/smoke --checkpoint <best-checkpoint>
~~~

Main đổi profile/data directory và dùng 30 vòng × 5 epoch. Trên máy hạn chế RAM, mặc định chạy actor lần lượt; thêm GPU theo tài nguyên thực tế. Modal nhận cả ba nguồn/cache thay vì hardcode CIC, vẫn đúng ba supernodes. Việc hỗ trợ chạy Modal không yêu cầu mở rộng số kiến trúc trong v1.

### 10.2. Artifacts

~~~text
data_paper_multi/
  smoke/ hoặc main/
    features.json
    prep_params.json
    dataset_manifest.json
    split_manifest.parquet
    quality_report.json
    feature_selection.csv
    multidataset/
      client_1.parquet
      client_2.parquet
      client_3.parquet
      val_client_1.parquet
      val_client_2.parquet
      val_client_3.parquet
      class_weights.json
    test/
      cicddos2019.parquet
      unsw_nb15.parquet
      iot23.parquet

results_multidataset/
  smoke/ hoặc main/
    fl/
      ..._best.pt
      ..._last.pt
      ..._rounds.csv
      ..._clients.csv
    evaluation_by_dataset.csv
    per_class.csv
    figures/
    summary.md
~~~

features.json có pipeline/schema version, classes đúng thứ tự, ordered features và các hash liên quan. prep_params.json lưu tất cả tham số AFN/missing/mapping/DAS cần để transform lại raw canonical data. dataset_manifest khóa PID 0/1/2 với đúng một nguồn.

## 11. Nội dung notebook

Notebook có bảy phần, dùng cùng module và artifact với CLI:

1. Giới thiệu ba nguồn, ba client và ba lớp.
2. Hiện trạng file, phiên bản, số cột và nhãn gốc.
3. Bảng ánh xạ nhãn; phân phối lớp trước/sau ánh xạ.
4. Bảng ánh xạ đặc trưng, đơn vị và các cột không dùng.
5. Kiểm tra chất lượng, missing, split, overlap và subset được giữ.
6. Điểm CRA, cột bị IDF loại, danh sách chung cuối cùng và phân phối sau AFN.
7. Đọc kết quả FL/test theo nguồn, giải thích các metric và giới hạn.

Run All ở cấu hình smoke/audit không tự khởi chạy train dài. Phần tải và train lớn là lệnh/cell gọi riêng có giải thích. Notebook chạy được từ kernel mới, không dựa vào biến của cell đã chạy ngẫu nhiên.

## 12. Thứ tự code, kiểm thử và nghiệm thu

| Bước | Công việc | Điều kiện chuyển bước |
|---:|---|---|
| 1 | Cấu hình, downloader và kiểm tra raw | Có đúng hai nguồn mới, manifest và parser đọc được batch thật |
| 2 | Adapter, mapping nhãn, quality report | Mọi nhãn có quy tắc; metadata và feature tách rõ; counts theo nguồn |
| 3 | Split, reservoir/subset và AFN | Split tái lập, nhóm không giao nhau như thiết kế, fit chỉ dùng train |
| 4 | DAS, artifacts và notebook | Cả ba file train có cùng F/thứ tự cột; preprocessor lưu/nạp tái lập |
| 5 | Loader, FedAvg và checkpoint | PID gắn đúng nguồn; đủ ba phản hồi; best chọn từ validation |
| 6 | Smoke trên ba nguồn thật | 2 vòng × 1 epoch hoàn tất; một best checkpoint đánh giá được ba test |
| 7 | Baselines, báo cáo, tài liệu chạy | Có lệnh chạy main/đối chứng, bảng metric đúng tên, notebook giải thích được |
| 8 | Thí nghiệm chính khi thực thi kế hoạch | Cùng tập seed/split cho hai cấu hình FL; báo cáo mean/std theo nguồn |

Các kiểm tra bắt buộc cho implementation:

- Đọc đúng CSV BOM và IoT header/separator/nhãn; phát hiện file HTML/login thay cho dataset.
- Mapping đơn vị/protocol/nhãn đúng trên fixture; nhãn lạ hoặc mâu thuẫn được báo.
- Chuỗi Flow Duration = 1.000.000 của CIC thành duration_s = 1, các rate tính theo giây.
- Duration 0/missing không sinh Inf; category vẫn one-hot; ID/nhãn không lọt vào model.
- Đổi validation/test với train và cấu hình cố định không đổi fitted AFN/DAS.
- Lớp vắng tại CIC không gây chia 0, không sinh mẫu giả và không đổi số đầu ra.
- DAS cho kết quả/tie-break tái lập, không trộn danh sách khác nhau giữa client.
- Transform sau khi load preprocessor khớp trước khi lưu với atol/rtol = 1e-6.
- Train/validation giữ ràng buộc nhóm; IoT capture không xuất hiện ở hai split; seed lặp cho cùng ID subset.
- Thiếu/trùng PID hoặc thiếu metric validation phải làm lượt FL thất bại rõ ràng.
- Best checkpoint thực sự theo validation, không có lượt đọc test trong callback chọn model.
- Ba hàng kết quả test cùng checkpoint hash, đúng support và metric N/A khi không xác định.
- Pipeline CIC cũ vẫn nạp/chạy được sau các thay đổi loader/metadata.
- Notebook chạy tuần tự từ kernel mới với smoke artifacts; toàn bộ test không tải archive nhiều GB.

Kiểm thử sử dụng fixture nhỏ để bắt lỗi logic và một smoke run dữ liệu thật để xác nhận tích hợp. Fixture không được báo thành kết quả học trên dataset thực.

## 13. Bàn giao

1. Pipeline Python và cấu hình cho đúng **3 client × 3 lớp**.
2. Dữ liệu/raw manifest, split/subset manifest, fitted preprocessor và bảng DAS.
3. Notebook khảo sát, giải thích toàn bộ xử lý và đọc kết quả.
4. Best/last checkpoint và báo cáo của cùng best model trên ba nguồn.
5. Hướng dẫn tái lập từ tải dữ liệu đến chạy thí nghiệm, kèm các điều chỉnh so với paper.

Phân tích nền: [Phân tích kết hợp ba dataset](phan_tich_ket_hop_ba_dataset.md).
