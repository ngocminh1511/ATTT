# Kịch bản thuyết trình — Học liên kết phát hiện tấn công mạng

Sinh từ `src/slides.json`; chỉnh nguồn rồi chạy `python presentation/build.py`.

Pipeline: dữ liệu → làm sạch → chia tập → tạo đặc trưng → chuẩn hóa → DAS → huấn luyện → kết quả → kết luận.

Các giá trị thực nghiệm: 4 client (CIC → 1, 2; UNSW → 3, 4), profile main, seed 0; F1 tổng hợp là trung bình đều F1-macro-present hai nguồn, trừ khi ghi khác.

## 00 · Từ dữ liệu phân tán đến mô hình phát hiện tấn công

**Giai đoạn:** Pipeline · **Trạng thái:** Đang bật

**Thông điệp:** Một pipeline, chín giai đoạn. Bấm vào từng bước để khám phá cách thực hiện và bằng chứng.

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

## 01 · Hai bộ dữ liệu

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

## 02 · Chuẩn hóa schema & đơn vị

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

## 03 · Gom nhãn về 3 lớp

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

## 04 · Kiểm tra chất lượng

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

## 05 · Tách test & validation

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

## 06 · Lấy subset & chia 4 client

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

## 07 · 8 trường cơ sở → 23 cột đầu vào

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

## 08 · Bước 1 · Biến đổi log1p

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

## 09 · Bước 2 · Chuẩn hóa z-score theo giao thức (AFN)

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

## 10 · DAS giữ thông tin liên quan, lọc phần dư thừa

**Giai đoạn:** Lựa chọn đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** CRA xếp hạng theo nhãn; IDF duyệt theo thứ hạng để loại cột trùng thông tin.

**Mục tiêu:** Giải thích tiêu chí DAS theo đúng triển khai thay vì xem đây là hộp đen.

**Nội dung trên slide:**

- CRA: trung bình r² với chỉ báo từng lớp có phương sai
- IDF: bỏ cột có |r| ≥ 0,9 với cột đã chọn
- Relevance > 0,001; tối đa 12 cột liên tục

**Lời trình bày:**

DAS trong pipeline gồm hai phần. CRA đo liên quan bằng bình phương tương quan giữa đặc trưng và chỉ báo từng lớp, rồi lấy trung bình các lớp có phương sai. Thống kê được gộp từ train của bốn client, tức hai nguồn. Sau khi xếp relevance giảm dần, IDF xét từng đặc trưng: bỏ cột hằng, cột có relevance không vượt 0,001, hoặc cột có tương quan tuyệt đối từ 0,9 với một cột đã giữ. Số cột liên tục được giữ không vượt mười hai. Nhãn chỉ tham gia chọn đặc trưng trên train; không dùng nhãn validation hoặc test để quyết định danh sách. Đây là chọn một bộ chung cho cả bốn client, chưa phải chọn riêng theo nguồn.

**Chỉ vào hình:** Theo ba cửa lọc: liên quan → dư thừa → giới hạn số lượng.

**Chuyển ý:** Bảng xếp hạng thực tế cho biết các tiêu chí này đã loại những cột nào.

**Nguồn:** fl_ddos/multidataset_prep.py: das_stats, das_relevance, das_select

## 11 · Từ tiêu chí đến quyết định giữ hoặc loại

**Giai đoạn:** Lựa chọn đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** Danh sách thực tế giữ 12 cột liên tục, loại bốn cột dư thừa và một cột ít liên quan.

**Mục tiêu:** Giải thích các quyết định DAS bằng số liệu và quan sát khác biệt relevance giữa các client.

**Nội dung trên slide:**

- total_bytes tương quan 0,977 với fwd_bytes
- total_packets tương quan 0,986 với fwd_packets
- bwd_iat_mean_s bị loại do relevance ≤ 0,001

**Lời trình bày:**

Bảng này lấy trực tiếp từ feature_selection.csv. bwd_packets_s có relevance gộp cao nhất, tiếp theo là fwd_packet_size_mean và các tỷ lệ chiều về. total_bytes dù có relevance tương đối cao vẫn bị loại vì tương quan 0,977 với fwd_bytes đã chọn. total_packets cũng bị loại do tương quan với fwd_packets. Ngược lại, bwd_iat_mean_s bị loại vì relevance gộp quá thấp. Bộ chọn pooled hoặc từng client cho thấy cùng một đặc trưng có thể liên quan rất khác theo miền: hai client CIC gần như giống nhau, còn khác biệt lớn nằm giữa client CIC và client UNSW. Tuy nhiên, đổi cách xem biểu đồ không làm hệ thống chọn lại danh sách; quyết định giữ hoặc loại vẫn là kết quả pooled trên train.

**Chỉ vào hình:** Đổi giữa pooled, client CIC và client UNSW rồi chỉ total_bytes và bwd_iat_mean_s; màu thể hiện quyết định pooled.

**Chuyển ý:** Từ đây em tạo hai cấu hình đầu vào để đo riêng đóng góp của bước chọn đặc trưng.

**Nguồn:** data_paper_multi_4c/main/feature_selection.csv

## 12 · ALL và DAS khác nhau ở bộ đầu vào

**Giai đoạn:** Lựa chọn đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** Cùng split, cùng mẫu và cùng quy trình chuẩn hóa; so sánh 23 với 18 đầu vào.

