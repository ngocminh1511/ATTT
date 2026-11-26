# Kịch bản thuyết trình — Học liên kết phát hiện tấn công mạng

Sinh từ `src/slides.json`; chỉnh nguồn rồi chạy `python presentation/build.py`.

Pipeline: dữ liệu → làm sạch → chia tập → tạo đặc trưng → chuẩn hóa → DAS → huấn luyện → kết quả.

Các giá trị thực nghiệm: 4 client (CIC → 1, 2; UNSW → 3, 4), profile main, seed 0; F1 tổng hợp là trung bình đều F1-macro-present hai nguồn, trừ khi ghi khác.

## 00 · Học liên kết phát hiện tấn công mạng

**Giai đoạn:** Pipeline · **Trạng thái:** Đang bật

**Thông điệp:** Đồ án An toàn thông tin · GVHD PGS.TS Nguyễn Tấn Khôi · SVTH Phan Văn Hiếu, Đoàn Ngọc Minh.

**Mục tiêu:** Giới thiệu đề tài, giảng viên hướng dẫn và nhóm thực hiện.

**Nội dung trên slide:**

- Đề tài: Học liên kết phát hiện tấn công mạng trên CIC-DDoS2019 và UNSW-NB15
- GVHD: PGS.TS Nguyễn Tấn Khôi
- SVTH: Phan Văn Hiếu (102230120), Đoàn Ngọc Minh (102230157)

**Lời trình bày:**

Em chào thầy. Nhóm em gồm Phan Văn Hiếu và Đoàn Ngọc Minh, thực hiện đồ án An toàn thông tin dưới sự hướng dẫn của thầy Nguyễn Tấn Khôi. Đề tài của nhóm là học liên kết để phát hiện tấn công mạng trên hai nguồn dữ liệu CIC-DDoS2019 và UNSW-NB15. Hình bên phải minh họa ý tưởng chính: server gửi mô hình chung xuống bốn client, mỗi client học trên dữ liệu riêng, chỉ gửi lại trọng số, và server tổng hợp thành mô hình mới; dữ liệu không rời khỏi client.

**Chỉ vào hình:** Giới thiệu thông tin bên trái, rồi chỉ vào bốn bước đang chạy trong hình bên phải.

**Chuyển ý:** Trước khi đi vào chi tiết, em giới thiệu quy trình thực hiện gồm tám giai đoạn.

**Nguồn:** Thông tin đề tài do nhóm cung cấp; fl_ddos/multidataset_server.py

## 01 · Quy trình thực hiện

**Giai đoạn:** Pipeline · **Trạng thái:** Đang bật

**Thông điệp:** Tám giai đoạn từ dữ liệu đến đánh giá kết quả.

**Mục tiêu:** Giúp thầy nắm toàn bộ luồng bài làm trước khi đi vào chi tiết.

**Nội dung trên slide:**

- CIC-DDoS2019 + UNSW-NB15
- 4 client · 3 lớp
- ResVGG-SwinNet · FedAvg / FedProx

**Lời trình bày:**

Em xin trình bày bài làm theo luồng dữ liệu, bắt đầu từ hai bộ dữ liệu có cấu trúc khác nhau và kết thúc bằng các kết quả đánh giá. Trước hết, dữ liệu được làm sạch và đồng nhất về schema, sau đó chia thành các tập riêng cho bốn client, mỗi nguồn hai client. Tiếp theo là tạo đặc trưng, chuẩn hóa và lựa chọn đầu vào. Các đầu vào này được dùng để huấn luyện mô hình và thực hiện các thí nghiệm đối chứng. Phần đánh giá sẽ tập hợp so sánh local, centralized, FL, ALL với DAS và FedAvg với FedProx. Sơ đồ này cũng là mục lục tương tác, nên em có thể quay lại bất kỳ công đoạn nào khi cần giải thích thêm.

**Chỉ vào hình:** Chỉ theo các mũi tên từ dữ liệu đến kết quả; các đối chứng đều nằm trong giai đoạn 8.

**Chuyển ý:** Em bắt đầu với dữ liệu và nhiệm vụ mà mô hình phải giải quyết.

**Nguồn:** fl_ddos/multidataset_prep.py; configs/multidataset.json

## 02 · Hai bộ dữ liệu

**Giai đoạn:** Tổng quan dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** CIC-DDoS2019 chỉ có DDoS; UNSW-NB15 gồm nhiều loại xâm nhập. Nhãn gốc được gom về ba lớp chung.

**Mục tiêu:** Giới thiệu hai bộ dữ liệu, các nhãn gốc và cách gom về ba lớp trong một slide.

**Nội dung trên slide:**

- CIC: 431.371 mẫu, 78 cột; 12/01 làm train/val, 11/03 làm test
- UNSW: 257.673 mẫu, 45 cột; Normal + 9 nhóm tấn công
- Ba lớp chung: BENIGN · DOS_DDOS · OTHER_ATTACK

**Lời trình bày:**

Bài dùng hai bộ dữ liệu công khai. CIC-DDoS2019 có khoảng bốn trăm ba mươi nghìn mẫu, nhãn là từng kiểu DDoS như NTP, TFTP hay SYN; ngày 12/01 dùng làm train và validation, ngày 11/03 làm test. UNSW-NB15 có khoảng hai trăm năm mươi nghìn mẫu, gồm Normal và chín nhóm tấn công. Màu của mỗi thanh cho biết nhãn đó được gom vào lớp nào: BENIGN, DOS_DDOS hoặc OTHER_ATTACK; CIC không có OTHER_ATTACK.

**Chỉ vào hình:** Chỉ chú thích màu, rồi so hai biểu đồ: CIC toàn xanh dương (DDoS), UNSW phần lớn tím (tấn công khác).

**Chuyển ý:** Hai bộ khác nhau cả tên cột lẫn đơn vị, nên bước tiếp theo là đưa về một schema chung.

**Nếu thầy hỏi:** Bản CIC đang dùng là Parquet (Kaggle dhoogla/cicddos2019), 77 đặc trưng + Label, không có SSDP dù mô tả gốc có; ngày 11/03 dùng nhãn Portmap. UNSW dùng hai file training/testing chính thức; benchmark đầy đủ có 2.540.044 mẫu, 49 trường. Mỗi nguồn lấy subset 100.000 train, 20.000 validation, 50.000 test.

**Nguồn:** presentation/data/datasets.json; configs/multidataset.json: label_map; https://www.unb.ca/cic/datasets/ddos-2019.html; https://research.unsw.edu.au/projects/unsw-nb15-dataset

## 03 · Chuẩn hóa schema & đơn vị

**Giai đoạn:** Làm sạch & đồng nhất · **Trạng thái:** Đang bật

**Thông điệp:** Đổi tên cột và đơn vị của hai nguồn về 8 trường chung.

**Mục tiêu:** Cho thấy rõ dữ liệu trước và sau khi đưa về schema chung.

**Nội dung trên slide:**

- CIC 78 cột, UNSW 45 cột → 8 trường chung
- Thời lượng và IAT đổi về giây
- Giao thức gom thành TCP / UDP / ICMP / OTHER

**Lời trình bày:**

Hai bộ đặt tên cột và dùng đơn vị khác nhau, nên em chuẩn hóa về tám trường chung. Hai cột bên phải là tên gốc của CIC và UNSW, cột tô xanh là trường sau chuẩn hóa. Thời lượng và khoảng cách gói được đổi hết về giây, giao thức gom thành bốn nhóm TCP, UDP, ICMP và OTHER.

**Chỉ vào hình:** Đọc từng hàng từ cột gốc sang cột tô xanh; nhấn vào µs ÷ 10⁶ và ms ÷ 10³.

**Chuyển ý:** Sau khi có schema chung, em gom nhãn và kiểm tra chất lượng dữ liệu.

**Nếu thầy hỏi:** CIC đo bằng micro giây nên chia 10⁶; UNSW dur đã là giây, còn sinpkt/dinpkt là mili giây nên chia 10³. Đơn vị µs của CIC được kiểm tra bằng tỷ lệ số gói / thời lượng so với Flow Packets/s (≈ 1). Đổi đơn vị chưa phải chuẩn hóa thống kê; z-score làm ở giai đoạn chuẩn hóa.

**Nguồn:** fl_ddos/dataset_adapters.py: CIC_FIELDS, cic_frame, unsw_frame, protocol_group; data_paper_multi_4c/main/quality_report.json: compatibility_checks

## 04 · Gom nhãn về 3 lớp

**Giai đoạn:** Làm sạch & đồng nhất · **Trạng thái:** Đang bật

**Thông điệp:** Nhãn gốc của hai nguồn được ánh xạ tường minh về BENIGN, DOS_DDOS và OTHER_ATTACK.

**Mục tiêu:** Cho thấy rõ nhãn nào đi về lớp nào và số mẫu mỗi lớp sau khi gom.

**Nội dung trên slide:**

- Benign / Normal → BENIGN
- DDoS của CIC và DoS của UNSW → DOS_DDOS
- 8 nhóm tấn công còn lại của UNSW → OTHER_ATTACK

**Lời trình bày:**

Hai bộ dữ liệu đặt tên nhãn khác nhau, nên em dùng một bảng ánh xạ tường minh. Bên trái là nhãn gốc của CIC, bên phải là của UNSW, ở giữa là lớp chung. Benign và Normal thành BENIGN; các kiểu DDoS của CIC cùng DoS của UNSW thành DOS_DDOS; tám nhóm còn lại của UNSW thành OTHER_ATTACK, và CIC không có lớp này.

**Chỉ vào hình:** Đi từng hàng: chip nhãn gốc → ô lớp chung có số mẫu của mỗi nguồn.

**Chuyển ý:** Sau khi nhãn đã thống nhất, em kiểm tra các giá trị đo bị lỗi.

**Nếu thầy hỏi:** Ánh xạ nằm trong configs/multidataset.json (label_map), so khớp không phân biệt hoa thường và khoảng trắng. Một nhãn không được thuộc hai lớp; nhãn chưa có trong bảng làm dừng pipeline.

**Nguồn:** configs/multidataset.json: label_map; fl_ddos/dataset_adapters.py: build_label_lookup; presentation/data/datasets.json: label_counts

## 05 · Kiểm tra chất lượng

**Giai đoạn:** Làm sạch & đồng nhất · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi loại giá trị lỗi có một cách xử lý cố định: loại dòng, gán missing, gom nhóm hoặc dừng.

**Mục tiêu:** Cho người nghe thấy cụ thể giá trị nào bị coi là lỗi và được xử lý ra sao.

**Nội dung trên slide:**

- Mỗi dòng: 7 số đo + giao thức + nhãn được kiểm tra
- Số gói lỗi / tổng gói = 0 → loại dòng; phép đo hỏng → missing
- Giao thức lạ → OTHER; nhãn lạ → dừng pipeline

**Lời trình bày:**

Sau khi chuẩn hóa, mỗi dòng có bảy số đo, giao thức và nhãn; em kiểm tra từng giá trị và đưa về một trong bốn kết quả: giữ nguyên, gán missing, loại dòng hoặc dừng pipeline. Nếu số gói âm, rỗng hoặc tổng gói bằng không thì flow không hợp lệ và bị loại. Nếu chỉ một phép đo như duration, byte hay IAT bị hỏng thì giữ dòng và gán missing; IAT cũng là missing khi một chiều có ít hơn hai gói. Giao thức hiếm gom vào OTHER, còn nhãn lạ thì dừng pipeline.

**Chỉ vào hình:** Đi theo dải tổng quan ở trên (dòng → kiểm tra → 4 kết quả), rồi đọc bảng theo hàng: trường → giá trị lỗi → cách xử lý.

**Chuyển ý:** Dữ liệu đã sạch và chung schema; tiếp theo em chia dữ liệu cho các client.

**Nếu thầy hỏi:** Trên dữ liệu hiện tại không có dòng nào bị loại, không thiếu duration và không có nhãn lạ (quality_report: drops và issues rỗng), vì bản Parquet CIC và hai CSV UNSW đã được làm sạch từ nguồn. Các quy tắc vẫn chạy trên mọi dòng để bảo vệ pipeline khi đổi dữ liệu. Duration lỗi không đổi thành 0 vì 0 có nghĩa riêng (cờ duration_zero); missing được bật cờ duration_missing và đưa về 0 sau z-score.

**Nguồn:** fl_ddos/dataset_adapters.py: finalize, protocol_group; fl_ddos/multidataset_prep.py: PrepError nhãn lạ; data_paper_multi_4c/main/quality_report.json

## 06 · Tách test & validation

**Giai đoạn:** Phân chia dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Test giữ riêng theo nguồn; phần còn lại chia train/validation theo nhóm fingerprint.

**Mục tiêu:** Hiểu quy tắc tách tập và giới hạn của kiểm tra độc lập dữ liệu.

**Nội dung trên slide:**

- Test CIC theo nhóm file/ngày khác; UNSW dùng testing-set có sẵn
- Train/val: StratifiedGroupKFold, 5 fold, seed 42
- Cùng fingerprint không nằm ở cả train và validation

**Lời trình bày:**

Bước đầu tiên là giữ riêng tập test: CIC dùng ngày thu thập khác, UNSW dùng testing-set có sẵn. Phần còn lại chia train và validation bằng năm fold theo nhóm fingerprint, nên các dòng trùng giá trị đo luôn nằm cùng một phía. Mọi bước học tham số như chuẩn hóa hay chọn đặc trưng chỉ làm sau bước này.