**Mục tiêu:** Chốt thiết kế đối chứng đặc trưng trước khi trình bày kết quả.

**Nội dung trên slide:**

- ALL: toàn bộ 17 cột liên tục hợp lệ + 6 cột cố định
- DAS: 12 cột liên tục được chọn + 6 cột cố định
- Không suy ra mức tiết kiệm thời gian hay truyền thông từ tỷ lệ giảm cột

**Lời trình bày:**

Nhánh ALL giữ toàn bộ mười bảy cột liên tục hợp lệ, còn DAS giữ mười hai cột đã chọn. Cả hai cùng có sáu cột cố định nên đầu vào cuối là hai mươi ba và mười tám cột. Hash split của hai artifact giống nhau, giúp bảo đảm đối chứng không thay đổi mẫu dữ liệu khi đổi đặc trưng. Hai nhánh dùng cùng kiến trúc tổng quát và ngân sách huấn luyện, nhưng lớp Linear đầu vào có kích thước phụ thuộc số cột. Giảm cột chỉ cho thấy biểu diễn gọn hơn; chưa thể suy ra phần trăm giảm chi phí toàn mô hình hoặc thời gian. Các kết quả dự đoán sẽ được kiểm chứng ở giai đoạn tám.

**Chỉ vào hình:** Chỉ hai nhánh, sáu cột giữ chung, và dấu xác nhận cùng split.

**Chuyển ý:** Sau khi cố định đầu vào, em trình bày kiến trúc sẽ học trên các vector này.

**Nguồn:** data_paper_multi_4c/main/features.json; data_paper_multi_4c/main_all/features.json

## 13 · ResVGG-SwinNet học trên biểu diễn của flow

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

## 14 · Local, centralized và FL tổ chức việc học ra sao?

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

## 15 · Một vòng FedAvg: gửi, học, nhận, tổng hợp

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Cả bốn client tham gia mỗi vòng; server gộp trọng số theo số mẫu train.

**Mục tiêu:** Mô tả vòng lặp và phân biệt trọng số client với trọng số lớp trong loss.

**Nội dung trên slide:**

- 30 vòng × 5 epoch cục bộ; Adam, lr 0,001
- Batch 64, dropout 0,3, weighted cross-entropy
- 50.000 mẫu/client → trọng số tổng hợp 25% mỗi client
- Class weight: nghịch đảo tần suất lớp tại client, giới hạn [0,1; 10], lớp vắng = 0

**Lời trình bày:**

Đầu vòng, server gửi cùng một mô hình toàn cục đến bốn client. Mỗi client huấn luyện năm epoch trên train của mình, sử dụng Adam và loss có trọng số lớp. Sau đó client gửi trọng số cùng số mẫu, server kiểm tra đủ bốn PID và tổng hợp theo số mẫu thực. Vì bốn client cùng có năm mươi nghìn mẫu train, hệ số ở phép trung bình là một phần tư cho mỗi client; tính theo nguồn thì CIC và UNSW vẫn mỗi bên một nửa. Đây là trọng số tổng hợp mô hình, khác với class weight trong loss ở dải phía dưới: class weight là nghịch đảo tần suất lớp tại từng client, nên lớp càng ít mẫu càng được nhân trọng số lớn. Ví dụ ở UNSW, DoS chỉ chiếm khoảng mười phần trăm nên có trọng số khoảng 2,05, còn ở CIC lớp OTHER_ATTACK không có nên trọng số bằng không. Quy trình lặp ba mươi vòng; sau mỗi lần tổng hợp, mô hình được đánh giá trên validation của bốn client và điểm chọn mô hình là trung bình theo nguồn. Các nút trên hình lần lượt mở từng bước để dễ theo dõi luồng.

**Chỉ vào hình:** Bấm các bước 1–4; đọc công thức FedAvg và phân biệt với bảng class weight.

**Chuyển ý:** FedAvg là cách tổng hợp cơ bản; FedProx sửa phần học tại client để xử lý dữ liệu khác phân phối.

**Nếu thầy hỏi:** Trọng số 25% đến từ FedAvg chuẩn (tỷ lệ số mẫu train) và cả bốn client đều có 50.000 mẫu. Class weight được tính trên train của từng client rồi cố định, không học từ validation hay test.

**Nguồn:** fl_ddos/multidataset_server.py; fl_ddos/task.py: train; configs/multidataset.json: fl

## 16 · FedProx: thêm điểm neo cho việc học tại client

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

## 17 · Cố định đối chứng, chọn mô hình bằng validation

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

## 18 · Ba câu hỏi đánh giá, ba cách đọc kết quả

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Không dùng F1 phân loại ba lớp để thay cho F1 phát hiện riêng DoS/DDoS.

**Mục tiêu:** Phân biệt nhiệm vụ, cách tổng hợp nguồn và các tỷ lệ báo động giả.

**Nội dung trên slide:**

- Ba lớp: argmax, F1-macro-present theo support thật
- Mọi tấn công: điểm 1 − P(BENIGN), ngưỡng 0,5
- DoS/DDoS: điểm P(DOS_DDOS), ngưỡng 0,5

**Lời trình bày:**