**Chỉ vào hình:** Chỉ test tách trước, năm fold, và hai mẫu cùng màu luôn ở cùng phía.

**Chuyển ý:** Từ các tập đã tách, em lấy một subset có kiểm soát cho mỗi nguồn.

**Nếu thầy hỏi:** Dùng StratifiedGroupKFold 5 fold, seed 42; fingerprint tạo từ vector đo gốc, không dùng nhãn hay ID. Báo cáo xác nhận không có nhóm giao nhau giữa train và validation. Vẫn có vector trùng với test được báo cáo riêng, nên không khẳng định train/test tuyệt đối khác nhau.

**Nguồn:** fl_ddos/multidataset_prep.py: split_train_val, build_splits, independence_checks

## 07 · Lấy subset & chia 4 client

**Giai đoạn:** Phân chia dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi nguồn lấy 100.000 train / 20.000 val / 50.000 test, rồi chia train và val cho hai client theo từng nhãn gốc.

**Mục tiêu:** Gộp bước lấy subset với cơ chế chia client; nói rõ chia theo gì, để làm gì, và non-IID nằm ở đâu.

**Nội dung trên slide:**

- Subset: train đặt sàn lớp rồi chia theo tỷ lệ gốc; val/test giữ tỷ lệ tự nhiên; không nhân bản mẫu
- Chia client: trong từng nhãn gốc xáo bằng seed rồi chia lần lượt 1, 2, 1, 2…; không chia theo giao thức
- Mục đích: hai client cùng nguồn có cùng phân bố nhãn (lệch ≤ 1 mẫu/nhãn) và nhận các dòng rời nhau
- Test không chia theo client, giữ theo nguồn

**Lời trình bày:**

Từ các tập đã tách, mỗi nguồn em lấy một subset cố định: một trăm nghìn train, hai mươi nghìn validation, năm mươi nghìn test, lấy mẫu thật và không nhân bản. Train đặt sàn cho mỗi lớp rồi chia phần còn lại theo tỷ lệ gốc; validation và test giữ tỷ lệ tự nhiên. Nhìn thanh màu thấy ngay hai nguồn lệch nhãn rất mạnh: CIC không có lớp OTHER_ATTACK, còn UNSW chỉ có khoảng mười phần trăm DoS, và em giữ toàn bộ 9.811 mẫu DoS thật. Sau đó train và validation của mỗi nguồn được chia cho hai client. Em không chia theo giao thức mà chia theo nhãn gốc: trong từng nhãn như DrDoS_NTP hay Exploits, các dòng được xáo bằng seed rồi chia lần lượt cho client 1, client 2, client 1, client 2. Mục đích là hai client cùng nguồn có cùng phân bố nhãn, mỗi nhãn lệch tối đa một mẫu, kể cả nhãn rất hiếm như WebDDoS, và mỗi dòng chỉ thuộc đúng một client. Như vậy khác biệt dữ liệu thật trong bài nằm giữa CIC và UNSW, không nằm giữa hai client cùng nguồn. Test không chia theo client mà giữ theo nguồn.

**Chỉ vào hình:** Chỉ dải cơ chế phía trên (subset → chia lần lượt 1, 2 → 2 client), rồi thanh màu CIC/UNSW (thiếu OTHER_ATTACK, ít DoS), cuối cùng dòng 'lệch tối đa 1 mẫu/nhãn' và ô Mục đích.

**Chuyển ý:** Dữ liệu đã nằm ở từng client; tiếp theo em xây dựng vector đặc trưng cho mỗi flow.

**Nếu thầy hỏi:** Subset không phải toàn bộ benchmark; mất cân bằng còn lại bù bằng class weight trong loss, không sinh thêm mẫu. Chia client là stratified round-robin theo original_label, seed 42, theo từng dòng: mỗi dòng thuộc đúng một client, nhưng hai flow có cùng vector đo (cùng fingerprint) vẫn có thể nằm ở hai client; điều này không gây rò rỉ vì cả hai đều là train, ràng buộc fingerprint đã áp ở ranh giới train/validation. Không tạo non-IID trong cùng nguồn (theo giao thức hay Dirichlet) vì mục tiêu là đo tác động của khác biệt giữa hai nguồn thật. Test không chia theo client; cùng một checkpoint toàn cục được chấm trên test của từng nguồn.

**Nguồn:** data_paper_multi_4c/main/sampling_report.md; fl_ddos/multidataset_prep.py: choose_subsets, split_shards, client_frames; configs/multidataset.json: clients, client_split; data_paper_multi_4c/main/dataset_manifest.json

## 08 · 8 trường cơ sở → 23 cột đầu vào

**Giai đoạn:** Xây dựng đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** Giữ 7 trường số, tạo thêm 10 đặc trưng; giao thức và cờ duration thành 6 cột cố định.

**Mục tiêu:** Cho thấy nguồn gốc từng nhóm đặc trưng và tách cột cố định khỏi cột được DAS lọc.

**Nội dung trên slide:**

- 7 trường số giữ nguyên + 10 đặc trưng tạo thêm = 17 cột liên tục
- Tạo thêm: tổng, tốc độ, tỷ lệ chiều về, kích thước gói trung bình
- 6 cột cố định: 4 one-hot giao thức + duration_missing + duration_zero

**Lời trình bày:**

Từ tám trường cơ sở, bảy trường số được giữ nguyên. Em tạo thêm mười đặc trưng chia thành bốn nhóm: tổng hai chiều, tốc độ theo giây, tỷ lệ chiều về và kích thước gói trung bình; cộng lại thành mười bảy cột liên tục. Trường giao thức được one-hot thành bốn cột, thêm hai cờ cho duration thiếu hoặc bằng không, thành sáu cột cố định. Tổng cộng hai mươi ba đầu vào.

**Chỉ vào hình:** Đi từ trái sang phải: 7 giữ nguyên → 10 tạo thêm theo 4 nhóm → 6 cố định, rồi đọc dải tổng ở dưới.

**Chuyển ý:** Các đặc trưng này có thang giá trị rất khác nhau, nên bước tiếp theo là chuẩn hóa.

**Nếu thầy hỏi:** Các phép tính làm theo từng dòng, không học tham số nên không gây rò rỉ giữa train và test. Khi mẫu số bằng 0 hoặc duration thiếu, đặc trưng tương ứng là missing chứ không gán 0. Sáu cột cố định không đi qua DAS.

**Nguồn:** fl_ddos/multidataset_prep.py: CONTINUOUS, FIXED, derive

## 09 · Bước 1 · Biến đổi log1p

**Giai đoạn:** Chuẩn hóa dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi giá trị x của 17 cột liên tục được thay bằng ln(1 + x) để kéo các giá trị rất lớn về gần phần còn lại.

**Mục tiêu:** Nói rõ công thức bước 1, áp cho những cột nào, và minh họa bằng một cột thật.

**Nội dung trên slide:**

- Công thức: x′ = ln(1 + x); áp cho cả 17 cột liên tục, 6 cột 0/1 giữ nguyên
- x âm hoặc không hữu hạn → missing
- Ví dụ trên duration_s: 0–120 giây thành 0–4,8

**Lời trình bày:**

Chuẩn hóa gồm hai bước. Bước một là biến đổi log1p: mỗi giá trị x của cả mười bảy cột liên tục được thay bằng logarit tự nhiên của một cộng x. Dùng một cộng x để giá trị không vẫn ra không. Sáu cột cố định là 0 hoặc 1 nên giữ nguyên; giá trị âm hoặc vô hạn được coi là missing. Lý do là dữ liệu mạng có đuôi rất dài: phần lớn flow nhỏ, một số flow cực lớn. Hình lấy cột duration làm ví dụ: trước log, gần như mọi thứ dồn vào cột đầu và trục kéo tới một trăm hai mươi giây; sau log, trục chỉ còn đến khoảng 4,8 và các flow dài hơn tách ra thành nhiều cột. Cột đầu vẫn cao vì nhiều flow có duration gần không, và log của một cộng không vẫn bằng không; log1p chỉ nén đuôi lớn chứ không làm mất đỉnh ở không.

**Chỉ vào hình:** Chỉ công thức và dòng '17 cột liên tục', rồi so hai histogram: trục 0–120 thành 0–4,8; giải thích cột đầu vẫn cao.

**Chuyển ý:** Sau khi nén, các giao thức vẫn ở mức khác nhau; bước hai đưa mỗi flow về thang của chính giao thức của nó.

**Nếu thầy hỏi:** Histogram dựng lại từ 200.000 mẫu train đã lưu sau AFN bằng tham số chuẩn hóa đã lưu nên có sai số float32; không lấy từ test.

**Nguồn:** fl_ddos/multidataset_prep.py: log1p_valid; data_paper_multi_4c/main/prep_params.json và train client_1..4.parquet

## 10 · Bước 2 · Chuẩn hóa z-score theo giao thức (AFN)

**Giai đoạn:** Chuẩn hóa dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi cột được trừ trung bình μ và chia độ lệch chuẩn σ của chính giao thức của flow; μ, σ chỉ học từ train của 4 client.

**Mục tiêu:** Nói rõ công thức z-score, nhóm theo giao thức để làm gì, và chứng minh bằng ví dụ số thật.

**Nội dung trên slide:**

- Tách train theo TCP / UDP / ICMP / OTHER; tính μ, σ cho từng cột trong từng nhóm
- Client gửi n, Σx, Σx²; server cộng lại thành μ, σ, không gửi dòng dữ liệu
- z = (x′ − μ_nhóm) / σ_nhóm; ví dụ 25 gói: TCP z ≈ 0, UDP z ≈ +0,87
- Val/test áp lại; σ ≈ 0 → 1; nhóm thiếu → μ, σ chung; missing → 0

**Lời trình bày:**

Bước hai là chuẩn hóa z-score, em gọi là AFN, tức chuẩn hóa đặc trưng thích nghi theo nhóm. Công thức quen thuộc: z bằng x trừ trung bình rồi chia độ lệch chuẩn. Điểm khác là trung bình và độ lệch chuẩn không tính chung cho mọi flow, mà tính riêng cho từng giao thức TCP, UDP, ICMP, OTHER. Vì sao? Bên phải là ví dụ thật từ tham số đã học: một flow có hai mươi lăm gói. Flow TCP trung bình khoảng hai mươi lăm gói, nên với TCP flow này cho z gần không, tức bình thường. Flow UDP trung bình chỉ khoảng tám gói, nên cùng hai mươi lăm gói, với UDP z bằng cộng 0,87, tức nhiều hơn mức thường. Nếu không tách giao thức, tức dùng một cặp trung bình và độ lệch chuẩn cho mọi flow, hai mức này bị trộn lẫn. Bảng phía dưới cho thấy điều này không chỉ đúng với số gói: trên train, flow TCP điển hình khoảng hai mươi lăm gói và kéo dài khoảng một giây, UDP khoảng tám gói nhưng tốc độ byte cao hơn nhiều; mỗi giao thức có một mức bình thường riêng. Về cách tính trong học liên kết: mỗi client chỉ gửi số mẫu, tổng và tổng bình phương theo từng nhóm; server cộng lại là ra trung bình và độ lệch chuẩn, không cần gửi dòng dữ liệu nào. Các tham số này chỉ học từ train; validation và test chỉ áp lại. Nếu độ lệch chuẩn gần không thì chia cho một, nhóm không có mẫu thì dùng tham số chung, và ô missing được đặt bằng không, tức bằng mức trung bình.

**Chỉ vào hình:** Đọc ba bước bên trái, rồi chỉ ví dụ bên phải: cùng 25 gói, TCP z ≈ 0 còn UDP z ≈ +0,87; cuối cùng dòng 'μ, σ chỉ học từ train'.

**Chuyển ý:** Khi các giá trị đã chuẩn hóa, em lựa chọn phần thông tin cần đưa vào mô hình.

**Nếu thầy hỏi:** Không có secure aggregation hoặc differential privacy trong thí nghiệm này; việc gửi thống kê không tự bảo đảm riêng tư tuyệt đối.

**Nguồn:** fl_ddos/multidataset_prep.py: afn_stats, aggregate_afn, apply_afn

## 11 · Nguyên lý DAS (Dual Adaptive Selector)

**Giai đoạn:** Lựa chọn đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** DAS gồm hai bước: CRA chấm điểm mức liên quan của từng đặc trưng với nhãn, IDF duyệt theo điểm để bỏ cột trùng thông tin.

**Mục tiêu:** Giải thích tiêu chí DAS theo đúng triển khai thay vì xem đây là hộp đen.

**Nội dung trên slide:**

- CRA: trung bình ρ² giữa đặc trưng và chỉ báo từng lớp
- IDF: bỏ nếu relevance ≤ 0,001 hoặc |ρ| ≥ 0,9 với cột đã giữ
- Tối đa 12 cột liên tục; 6 cột cố định không qua DAS

**Lời trình bày:**

DAS, viết tắt của Dual Adaptive Selector, gồm hai bước. Bước một là CRA, Conditional Relevance Assessor: với mỗi đặc trưng, em tính hệ số tương quan với chỉ báo của từng lớp, bình phương lên rồi lấy trung bình; điểm càng cao thì đặc trưng càng giúp phân biệt các lớp. Bước hai là IDF, Iterative Dependency Filter: duyệt các đặc trưng theo điểm từ cao xuống thấp, bỏ cột có điểm quá thấp, bỏ cột tương quan từ 0,9 trở lên với một cột đã giữ vì trùng thông tin, và dừng khi đủ mười hai cột.