Đầu tiên, phân loại ba lớp dùng argmax và tính F1 cho từng lớp có support thật. CIC có hai lớp thật, UNSW có ba lớp, nên F1-macro-present của mỗi nguồn không có cùng số lớp trong phép trung bình. Thứ hai, phát hiện mọi tấn công dùng một trừ xác suất BENIGN với ngưỡng 0,5. Thứ ba, phát hiện riêng DoS/DDoS dùng xác suất DOS_DDOS với cùng ngưỡng. FAR trên benign là tỷ lệ mẫu bình thường bị báo là tấn công của nhiệm vụ tương ứng. Chỉ số tổng hợp chính lấy trung bình đều hai nguồn test, không phải tính F1 từ dự đoán gộp. Các bảng luôn ghi rõ nhiệm vụ và cách gộp để tránh hiểu nhầm.

**Chỉ vào hình:** Chỉ điểm số, ngưỡng và nhãn thật của từng nhiệm vụ; chỉ chú thích mean khác pooled.

**Chuyển ý:** Với cách đọc đó, trước hết em so sánh các cách tổ chức việc học.

**Nguồn:** fl_ddos/multidataset_eval.py: source_metrics, binary_block, evaluate_checkpoint

## 19 · Học liên kết chỉ vượt local rõ rệt khi dùng FedProx

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Với cùng DAS, FedAvg đạt 46,89% F1-macro trung bình, ngang local tốt nhất (46,63%); centralized đạt 60,89%.

**Mục tiêu:** Đọc trung thực mức lợi của học chung so với local, không phóng đại kết quả FedAvg.

**Nội dung trên slide:**

- Local CIC #1/#2: 42,07% / 42,00%; Local UNSW #3/#4: 46,63% / 44,02%
- FedAvg DAS chỉ hơn local tốt nhất 0,26 điểm phần trăm
- Trên nguồn riêng, local vẫn có thể tốt hơn mô hình chung

**Lời trình bày:**

Ở biểu đồ mặc định, mỗi mô hình được chấm trên cả hai nguồn rồi lấy trung bình đều. Hai local học CIC đạt khoảng 42 phần trăm F1-macro, hai local học UNSW đạt 46,63 và 44,02 phần trăm. FedAvg DAS đạt 46,89 phần trăm, chỉ hơn local tốt nhất 0,26 điểm, tức gần như ngang nhau. Centralized đạt 60,89 phần trăm. Như vậy, với bốn client, chỉ phối hợp bằng FedAvg chưa đủ để vượt rõ các mô hình local trên chỉ số tổng hợp; lợi ích rõ hơn xuất hiện khi dùng FedProx, em sẽ trình bày ở phần sau. Khi chỉ đánh giá trên nguồn riêng, local có thể tốt hơn. Centralized là một mốc thực nghiệm, không phải cận trên toán học. Có thể đổi nguồn để thấy rõ điều kiện của kết luận.

**Chỉ vào hình:** Xem trung bình trước, so FedAvg DAS với local UNSW #3; rồi chuyển CIC và UNSW để quan sát đảo thứ hạng.

**Chuyển ý:** Ma trận đánh giá chéo giải thích vì sao từng mô hình local có điểm tổng hợp thấp.

**Nếu thầy hỏi:** FedAvg DAS gần như ngang local tốt nhất; em không kết luận FedAvg thắng local trong lượt này.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/das/evaluation_by_dataset.csv; results_modal_multidataset/20261122_235344_298853/main/das/evaluation_by_dataset.csv

## 20 · Local gặp khó khi chuyển sang nguồn chưa học

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Điểm trên miền riêng và khả năng dùng chung trên hai miền là hai mục tiêu khác nhau.

**Mục tiêu:** Đọc sự chênh lệch trong/ngoài miền thay vì chỉ nhìn một số trung bình.

**Nội dung trên slide:**

- Local CIC #1: F1-macro 59,69% trên CIC, 24,45% trên UNSW
- Local UNSW #3: 67,80% trên UNSW, 25,47% trên CIC
- FedAvg DAS: 59,65% / 34,12% trên CIC / UNSW

**Lời trình bày:**

Mỗi hàng là một mô hình, mỗi cột là một nguồn test. Hai local CIC gần như giống nhau, khoảng 59,7 phần trăm trên CIC nhưng chỉ khoảng 24 phần trăm khi chuyển sang UNSW. Hai local UNSW đạt khoảng 67,8 phần trăm trên UNSW và chỉ 20 đến 25 phần trăm trên CIC. Hai client cùng nguồn cho kết quả sát nhau vì dữ liệu được chia phân tầng. FedAvg DAS đạt 59,65 trên CIC nhưng chỉ 34,12 phần trăm trên UNSW: mô hình chung giữ được CIC nhưng chưa học tốt UNSW. Điều này phù hợp với việc local chỉ quan sát một phân phối và, với CIC, còn không có ví dụ OTHER_ATTACK. Em không lấy trung bình các ô trong miền của local để thay cho một checkpoint toàn cục; đó là hệ thống nhiều mô hình chuyên biệt và cần được mô tả riêng.

**Chỉ vào hình:** Chỉ các ô trong miền của local rồi đi ngang sang ô ngoài miền; so hai local cùng nguồn.

**Chuyển ý:** Tiếp theo, em giữ cách học FedAvg và chỉ thay đổi bộ đặc trưng để kiểm tra DAS.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/das/evaluation_by_dataset.csv; results_modal_multidataset/20261122_235344_298853/main/das/evaluation_by_dataset.csv

## 21 · Với 4 client, DAS không nâng F1 tổng hợp

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** F1-macro trung bình giảm từ 50,70% (ALL) xuống 46,89% (DAS), tương đương 3,81 điểm phần trăm.

**Mục tiêu:** Trình bày đúng kết quả đối chứng ALL/DAS, kể cả khi DAS không thắng.

**Nội dung trên slide:**

- CIC: 66,72% → 59,65%, giảm 7,07 điểm phần trăm
- UNSW: 34,67% → 34,12%, gần như không đổi
- Cùng subset và ngân sách; checkpoint được chọn riêng bằng validation

**Lời trình bày:**

Ở đối chứng này, hai nhánh đều dùng FedAvg với bốn client, nhưng ALL có hai mươi ba đầu vào và DAS có mười tám. F1-macro trung bình hai nguồn giảm từ 50,70 xuống 46,89 phần trăm. Khi tách nguồn, CIC giảm khoảng 7,07 điểm phần trăm, còn UNSW gần như không đổi ở mức khoảng 34 phần trăm. Như vậy, trong lượt chạy này, bỏ năm cột liên tục làm mất một phần thông tin hữu ích cho CIC, trong khi không giúp FedAvg học UNSW tốt hơn. Mỗi nhánh được chọn best checkpoint theo cùng quy tắc validation: ALL ở vòng mười ba và DAS ở vòng hai mươi lăm. Kết luận chỉ áp dụng cho cấu hình bốn client và một seed; DAS vẫn cho đầu vào gọn hơn và có ảnh hưởng khác lên báo động giả, em trình bày ở slide sau.

**Chỉ vào hình:** Đọc ba hàng CIC, UNSW và trung bình; chỉ khoảng giảm lớn ở CIC và UNSW gần như đứng yên.

**Chuyển ý:** F1-macro mới chỉ là một góc nhìn; cần kiểm tra nhiệm vụ DoS/DDoS và báo động giả.

**Nếu thầy hỏi:** Ranking và danh sách cột DAS không đổi so với bản trước; thay đổi đến từ cách chia client và quá trình huấn luyện, nên cần nhiều seed để tách hai yếu tố.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/all/evaluation_by_dataset.csv; results_modal_multidataset/20261122_152058_5ec64a/main/das/evaluation_by_dataset.csv

## 22 · DAS giảm F1, đổi lại ít báo động giả hơn

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** So với ALL, DAS có F1-macro và F1 DoS/DDoS thấp hơn, nhưng FAR mọi tấn công giảm.

**Mục tiêu:** Đánh giá DAS theo nhiều chỉ số phù hợp với mục tiêu phát hiện tấn công.

**Nội dung trên slide:**

- F1 DoS/DDoS: 50,26% → 44,98%
- FAR mọi tấn công trên BENIGN: 4,45% → 3,01%
- Kết luận phụ thuộc nhiệm vụ, nguồn và ngưỡng quyết định

**Lời trình bày:**

DAS không tốt hơn trên mọi chỉ số, nhưng cũng không kém trên mọi chỉ số. Ở ngưỡng 0,5 đang cố định, F1 phát hiện riêng nhóm DoS/DDoS trung bình hai nguồn giảm từ 50,26 xuống 44,98 phần trăm. Ngược lại, tỷ lệ báo động giả cho nhiệm vụ mọi tấn công giảm từ 4,45 xuống 3,01 phần trăm, tức DAS ít gán nhầm lưu lượng bình thường là tấn công hơn. Kết luận hợp lý là trong lượt bốn client, DAS tạo biểu diễn gọn hơn và thận trọng hơn, nhưng đánh đổi bằng F1. Nếu ưu tiên phát hiện DoS, ALL đang tốt hơn; nếu ưu tiên hạn chế cảnh báo giả, DAS có lợi thế nhỏ. Cần chọn lại đặc trưng, loss và ngưỡng dựa trên validation theo mục tiêu vận hành.

**Chỉ vào hình:** Chỉ chiều tốt/xấu của từng chỉ số; FAR có mũi tên giảm là tốt và là chỉ số duy nhất DAS thắng.

**Chuyển ý:** Ngoài đầu vào, sự khác biệt trong cập nhật học giữa các client cũng cần được xem xét.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/all/evaluation_by_dataset.csv; results_modal_multidataset/20261122_152058_5ec64a/main/das/evaluation_by_dataset.csv

## 23 · Chung đầu vào chưa làm hai nguồn học giống nhau

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Với FedAvg, validation UNSW kẹt quanh 32% trong khi CIC gần 99%; FedProx kéo UNSW lên 62%.

**Mục tiêu:** Dùng lịch sử thật để đặt vấn đề về tối ưu trong môi trường khác phân phối.

**Nội dung trên slide:**

- FedAvg DAS: best vòng 25, UNSW validation chỉ 16% → 32%
- FedProx: UNSW tăng dần đến 62% ở vòng 30, CIC giữ khoảng 96%
- Khác biệt cập nhật là giả thuyết giải thích, không phải nguyên nhân duy nhất đã chứng minh

**Lời trình bày:**