**Chỉ vào hình:** Đọc công thức CRA bên trái, rồi bốn bước IDF bên phải; dải dưới tóm tắt luồng 17 → 12.

**Chuyển ý:** Áp dụng lên dữ liệu thật, đây là điểm CRA của 17 đặc trưng.

**Nếu thầy hỏi:** Thống kê tính trên train sau log1p + AFN, gộp từ 4 client bằng các tổng đủ (n, Σx, Σxxᵀ, Σx·y), không dùng validation hay test. Cột hằng có relevance = 0.

**Nguồn:** fl_ddos/multidataset_prep.py: das_relevance, das_select; configs/multidataset.json: das

## 12 · Kết quả CRA: điểm liên quan của 17 đặc trưng

**Giai đoạn:** Lựa chọn đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** 12 cột được giữ; 4 cột bị loại vì trùng thông tin, 1 cột vì relevance quá thấp.

**Mục tiêu:** Giải thích các quyết định DAS bằng số liệu và quan sát khác biệt relevance giữa các client.

**Nội dung trên slide:**

- Cao nhất: bwd_packets_s, fwd_packet_size_mean, bwd_byte_fraction
- 4 cột trùng thông tin: total_bytes, bwd_bytes, total_packets, fwd_packets_s
- bwd_iat_mean_s: relevance ≈ 0

**Lời trình bày:**

Đây là điểm CRA thực tế của mười bảy đặc trưng, sắp từ cao xuống thấp. Màu xanh là cột được giữ. Bốn cột màu cam có điểm khá cao nhưng bị loại vì gần như trùng với một cột đã giữ phía trên, ví dụ total_bytes trùng fwd_bytes. Cột xám bwd_iat_mean_s bị loại vì điểm gần bằng không.

**Chỉ vào hình:** Chỉ ba cột đầu, rồi các dòng cam và lý do bên phải.

**Chuyển ý:** Ma trận tương quan cho thấy rõ vì sao bốn cột kia bị coi là trùng.

**Nếu thầy hỏi:** Trùng thông tin được đo bằng hệ số tương quan Pearson |ρ| trên train giữa cột đang xét và từng cột đã giữ; |ρ| ≥ 0,9 nghĩa là biết cột này gần như đoán được cột kia. Ví dụ total_bytes = fwd_bytes + bwd_bytes mà byte chủ yếu đi chiều đi, nên total_bytes ≈ fwd_bytes. Thứ hạng theo thống kê gộp 4 client; relevance từng client ở phụ lục A4.

**Nguồn:** data_paper_multi_4c/main/feature_selection.csv

## 13 · Kết quả IDF: lọc cột trùng qua ma trận tương quan

**Giai đoạn:** Lựa chọn đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** Bốn cặp có |ρ| ≥ 0,9; trong mỗi cặp, cột có điểm CRA thấp hơn bị loại.

**Mục tiêu:** Cho thấy bằng số liệu thật vì sao IDF loại các cột trùng thông tin.

**Nội dung trên slide:**

- total_bytes – fwd_bytes: 0,977
- bwd_bytes – bwd_packets: 0,953
- total_packets – fwd_packets: 0,986 · fwd_packets_s – flow_packets_s: 0,998

**Lời trình bày:**

Mỗi ô là trị tuyệt đối hệ số tương quan giữa hai đặc trưng, màu càng đậm càng giống nhau. Bốn ô viền đỏ là các cặp có tương quan từ 0,9 trở lên, ví dụ fwd_packets_s và flow_packets_s gần như bằng nhau với 0,998. Trong mỗi cặp, IDF giữ cột có điểm CRA cao hơn và bỏ cột còn lại, nên mô hình không phải học cùng một thông tin hai lần.

**Chỉ vào hình:** Chỉ các ô viền đỏ trên ma trận rồi đối chiếu với danh sách bên phải.

**Chuyển ý:** Kết quả cuối cùng là bộ đầu vào đưa vào huấn luyện.

**Nếu thầy hỏi:** Ma trận được tính lại từ train đã lưu (artifact ALL, 4 client, sau log1p + AFN); bộ build kiểm tra CRA và |ρ| khớp với feature_selection.csv.

**Nguồn:** data_paper_multi_4c/main_all/multidataset/client_*.parquet; data_paper_multi_4c/main/feature_selection.csv; presentation/build.py: das_correlation

## 14 · Bộ đầu vào cuối cùng

**Giai đoạn:** Lựa chọn đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** 18 đầu vào DAS = 12 cột liên tục được giữ + 6 cột cố định; ALL 23 cột giữ làm đối chứng.

**Mục tiêu:** Chốt thiết kế đối chứng đặc trưng trước khi trình bày kết quả.

**Nội dung trên slide:**

- 12 cột liên tục được giữ
- 6 cột cố định: 4 one-hot giao thức + 2 cờ duration
- 5 cột bị loại; ALL 23 cột dùng làm đối chứng

**Lời trình bày:**

Kết quả của DAS là mười tám đầu vào để huấn luyện: mười hai cột liên tục được giữ và sáu cột cố định. Năm cột bị loại nằm bên phải cùng lý do. Em vẫn giữ bộ ALL hai mươi ba cột làm đối chứng, cùng split và cùng mẫu, để kiểm tra ở giai đoạn kết quả xem bỏ năm cột này ảnh hưởng thế nào.

**Chỉ vào hình:** Đọc khối xanh (đưa vào huấn luyện), khối xám (bị loại), rồi dải ALL − 5 = DAS.

**Chuyển ý:** Với bộ đầu vào này, em chuyển sang kiến trúc mô hình và cách huấn luyện.

**Nguồn:** data_paper_multi_4c/main/features.json; data_paper_multi_4c/main_all/features.json

## 15 · ResVGG-SwinNet học trên biểu diễn của flow

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Một lớp Linear chiếu vector đặc trưng thành lưới 8×8 trước các khối ResNet, VGG và Swin.

**Mục tiêu:** Hiểu vai trò kiến trúc và tránh nhầm dữ liệu flow là ảnh gốc.

**Nội dung trên slide:**

- ResNet: học đặc trưng với đường nối tắt
- VGG: hai lớp convolution 3×3
- Swin: attention cửa sổ thường và cửa sổ dịch

**Lời trình bày:**