Biểu đồ hiển thị đủ ba mươi vòng validation, đường CIC và UNSW là trung bình của hai client cùng nguồn. Với FedAvg DAS, CIC đạt gần chín mươi chín phần trăm ngay từ đầu, còn UNSW chỉ tăng từ khoảng mười sáu lên ba mươi hai phần trăm rồi đứng yên; best ở vòng hai mươi lăm. Nhánh ALL cũng có UNSW quanh ba mươi ba phần trăm. Một cách giải thích là phần cập nhật từ hai client CIC và hai client UNSW đi theo hướng khác nhau, và mô hình chung nghiêng về CIC. Khi chuyển sang FedProx, đường UNSW tăng đều đến sáu mươi hai phần trăm ở vòng ba mươi, trong khi CIC chỉ giảm nhẹ. Tuy vậy, đường validation không tự chứng minh nguyên nhân duy nhất; loss, kiến trúc, mất cân bằng và độ lệch train/test cũng có thể góp phần. Lưu ý thêm: validation CIC rất cao nhưng test CIC chỉ khoảng sáu mươi phần trăm, do test CIC lấy từ ngày khác.

**Chỉ vào hình:** Chọn FedAvg DAS để xem khoảng cách CIC/UNSW, rồi chuyển FedProx để thấy đường UNSW đi lên; đây là validation, không phải test theo vòng.

**Chuyển ý:** FedProx, cách học có điểm neo đã giới thiệu ở chương 7, được kiểm chứng trên cùng bộ DAS ở slide tiếp theo.

**Nếu thầy hỏi:** Validation CIC cao hơn test CIC nhiều vì test CIC là ngày thu thập khác; em không dùng validation để suy ra điểm test.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/das/fl/*_rounds.csv; results_modal_multidataset/20261122_152058_5ec64a/main/all/fl/*_rounds.csv

## 24 · FedProx tăng F1-macro, đổi lại DoS-F1 giảm và báo động giả tăng

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** F1-macro trung bình đạt 56,99%, cao hơn FedAvg DAS 10,10 điểm phần trăm, vẫn thấp hơn centralized 3,90 điểm.

**Mục tiêu:** Đọc kết quả cải tiến cùng giới hạn và đánh đổi thay vì chỉ chọn chỉ số thuận lợi.

**Nội dung trên slide:**

- UNSW: 34,12% → 60,91%; CIC: 59,65% → 53,07%
- F1 DoS/DDoS: 44,98% → 36,01%; FAR mọi tấn công: 3,01% → 16,96%
- Best FedProx ở vòng 30 (vòng cuối); một seed nên chưa kết luận ưu thế tổng quát

**Lời trình bày:**

Với cùng bộ DAS và bốn client, FedProx đạt F1-macro trung bình 56,99 phần trăm, cao hơn FedAvg DAS 10,10 điểm phần trăm và là cấu hình FL tốt nhất. Mức này vẫn thấp hơn centralized 60,89 phần trăm khoảng 3,90 điểm. Khi tách nguồn, phần tăng đến gần như hoàn toàn từ UNSW: từ 34,12 lên 60,91 phần trăm, trong khi CIC giảm từ 59,65 xuống 53,07 phần trăm. Đi kèm là hai đánh đổi: F1 phát hiện DoS/DDoS giảm từ 44,98 xuống 36,01 phần trăm, và FAR mọi tấn công tăng từ 3,01 lên 16,96 phần trăm. Best checkpoint rơi đúng vòng ba mươi, vòng cuối, nên có thể mô hình chưa hội tụ hết. Chưa có nhiều seed hoặc một phép so sánh tốc độ cùng GPU, nên em giới hạn kết luận vào các metric dự đoán đã đo.

**Chỉ vào hình:** Đổi chỉ số từ F1-macro sang DoS-F1 rồi FAR; chuyển nguồn CIC/UNSW để thấy phần tăng nằm ở UNSW.

**Chuyển ý:** Các ma trận nhầm lẫn sẽ giúp xem phần sai còn lại nằm ở những lớp nào.

**Nếu thầy hỏi:** Centralized chọn checkpoint ở epoch 1 theo validation; đây là kết quả của quy tắc chọn, cần nhiều seed để biết có ổn định không.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/das/evaluation_by_dataset.csv; results_modal_multidataset/20261122_235344_298853/main/das/evaluation_by_dataset.csv

## 25 · Nhìn vào lỗi để hiểu giới hạn của điểm tổng hợp

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Ma trận nhầm lẫn và recall từng lớp cho biết mô hình đang bỏ sót hay nhầm ở đâu.

**Mục tiêu:** Liên kết kết quả tổng hợp với lỗi cụ thể và phân biệt các quy tắc ra quyết định.

**Nội dung trên slide:**

- Đọc theo hàng nhãn thật, cột nhãn dự đoán
- CIC không có OTHER_ATTACK thật: hàng đó N/A khi chuẩn hóa
- Ma trận argmax không thay thế FAR nhị phân ở ngưỡng 0,5

**Lời trình bày:**

Trong ma trận, mỗi hàng là nhãn thật và mỗi cột là nhãn dự đoán bằng argmax. Có thể chọn số đếm hoặc chuẩn hóa theo hàng để xem recall. Hàng OTHER_ATTACK của CIC không có support nên phải ghi không có mẫu thật, không diễn giải thành recall bằng không. Khi so sánh các checkpoint, cần quan sát cả phần benign bị gán tấn công và phần DOS_DDOS bị nhầm sang lớp khác. Ma trận này dùng argmax, còn FAR mọi tấn công dùng ngưỡng trên một trừ xác suất benign, nên không được lấy tùy tiện một ô ma trận để thay FAR trong bảng nhị phân. Phụ lục giữ thêm tỷ lệ phát hiện theo nhãn gốc để truy vết sâu hơn.

**Chỉ vào hình:** Chọn mô hình và nguồn, đổi số đếm/tỷ lệ hàng, đọc đường chéo và recall bên cạnh.

**Chuyển ý:** Từ toàn bộ pipeline và các đối chứng, em tổng kết những gì bài làm đã đạt được.

**Nguồn:** results_modal_multidataset/*/main/*/confusion.csv; results_modal_multidataset/*/main/*/per_class.csv

## 26 · Đóng góp nằm ở cả pipeline và cách kiểm chứng

**Giai đoạn:** Kết luận & hướng đi · **Trạng thái:** Đang bật

**Thông điệp:** Thống nhất dữ liệu, tổ chức học chung và đo đóng góp của từng lựa chọn bằng đối chứng.

**Mục tiêu:** Tóm tắt đóng góp chính xác, không biến tất cả metric thành một kết luận thắng tuyệt đối.

**Nội dung trên slide:**

- Pipeline hai nguồn, bốn client: chia tập trước fit, lưu tham số và truy vết
- DAS: đầu vào gọn hơn, ít báo động giả hơn nhưng F1 thấp hơn ALL
- FedProx: tốt nhất trong FL (56,99%), còn sau centralized và FAR cao hơn

**Lời trình bày:**

Bài làm xây dựng được một pipeline từ hai nguồn dữ liệu khác cấu trúc, chia cho bốn client, đến mô hình và báo cáo đánh giá chung. Các bước chia tập, fit tham số từ train, lưu schema và kiểm tra hash giúp đối chứng rõ ràng hơn. Về kết quả trong lượt bốn client: FedAvg DAS chỉ ngang local tốt nhất; DAS có F1 thấp hơn ALL nhưng ít báo động giả hơn; FedProx là cấu hình FL tốt nhất với 56,99 phần trăm F1-macro, chủ yếu nhờ cải thiện UNSW, nhưng vẫn sau centralized và đổi lấy FAR cao hơn. Vì vậy, đóng góp là một pipeline có thể kiểm chứng và các bằng chứng trung thực về lợi ích cùng giới hạn của từng lựa chọn, kể cả những chỗ kết quả không như kỳ vọng.

**Chỉ vào hình:** Chỉ ba lớp đóng góp: dữ liệu, đối chứng, kết quả; các mốc F1 có cùng cách tổng hợp nguồn, centralized là nét đứt tham chiếu.

**Chuyển ý:** Phần cuối là những giới hạn cần giữ khi diễn giải và các bước phát triển tiếp theo.

**Nguồn:** data_paper_multi_4c/main/quality_report.json; results_modal_multidataset/20261122_152058_5ec64a/main/*/evaluation_by_dataset.csv; results_modal_multidataset/20261122_235344_298853/main/das/evaluation_by_dataset.csv

## 27 · Từ kết quả thực nghiệm đến bước phát triển tiếp

**Giai đoạn:** Kết luận & hướng đi · **Trạng thái:** Đang bật

**Thông điệp:** Ưu tiên kiểm chứng độ lặp lại và giảm báo động giả trước khi mở rộng kết luận.

**Mục tiêu:** Nêu giới hạn cụ thể và hướng phát triển có liên hệ trực tiếp với vấn đề quan sát.

**Nội dung trên slide:**

- Chạy nhiều seed; thêm vòng cho FedProx vì best rơi vào vòng cuối
- Xem lại DAS khi chia client; chọn ngưỡng / μ trên validation
- Rà soát overlap với test và đánh giá thêm dữ liệu độc lập

**Lời trình bày:**

Kết quả hiện tại còn giới hạn ở một seed, bốn client từ hai nguồn và các subset đánh giá. Chưa có độ biến động giữa các lần chạy hoặc chứng cứ cho nhiều môi trường triển khai thực tế. Hướng đầu tiên là chạy thêm seed để kiểm tra khả năng lặp lại, và tăng số vòng cho FedProx vì best checkpoint rơi vào vòng cuối. Thứ hai, DAS cho F1 thấp hơn ALL trong cấu hình này, nên cần xem lại lựa chọn đặc trưng và mục tiêu loss. Thứ ba, chọn μ và ngưỡng dựa trên validation, với mục tiêu rõ về recall, F1 và mức báo động giả chấp nhận được. Cần rà thêm các vector trùng với test, giữ báo cáo trung thực và bổ sung một tập kiểm tra độc lập. Nếu đi đến triển khai thật, còn phải đánh giá truyền thông, riêng tư và vận hành trên hạ tầng phù hợp. Em kết thúc phần chính tại đây và có các trang phụ lục để trao đổi thêm.

**Chỉ vào hình:** Ghép từng giới hạn với bước kiểm chứng tương ứng; dùng nút phụ lục khi thầy hỏi sâu.

**Chuyển ý:** Em xin trao đổi thêm các câu hỏi; có thể quay lại pipeline hoặc mở phụ lục theo chủ đề.

**Nguồn:** data_paper_multi_4c/main/quality_report.json: independence; configs/multidataset.json: train_seeds; Kết quả main của run 4 client đã chốt

## A1 · Công thức và cách tổng hợp chỉ số

**Giai đoạn:** Phụ lục · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi chỉ số cần đi cùng nhãn dương, quy tắc quyết định và mẫu số.

**Mục tiêu:** Tra cứu công thức khi cần bảo vệ cách đánh giá.