Mô hình nhận vector mười tám hoặc hai mươi ba đặc trưng tùy cấu hình. Một lớp Linear học phép chiếu thành sáu mươi tư giá trị rồi sắp thành lưới tám nhân tám. Lưới này không phải ảnh lưu lượng có sẵn; đây là biểu diễn do mô hình học. Phần ResNet có hai residual block để trích xuất với đường nối tắt. Hai lớp convolution kiểu VGG tiếp tục biến đổi biểu diễn, sau đó hai Swin block học quan hệ trong cửa sổ thường và cửa sổ dịch. Cuối cùng lấy trung bình token và dùng đầu Linear để tạo ba logits. Kiến trúc tham khảo bài của Alshdadi và cộng sự năm 2025, không khẳng định tái hiện tuyệt đối mọi chi tiết chưa được bài mô tả. Điểm quan trọng cho phần so sánh: cả tám cấu hình, từ local, centralized đến FedAvg và FedProx, đều dùng đúng mô hình này, chỉ khác số đầu vào, nên khác biệt kết quả đến từ cách học và bộ đặc trưng chứ không đến từ mô hình.

**Chỉ vào hình:** Theo mũi tên qua các khối; nhấn mạnh chữ “lưới học được” tại 8×8.

**Chuyển ý:** Cùng một kiến trúc này được dùng cho mọi cách học; tiếp theo em so sánh local, centralized và FL.

**Nếu thầy hỏi:** Lưới 8×8 không có ý nghĩa không gian sẵn có như ảnh; lớp Linear học cách sắp 64 giá trị sao cho các khối convolution và attention phía sau khai thác được. Em giữ kiến trúc theo bài tham khảo để so sánh, không khẳng định đây là kiến trúc tối ưu cho dữ liệu dạng bảng; một MLP là hướng đối chứng tiếp theo.

**Nguồn:** fl_ddos/models.py: ResVGGSwinNet

## 16 · Local, centralized và FL tổ chức việc học ra sao?

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** FL cho phép phối hợp học từ hai nguồn bằng cập nhật mô hình; hiệu quả cần được kiểm chứng riêng.

**Mục tiêu:** Nêu lý do chọn FL mà không mặc định FL luôn có độ chính xác cao hơn.

**Nội dung trên slide:**

- Local: mỗi mô hình chỉ học dữ liệu của một client
- Centralized: gộp train hai nguồn
- FL: train cục bộ rồi tổng hợp trọng số

**Lời trình bày:**

Local-only tạo bốn mô hình riêng, mỗi mô hình chỉ được học dữ liệu của một client, tức một nửa train của một nguồn. Centralized gộp train của hai nguồn thành một tập và huấn luyện trực tiếp, là đối chứng khi việc tập trung dữ liệu được phép. FL giữ việc học theo client và phối hợp qua các cập nhật mô hình. Lý do nghiên cứu FL là khả năng học chung mà không cần tập trung dữ liệu thô trong quy trình thuật toán. Điều đó không tự chứng minh riêng tư tuyệt đối, vì cập nhật hoặc thống kê vẫn có thể chứa thông tin. Đồng thời, không có bảo đảm FL luôn chính xác hơn local hay centralized. Phần kết quả sẽ đo riêng hiệu quả và khả năng tổng quát theo từng nguồn.

**Chỉ vào hình:** Chỉ loại thông tin đi trên mũi tên: dữ liệu ở centralized, trọng số ở FL.

**Chuyển ý:** Với FL, mỗi vòng học được thực hiện theo chu trình sau.

**Nếu thầy hỏi:** Centralized là mốc thực nghiệm khi được phép gom dữ liệu, không phải cận trên lý thuyết. FL chỉ gửi trọng số mô hình, nhưng trọng số vẫn có thể rò rỉ thông tin; thí nghiệm không dùng secure aggregation hay differential privacy.

**Nguồn:** baselines/multidataset_baselines.py; fl_ddos/multidataset_server.py; https://proceedings.mlr.press/v54/mcmahan17a.html

## 17 · Một vòng FedAvg: gửi, học, nhận, tổng hợp

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Cả bốn client tham gia mỗi vòng; server gộp trọng số theo số mẫu train.

**Mục tiêu:** Mô tả vòng lặp và phân biệt trọng số client với trọng số lớp trong loss.

**Nội dung trên slide:**

- 30 vòng × 5 epoch cục bộ; Adam, lr 0,001
- Batch 64, dropout 0,3, weighted cross-entropy
- 50.000 mẫu/client → trọng số tổng hợp 25% mỗi client

**Lời trình bày:**

Đầu vòng, server gửi cùng một mô hình toàn cục đến bốn client. Mỗi client huấn luyện năm epoch trên train của mình, sử dụng Adam và loss có trọng số lớp. Sau đó client gửi trọng số cùng số mẫu, server kiểm tra đủ bốn PID và tổng hợp theo số mẫu thực. Vì bốn client cùng có năm mươi nghìn mẫu train, hệ số ở phép trung bình là một phần tư cho mỗi client; tính theo nguồn thì CIC và UNSW vẫn mỗi bên một nửa. Đây là trọng số tổng hợp mô hình, khác với class weight trong loss: class weight là nghịch đảo tần suất lớp tại từng client, nên lớp càng ít mẫu càng được nhân trọng số lớn. Ví dụ ở UNSW, DoS chỉ chiếm khoảng mười phần trăm nên có trọng số khoảng 2,05, còn ở CIC lớp OTHER_ATTACK không có nên trọng số bằng không. Quy trình lặp ba mươi vòng; sau mỗi lần tổng hợp, mô hình được đánh giá trên validation của bốn client và điểm chọn mô hình là trung bình theo nguồn. Các nút trên hình lần lượt mở từng bước để dễ theo dõi luồng.

**Chỉ vào hình:** Bấm lần lượt các bước 1 → 4 trên pipeline; ở bước 4 đọc công thức trung bình trọng số.

**Chuyển ý:** FedAvg là cách tổng hợp cơ bản; FedProx sửa phần học tại client để xử lý dữ liệu khác phân phối.

**Nếu thầy hỏi:** Trọng số 25% đến từ FedAvg chuẩn (tỷ lệ số mẫu train) và cả bốn client đều có 50.000 mẫu. Class weight được tính trên train của từng client rồi cố định, không học từ validation hay test.

**Nguồn:** fl_ddos/multidataset_server.py; fl_ddos/task.py: train; configs/multidataset.json: fl

## 18 · FedProx: thêm điểm neo cho việc học tại client

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Client tối ưu loss dữ liệu cộng μ/2 · ‖w − w_global‖²; server vẫn tổng hợp theo FedAvg.

**Mục tiêu:** Hiểu chính xác vị trí và tác dụng mong muốn của số hạng proximal.

**Nội dung trên slide:**

- Mốc tham chiếu là trọng số toàn cục ở đầu mỗi vòng
- μ = 0 trở về loss cục bộ của cấu hình FedAvg
- Thí nghiệm dùng μ = 0,1; không phải cơ chế chống đầu độc

**Lời trình bày:**