**Nội dung trên slide:**

- Precision, recall, F1, FAR và accuracy
- Macro-present chỉ trung bình lớp có support thật
- Mean nguồn khác metric tính từ predictions pooled

**Lời trình bày:**

Precision đo tỷ lệ dự đoán dương đúng, recall đo tỷ lệ mẫu dương được phát hiện. F1 là trung bình điều hòa của hai đại lượng này. FAR trên benign lấy số mẫu benign bị báo dương chia cho tổng benign, nên với nhiệm vụ DoS không lấy toàn bộ OTHER_ATTACK làm mẫu số benign. F1-macro-present bỏ lớp không có support thật khỏi trung bình, nhưng dự đoán nhầm vào lớp vắng vẫn có thể làm giảm recall của các lớp thật. Trung bình nguồn cho mỗi nguồn một trọng số bằng nhau; pooled tính lại metric sau khi gộp dự đoán. Nếu chỉ số không xác định, bảng ghi N/A thay vì tự gán số không hoặc một.

**Chỉ vào hình:** Đối chiếu nhãn dương và mẫu số trong từng công thức.

**Chuyển ý:** Bảng đầy đủ sau đây cho phép kiểm tra các chỉ số theo từng nguồn.

**Nguồn:** fl_ddos/multidataset_eval.py

## A2 · Bảng kết quả đầy đủ theo nguồn

**Giai đoạn:** Phụ lục · **Trạng thái:** Đang bật

**Thông điệp:** Tám mô hình được đánh giá trên cùng hai test; ghi rõ cách tổng hợp khi xem hàng tổng.

**Mục tiêu:** Cung cấp bảng tra cứu số liệu thay vì chỉ các chỉ số được chọn cho slide chính.

**Nội dung trên slide:**

- Accuracy, F1-macro-present, attack-F1, DoS-F1, recall, FAR, AUC
- Chuyển riêng từng nguồn, mean, worst hoặc pooled
- Checkpoint, seed và validation score được giữ trong snapshot

**Lời trình bày:**

Bảng này gom các metric của tám mô hình từ CSV đánh giá: bốn local, centralized, FedAvg ALL, FedAvg DAS và FedProx DAS. Bộ chọn nguồn có cả mean_over_sources, worst_source và pooled_predictions. Hàng worst không nhất thiết tương ứng một nguồn duy nhất cho mọi chỉ số, vì mỗi metric được lấy cực trị riêng. Các cột attack và DoS dùng nhãn dương khác nhau nên phải đọc đúng tiêu đề. Cột Best của local và centralized là epoch, của FL là vòng. Tất cả kết quả là seed không, checkpoint đã chọn từ validation và test subset năm mươi nghìn mẫu mỗi nguồn. Không có khoảng tin cậy từ nhiều seed trong bảng này.

**Chỉ vào hình:** Chọn nguồn hoặc cách gộp trước khi đọc ngang một hàng mô hình.

**Chuyển ý:** Nếu cần xem các sai khác cụ thể giữa nhãn, chuyển sang ma trận nhầm lẫn.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/*/evaluation_by_dataset.csv; results_modal_multidataset/20261122_235344_298853/main/das/evaluation_by_dataset.csv

## A3 · Ma trận nhầm lẫn và nhãn tấn công gốc

**Giai đoạn:** Phụ lục · **Trạng thái:** Đang bật

**Thông điệp:** Dùng số đếm, tỷ lệ theo hàng và thống kê nhãn gốc để truy vết lỗi.

**Mục tiêu:** Tra cứu lỗi sâu hơn theo lớp chung và nhãn tấn công gốc.

**Nội dung trên slide:**

- Ma trận ba lớp dùng dự đoán argmax
- Tỷ lệ phát hiện theo nhãn gốc không phải phân loại đúng tên loại con
- Lớp không có mẫu thật được ghi N/A

**Lời trình bày:**

Phần trên giữ ma trận ba lớp của mô hình đã chọn. Bên dưới là các nhóm nhãn gốc cùng support và tỷ lệ bị nhận là attack hoặc DoS. Ví dụ một nhãn con CIC được tính tỷ lệ phát hiện tấn công, chứ mô hình ba lớp không dự đoán chính xác tên DNS hay LDAP. Thống kê này giúp xem lỗi tập trung ở nhóm nào mà F1 tổng hợp có thể che đi. Không cộng hoặc lấy trung bình tùy ý các tỷ lệ nhãn gốc để thay cho recall toàn nguồn vì mỗi nhóm có support khác nhau. Các giá trị đều được lấy từ per_original_label.csv của cùng checkpoint.

**Chỉ vào hình:** Phân biệt cột tên nhãn gốc với ba cột dự đoán của mô hình.

**Chuyển ý:** Bảng đặc trưng tiếp theo cung cấp chi tiết của quyết định DAS.

**Nguồn:** results_modal_multidataset/*/main/*/confusion.csv; results_modal_multidataset/*/main/*/per_original_label.csv

## A4 · Toàn bộ bảng lựa chọn đặc trưng

**Giai đoạn:** Phụ lục · **Trạng thái:** Đang bật

**Thông điệp:** Relevance gộp quyết định thứ hạng; relevance từng client là thông tin đối chiếu.

**Mục tiêu:** Có thể giải thích từng cột bị loại và so sánh khác biệt relevance theo client.

**Nội dung trên slide:**

- 17 cột liên tục, 12 được giữ
- Lý do loại: redundancy hoặc relevance thấp
- 6 cột cố định được giữ ngoài danh sách chọn DAS

**Lời trình bày:**

Bảng đầy đủ ghi tên, hạng, relevance gộp, relevance riêng của bốn client và lý do loại. Các quyết định được thực hiện theo relevance gộp và tương quan với cột đã chọn. Một cột có relevance lớn vẫn có thể bị loại nếu trùng thông tin; một cột hữu ích ở một nhóm client có thể có relevance gộp nhỏ. Sáu cột cố định về giao thức và trạng thái duration không nằm trong mười bảy dòng này vì chúng được giữ riêng. Bảng không phải trọng số giải thích của mô hình sau huấn luyện và cũng không chứng minh quan hệ nhân quả giữa đặc trưng với tấn công.

**Chỉ vào hình:** Đọc một dòng giữ và một dòng loại cùng lý do cụ thể.

**Chuyển ý:** Phần nguồn và kiểm tra thí nghiệm giúp truy vết lại các con số.

**Nguồn:** data_paper_multi_4c/main/feature_selection.csv; data_paper_multi_4c/main/features.json

## A5 · Nguồn số liệu và kiểm tra tính nhất quán

**Giai đoạn:** Phụ lục · **Trạng thái:** Đang bật

**Thông điệp:** Hai run completed cùng bundle; ALL và DAS dùng cùng split; mọi con số đều truy được nguồn.

**Mục tiêu:** Giải trình nguồn và giới hạn của tính tái lập.

**Nội dung trên slide:**

- Profile main · seed 0 · bundle bất biến
- Schema, preprocessor, split và checksum nguồn được lưu
- Có vector trùng với test được báo cáo; không khẳng định độc lập tuyệt đối

**Lời trình bày:**

FedAvg ALL, FedAvg DAS, FedProx và bốn local đến từ run 20261122_152058_5ec64a; centralized được chạy riêng trong run 20261122_235344_298853. Cả hai completed và dùng cùng bundle dữ liệu bốn client. ALL và DAS có cùng hash split nhưng khác hash schema và preprocessor theo số cột. Snapshot của bộ trình chiếu lưu đường dẫn và SHA-256 của nguồn đọc để có thể đối chiếu. Báo cáo chất lượng có giao nhóm train/validation bằng không, nhưng vẫn ghi vector trùng với test: điều này cần được công khai và kiểm tra thêm, không tự động chứng minh rò rỉ nhãn. Các job chạy trên GPU A10 hoặc A10G khác nhau, nên dữ liệu hiện có không dùng để kết luận tốc độ tương đối.

**Chỉ vào hình:** Đối chiếu bundle, best round và bảng overlap; mở danh sách checksum khi cần.

**Chuyển ý:** Trang cuối tập hợp các câu hỏi phản biện có thể gặp.

**Nguồn:** data_paper_multi_4c/main/quality_report.json; results_modal_multidataset/20261122_152058_5ec64a/status_snapshot.json; results_modal_multidataset/20261122_235344_298853/status_snapshot.json

## A6 · Trao đổi và câu hỏi phản biện

**Giai đoạn:** Phụ lục · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi câu trả lời phân biệt thiết kế, bằng chứng thực nghiệm và điều chưa kiểm chứng.

**Mục tiêu:** Chuẩn bị trả lời nhất quán với pipeline và số liệu thực tế.

**Nội dung trên slide:**

- Vì sao FL, vì sao DAS, vì sao kiến trúc lai?
- FedProx giải quyết gì và chưa giải quyết gì?
- Kết quả có lặp lại và dùng được trong thực tế chưa?

**Lời trình bày:**

Em chuẩn bị các câu hỏi theo ba nhóm: lựa chọn thiết kế, cách đánh giá và giới hạn kết luận. Với mỗi câu, phần trả lời nêu rõ điều đã thực hiện và bằng chứng hiện có. Chẳng hạn, FL cho phép phối hợp học nhưng chưa có bảo đảm riêng tư tuyệt đối; DAS giảm FAR nhưng F1 thấp hơn ALL trong lượt bốn client; FedProx có số hạng neo trong loss chứ không phải bộ lọc client độc hại. Kiến trúc lai là lựa chọn triển khai theo phương pháp tham khảo, chưa có ablation đầy đủ trên pipeline hai nguồn, bốn client để khẳng định từng khối đều cần thiết. Có thể bấm câu hỏi để mở câu trả lời hoặc quay về đúng giai đoạn trên pipeline.

**Chỉ vào hình:** Mở câu hỏi tương ứng, sau đó dùng liên kết về giai đoạn nếu cần minh họa.

**Chuyển ý:** Cảm ơn thầy đã theo dõi. Em xin tiếp tục trao đổi theo câu hỏi.

**Nguồn:** Mã nguồn pipeline multidataset_v1; Các artifact main đã chốt; https://proceedings.mlr.press/v54/mcmahan17a.html; https://arxiv.org/abs/1812.06127

## Tài liệu phương pháp

- [FedAvg · McMahan et al. (2017)](https://proceedings.mlr.press/v54/mcmahan17a.html)
- [FedProx · Li et al. (2020)](https://arxiv.org/abs/1812.06127)
- [Phương pháp tham khảo · Alshdadi et al. (2025)](https://doi.org/10.3390/fi17020088)