FedProx thay đổi mục tiêu học tại client bằng cách cộng một số hạng phạt khoảng cách bình phương từ trọng số hiện tại đến mô hình toàn cục đầu vòng. Client vẫn muốn giảm lỗi trên dữ liệu riêng, đồng thời phải trả chi phí khi đi quá xa điểm khởi đầu chung. Khi μ bằng không thì không còn số hạng này. Trong thử nghiệm, μ là 0,1 và server vẫn dùng phép trung bình có trọng số như FedAvg. Ràng buộc này nhằm xử lý khó khăn tối ưu với dữ liệu không đồng nhất, nhưng không loại bỏ khác biệt miền và không tự bảo đảm chống client độc hại. Tác dụng cuối cùng vẫn phải đọc từ kết quả và các đánh đổi.

**Chỉ vào hình:** Chỉ hai thành phần loss và sơ đồ điểm neo; hình hướng cập nhật chỉ là minh họa.

**Chuyển ý:** Với hai cách tổng hợp này, em cố định ma trận thí nghiệm và quy tắc chọn checkpoint.

**Nếu thầy hỏi:** μ = 0,1 nằm trong dải giá trị bài FedProx đã thử (0,001 đến 1); em chưa dò μ bằng validation, đây là một hạn chế. Số hạng proximal chỉ làm chậm việc client trôi khỏi mô hình chung, không phải cơ chế chống client độc hại.

**Nguồn:** fl_ddos/task.py: train; fl_ddos/multidataset_server.py; https://arxiv.org/abs/1812.06127

## 19 · Cố định đối chứng, chọn mô hình bằng validation

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Tám checkpoint đại diện cho các cách học và bộ đặc trưng; test không dùng để chọn vòng.

**Mục tiêu:** Hiểu thiết kế đối chứng, checkpoint selection và giới hạn của một seed.

**Nội dung trên slide:**

- FL: ALL / DAS / DAS + FedProx μ=0,1
- 4 local (mỗi client một mô hình) và centralized dùng DAS, 150 epoch
- Một seed 0; best FL theo trung bình F1-macro-present theo nguồn trên validation

**Lời trình bày:**

Ma trận thí nghiệm gồm FedAvg ALL, FedAvg DAS, FedProx DAS, một centralized DAS và bốn mô hình local DAS, mỗi client một mô hình. Các baseline dùng một trăm năm mươi epoch, tương ứng mốc ba mươi vòng nhân năm epoch cục bộ, nhưng đây không phải bảo đảm các phương pháp có chi phí tính toán hoàn toàn bằng nhau. Best FL và centralized được chọn theo trung bình đều theo nguồn của F1-macro-present trên validation: lấy trung bình hai client cùng nguồn trước, rồi trung bình hai nguồn. Local được chọn theo validation của chính client. Sau khi chốt, một checkpoint được đánh giá trên hai test. Toàn bộ kết quả chính chỉ có seed không, nên chưa có độ lệch chuẩn giữa các lần chạy. FL và local nằm trong một run, centralized chạy riêng nhưng cùng bundle dữ liệu; các job dùng GPU A10 hoặc A10G nên không so sánh tốc độ trực tiếp.

**Chỉ vào hình:** Chỉ các cấu hình cùng DAS và nhánh ALL; chỉ ranh giới validation → chọn best → test.

**Chuyển ý:** Sau khi đã chốt mô hình, em chuyển sang cách đọc và phân tích kết quả.

**Nếu thầy hỏi:** 150 epoch cho baseline để tổng số epoch bằng 30 vòng × 5 epoch của FL; đây là cân bằng số lượt học, không phải cân bằng chi phí tính toán. Chỉ có seed 0 nên chưa có độ lệch chuẩn giữa các lần chạy.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/status_snapshot.json; results_modal_multidataset/20261122_235344_298853/status_snapshot.json; baselines/multidataset_baselines.py

## 20 · Phương pháp đánh giá

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Mô hình dự đoán một lần ra 3 xác suất; ba câu hỏi là ba cách đọc kết quả đó, mỗi câu có bộ chỉ số riêng.

**Mục tiêu:** Người nghe hiểu ba thước đo trước khi xem số.

**Nội dung trên slide:**

- Thuộc lớp nào? → F1 macro, Acc
- Có phải tấn công? → Attack F1, recall, FAR, AUC
- Có phải DoS/DDoS? → DoS F1, recall, FAR, AUC
- Điểm cuối = trung bình test CIC và test UNSW

**Lời trình bày:**

Phần này em trình bày phương pháp đánh giá. Mô hình chỉ dự đoán một lần và cho ra ba xác suất cho mỗi flow: bình thường, DoS/DDoS và tấn công khác. Từ ba xác suất đó em đặt ba câu hỏi. Một, flow thuộc lớp nào: lấy lớp có xác suất cao nhất, đo bằng F1 macro và accuracy. Hai, flow có phải tấn công không: báo tấn công khi một trừ xác suất bình thường từ 0,5 trở lên, đo bằng F1, recall, tỷ lệ báo động giả FAR và AUC. Ba, flow có phải DoS/DDoS không, đúng mục tiêu chính của đề tài: dùng xác suất DoS/DDoS với cùng ngưỡng và cùng bốn chỉ số. FAR càng thấp càng tốt, các chỉ số còn lại càng cao càng tốt. Mỗi chỉ số tính riêng trên test CIC và test UNSW rồi lấy trung bình.

**Chỉ vào hình:** Chỉ dòng ví dụ 3 xác suất ở trên, rồi đi thẻ 1 → 3: cách quyết định, kết quả của ví dụ, và các chỉ số tương ứng với cột trong bảng kết quả.

**Chuyển ý:** Với ba thước đo này, đây là kết quả của cả tám mô hình.

**Nếu thầy hỏi:** F1 macro chỉ tính trên các lớp thật sự có trong từng nguồn (CIC không có OTHER_ATTACK), gọi là F1-macro-present. Ngưỡng 50% cố định, chưa tối ưu bằng validation. Điểm cuối lấy trung bình hai nguồn để nguồn lớn không lấn át; số tính trên dự đoán gộp nằm ở phụ lục.

**Nguồn:** fl_ddos/multidataset_eval.py: source_metrics, binary_block, evaluate_checkpoint

## 21 · Kết quả của 8 mô hình

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Centralized có F1 macro cao nhất (60,89%); trong học liên kết, FedProx dẫn F1 macro (56,99%) nhưng không mô hình nào thắng mọi chỉ số.

**Mục tiêu:** Cho thấy toàn cảnh kết quả trên một bảng trước khi so sánh chi tiết.

**Nội dung trên slide:**

- Local: 42–47% F1 macro; Local UNSW báo nhầm tới 39–44%
- Centralized: 60,89% F1 macro
- FedProx DAS 56,99% · FedAvg ALL 50,26% F1 DoS · FedAvg DAS FAR 3,01%

**Lời trình bày:**

Bảng này là toàn bộ kết quả, mỗi ô là trung bình hai nguồn test. Các mô hình local chỉ đạt khoảng 42 đến 47 phần trăm F1 macro, và hai local UNSW báo nhầm rất nhiều, gần 40 phần trăm. Centralized, gom toàn bộ dữ liệu về một chỗ, đạt cao nhất 60,89 phần trăm. Trong ba mô hình học liên kết, FedProx cao nhất về F1 macro với 56,99 phần trăm; FedAvg với đủ đặc trưng bắt DoS/DDoS tốt nhất; còn FedAvg với DAS ít báo nhầm nhất, chỉ 3,01 phần trăm. FedProx hơn FedAvg khoảng mười điểm F1 macro chủ yếu nhờ UNSW: FedAvg chỉ đạt khoảng 34 phần trăm trên UNSW, FedProx kéo lên khoảng 61 phần trăm, chỉ kém centralized 3,9 điểm. Không có mô hình nào thắng mọi chỉ số.

**Chỉ vào hình:** Đọc theo ba nhóm cột ①②③ như slide phương pháp; chỉ các ô xanh là tốt nhất mỗi cột, rồi đọc dòng kết luận.

**Chuyển ý:** Tiếp theo em xem kỹ ba mô hình học liên kết đánh đổi nhau thế nào.

**Nếu thầy hỏi:** Kết quả chỉ có một seed nên chưa có độ lệch chuẩn; chênh lệch dưới khoảng 1 điểm phần trăm chưa đủ để kết luận.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/*/evaluation_by_dataset.csv; results_modal_multidataset/20261122_235344_298853/main/das/evaluation_by_dataset.csv

## 22 · Ma trận nhầm lẫn: mô hình sai ở đâu

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi hàng là nhãn thật, mỗi cột là nhãn mô hình đoán; đường chéo là đoán đúng, ô ngoài đường chéo là nhầm.

**Mục tiêu:** Cho thấy cụ thể mô hình nhầm lớp nào với lớp nào, thay vì chỉ một con số tổng.

**Nội dung trên slide:**

- Chọn mô hình và nguồn test ở góc trên
- FedAvg DAS không đoán lớp Tấn công khác: 78% của lớp này trên UNSW bị coi là bình thường; FedProx đoán đúng 58%
- Recall theo lớp bên phải: % mẫu thật của lớp được đoán đúng

**Lời trình bày:**

Ma trận nhầm lẫn cho biết mô hình sai ở đâu. Mỗi hàng là nhãn thật, mỗi cột là nhãn mô hình đoán; ô trên đường chéo là đoán đúng, ô ngoài đường chéo là nhầm. Bên phải là recall của từng lớp, tức bao nhiêu phần trăm mẫu thật của lớp đó được đoán đúng. Điểm đáng chú ý thứ nhất: FedAvg DAS không bao giờ đoán lớp tấn công khác, nên trên UNSW khoảng 78 phần trăm tấn công khác bị đoán là bình thường; đó là lý do FedAvg học UNSW kém. FedProx thì đoán đúng khoảng 58 phần trăm lớp này. Thứ hai, trên CIC cả hai mô hình đều đoán phần lớn DoS/DDoS thành bình thường, khoảng 58 đến 62 phần trăm, vì test CIC lấy từ một ngày thu thập khác. Trên CIC, lớp tấn công khác không có mẫu thật nên ghi N/A.

**Chỉ vào hình:** Chọn FedAvg · DAS, nguồn UNSW: chỉ cột Tấn công khác toàn 0; đổi sang FedProx · DAS để so; cuối cùng đổi nguồn CIC để thấy DoS/DDoS bị đoán thành bình thường.

**Chuyển ý:** Từ bảng số và ma trận nhầm lẫn, em nhận xét ưu và nhược điểm của từng phương pháp.

**Nếu thầy hỏi:** Ma trận dùng nhãn có xác suất cao nhất; FAR nhị phân dùng ngưỡng 0,5 trên xác suất riêng nên có thể khác nhẹ so với đọc từ ma trận.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/*/confusion*.csv

## 23 · Nhận xét: ưu và nhược điểm của từng phương pháp

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Học liên kết vượt các mô hình tự học và tiến gần centralized mà không cần gom dữ liệu, nhưng không có phương pháp nào tốt nhất mọi mặt.

**Mục tiêu:** Nhận xét ưu / nhược điểm bằng hình so sánh trực quan thay vì chỉ đọc số.

**Nội dung trên slide:**

- Local: không chia sẻ gì nhưng F1 thấp, báo nhầm nhiều
- Centralized: F1 macro cao nhất nhưng phải gom dữ liệu
- FedAvg ALL bắt DoS tốt nhất · FedAvg DAS ít báo nhầm nhất · FedProx F1 macro cao nhất trong FL

**Lời trình bày:**

Biểu đồ radar này gom sáu chỉ số, càng ra ngoài càng tốt; mỗi đường là một phương pháp. Local tự học có đường bao nhỏ nhất: không phải chia sẻ gì nhưng F1 thấp và báo nhầm nhiều. Centralized có đường bao lớn nhất ở F1 macro và DoS, nhưng phải gom toàn bộ dữ liệu về một chỗ. Ba cấu hình học liên kết mỗi cái mạnh một hướng: FedAvg với đủ đặc trưng bắt DoS tốt nhất, FedAvg với DAS ít báo nhầm nhất, còn FedProx có F1 macro cao nhất trong học liên kết, chỉ kém centralized 3,9 điểm, đổi lại báo nhầm tăng lên khoảng 17 phần trăm. Vì vậy chọn phương pháp theo mục tiêu vận hành.

**Chỉ vào hình:** Chọn "Làm nổi bật" lần lượt từng phương pháp để đường của nó đậm lên, đọc ô ưu / nhược tương ứng bên phải.

**Chuyển ý:** Phần trình bày của nhóm em đến đây là hết, em xin cảm ơn thầy đã lắng nghe.

**Nếu thầy hỏi:** Chỉ có một seed và ngưỡng 0,5 cố định; chênh lệch dưới khoảng 1 điểm phần trăm chưa đủ để kết luận.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/*/evaluation_by_dataset.csv; results_modal_multidataset/20261122_235344_298853/main/das/evaluation_by_dataset.csv

## Tài liệu phương pháp

- [FedAvg · McMahan et al. (2017)](https://proceedings.mlr.press/v54/mcmahan17a.html)
- [FedProx · Li et al. (2020)](https://arxiv.org/abs/1812.06127)
- [Phương pháp tham khảo · Alshdadi et al. (2025)](https://doi.org/10.3390/fi17020088)
