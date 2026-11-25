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

## 05 · Mỗi nguồn dữ liệu chia cho hai client

**Giai đoạn:** Phân chia dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** CIC và UNSW vẫn tách riêng; trong mỗi nguồn, train và validation chia đều cho hai client theo nhãn gốc.

**Mục tiêu:** Làm rõ ranh giới dữ liệu, cách chia bốn client và tổ chức mô phỏng federated learning.

**Nội dung trên slide:**

- Client 1, 2 · partition 0, 1 · CIC-DDoS2019
- Client 3, 4 · partition 2, 3 · UNSW-NB15
- Mỗi client 50.000 train / 10.000 validation; test giữ theo nguồn

**Lời trình bày:**

Bản hiện tại dùng bốn client. Hai client đầu, partition 0 và 1, giữ dữ liệu CIC; hai client sau, partition 2 và 3, giữ dữ liệu UNSW. Trong mỗi nguồn, train và validation được chia đều cho hai client bằng cách phân tầng theo nhãn gốc, xếp vòng với seed cố định, nên mỗi client có năm mươi nghìn mẫu train và mười nghìn mẫu validation với tỷ lệ nhãn gần như nhau. Như vậy hai client cùng nguồn gần IID với nhau, còn khác biệt lớn vẫn nằm giữa CIC và UNSW: loại tấn công, tỷ lệ lớp và cách đo flow. Server kiểm tra nhận đủ bốn phản hồi đúng PID ở mỗi vòng. Test không chia theo client mà giữ theo nguồn, và cùng một checkpoint toàn cục được chấm trên hai test. Các client chạy trên cùng hạ tầng mô phỏng; hình mô tả tổ chức logic, không khẳng định cách ly vật lý.

**Chỉ vào hình:** Chỉ hai khối nguồn, mỗi khối hai client với số mẫu bằng nhau; dữ liệu không đi qua mũi tên cập nhật mô hình.

**Chuyển ý:** Bên trong mỗi nguồn, trước khi chia client, em tách dữ liệu học, chọn mô hình và kiểm tra cuối cùng.

**Nếu thầy hỏi:** Chia hai client trong cùng nguồn làm tăng số bên tham gia nhưng không tạo thêm khác biệt phân phối; khác biệt chính vẫn là giữa hai nguồn.

**Nguồn:** configs/multidataset.json: clients, client_split; fl_ddos/multidataset_prep.py: chia client phân tầng; data_paper_multi_4c/main/dataset_manifest.json; fl_ddos/multidataset_server.py: pid_map

## 06 · Chia tập trước mọi bước học tham số

**Giai đoạn:** Phân chia dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Test giữ riêng theo nguồn; train/validation được phân tầng theo nhóm fingerprint.

**Mục tiêu:** Hiểu quy tắc tách tập và giới hạn của kiểm tra độc lập dữ liệu.

**Nội dung trên slide:**

- Test CIC theo nhóm file/ngày khác; UNSW dùng testing-set có sẵn
- Train/val: StratifiedGroupKFold, 5 fold, seed 42
- Cùng fingerprint không nằm ở cả train và validation

**Lời trình bày:**

Test được giữ riêng từ đầu theo quy ước nguồn: CIC dùng hai nhóm file tương ứng các ngày khác nhau, còn UNSW dùng tập testing đã cung cấp. Phần pool còn lại được chia train và validation bằng StratifiedGroupKFold. Fingerprint được tạo từ vector đo gốc, không dùng nhãn hoặc ID; các dòng cùng fingerprint nằm cùng nhóm nên không đi sang hai phía train và validation. Hệ thống chọn fold validation có đủ lớp có mặt trong nguồn. Báo cáo hiện tại xác nhận không có nhóm giao nhau giữa train và validation. Tuy vậy, vẫn có vector trùng với test được báo cáo riêng; không được kết luận toàn bộ train/test hoàn toàn không trùng chỉ từ phép kiểm tra train/validation.

**Chỉ vào hình:** Chỉ test tách trước, năm fold, và hai mẫu cùng màu luôn ở cùng phía.

**Chuyển ý:** Sau khi chia, em giới hạn số mẫu và kiểm soát độ đại diện của từng lớp.

**Nếu thầy hỏi:** Không nói chia ngẫu nhiên 80/20 cho toàn bộ dữ liệu; quota cuối cùng còn thay đổi số mẫu từng tập.

**Nguồn:** fl_ddos/multidataset_prep.py: split_train_val, build_splits, independence_checks

## 07 · Lấy subset có kiểm soát, không nhân bản mẫu

**Giai đoạn:** Phân chia dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi nguồn dùng 100.000 train, 20.000 validation và 50.000 test trong bản main.

**Mục tiêu:** Phân biệt lấy mẫu, cân bằng bằng loss và sinh thêm mẫu.

**Nội dung trên slide:**

- Train: đặt sàn lớp rồi phân bổ phần ngân sách còn lại
- Val/test: quota theo tỷ lệ lớp tự nhiên của nguồn
- UNSW DoS chỉ có 9.811 mẫu train thật: giữ toàn bộ

**Lời trình bày:**

Chính sách lấy mẫu hiện tại đặt sàn mười nghìn mẫu cho mỗi lớp có mặt trong train, sau đó phân bổ ngân sách còn lại theo số lượng gốc. UNSW chỉ có 9.811 mẫu DoS trong phần train khả dụng nên hệ thống giữ toàn bộ và ghi cảnh báo, không nhân bản để đạt sàn. Validation và test giữ tỷ lệ lớp của nguồn, đồng thời bảo đảm support tối thiểu khi có đủ mẫu thật. Với lần chuẩn bị này, mỗi nguồn đạt một trăm nghìn train, hai mươi nghìn validation và năm mươi nghìn test. Sau đó phần train và validation của mỗi nguồn mới được chia đôi cho hai client, mỗi client năm mươi nghìn train và mười nghìn validation. Đây là các subset, không phải toàn bộ benchmark. Mất cân bằng còn lại được phản ánh trong class weight ở bước huấn luyện.

**Chỉ vào hình:** Đọc hàng UNSW DOS_DDOS và tổng mẫu từng cột; nhấn mạnh không có augmentation.

**Chuyển ý:** Từ các trường cơ sở của những mẫu đã chọn, em xây dựng vector đặc trưng.

**Nguồn:** data_paper_multi_4c/main/sampling_report.md; fl_ddos/multidataset_sampling.py

## 08 · Tám trường cơ sở tạo thành 23 cột đầu vào

**Giai đoạn:** Xây dựng đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** Bổ sung tốc độ, tỷ lệ và kích thước gói để biểu diễn flow từ nhiều góc độ.

**Mục tiêu:** Cho thấy nguồn gốc từng nhóm đặc trưng và tách cột cố định khỏi cột được DAS lọc.

**Nội dung trên slide:**

- 17 cột liên tục: lượng, tốc độ, tỷ lệ, kích thước và IAT
- 4 cột one-hot giao thức
- 2 cờ duration_missing và duration_zero

**Lời trình bày:**

Tám trường canonical chưa phải vector cuối cùng. Từ số gói và byte theo hai chiều, hệ thống tạo tổng số gói, tổng byte, tốc độ theo giây, kích thước gói trung bình và các tỷ lệ theo chiều. Kết quả có mười bảy cột liên tục. Giao thức được one-hot thành bốn cột, và hai cờ bổ sung cho biết duration bị thiếu hoặc bằng không. Sáu cột cố định này không được DAS chọn lọc như nhóm liên tục. Những phép tạo đặc trưng là phép tính theo từng dòng và không học tham số từ validation hoặc test. Thứ tự cột được lưu trong metadata để mọi client và checkpoint dùng cùng một vector.

**Chỉ vào hình:** Theo sơ đồ 8 → 17 + 6 → 23, chỉ các nhóm đặc trưng có chung nguồn đo.

**Chuyển ý:** Một ví dụ số sẽ làm rõ cách các đặc trưng mới được tính.

**Nguồn:** fl_ddos/multidataset_prep.py: CONTINUOUS, FIXED, derive

## 09 · Một flow, nhiều cách nhìn về hành vi mạng

**Giai đoạn:** Xây dựng đặc trưng · **Trạng thái:** Đang bật

**Thông điệp:** Ví dụ minh họa giúp kiểm tra ý nghĩa phép tính và các trường hợp mẫu số không hợp lệ.

**Mục tiêu:** Giải thích công thức bằng dữ liệu giả định và cách xử lý missing.

**Nội dung trên slide:**

- Ví dụ: duration 2 s, 8 gói đi, 2 gói về
- Tổng 10 gói → 5 gói/s
- Duration = 0: rate không xác định, cờ duration_zero = 1

**Lời trình bày:**

Em dùng một flow giả định để minh họa, không phải mẫu đo của thí nghiệm. Flow kéo dài hai giây, có tám gói đi, hai gói về, tám trăm byte đi và bốn trăm byte về. Tổng là mười gói và một nghìn hai trăm byte, nên tốc độ là năm gói mỗi giây và sáu trăm byte mỗi giây. Kích thước gói đi trung bình là một trăm byte, tỷ lệ gói về là hai mươi phần trăm. Nếu thời lượng bằng không, tốc độ không được coi là không mà là thiếu, đồng thời duration_zero được bật. Nếu số gói một chiều bằng không, kích thước trung bình chiều đó cũng không xác định. Nút chuyển ví dụ cho thấy những trường hợp này.

**Chỉ vào hình:** Bấm lần lượt flow hợp lệ, duration bằng 0 và chiều về không có gói.

**Chuyển ý:** Các giá trị tính được vẫn có thể rất khác thang đo, nên cần bước chuẩn hóa.

**Nguồn:** fl_ddos/multidataset_prep.py: derive; Ví dụ giả định, không dùng làm số liệu kết quả

## 10 · log1p nén đuôi lớn của giá trị

**Giai đoạn:** Chuẩn hóa dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Biến đổi ln(1 + x) giữ thứ tự giá trị không âm và giảm khoảng cách ở vùng rất lớn.

**Mục tiêu:** Giải thích tác dụng log1p và cho thấy sự thay đổi phân bố trên dữ liệu train.

**Nội dung trên slide:**

- Ví dụ: 0 → 0; 999 → 6,91; 999.999 → 13,82
- Giá trị không hữu hạn hoặc âm được coi là missing
- Histogram lấy từ 200.000 mẫu train đã chọn

**Lời trình bày:**

Các đặc trưng mạng thường có nhiều giá trị nhỏ nhưng một số flow rất lớn. Hàm log1p đưa giá trị không âm x về log tự nhiên của một cộng x, nhờ vậy những chênh lệch lớn được nén lại. Các con số bên trái là ví dụ toán học. Hai histogram bên phải mô tả duration của hai trăm nghìn mẫu train đã chọn. Do artifact lưu dữ liệu sau AFN, phân bố trước và sau log được tái dựng bằng tham số chuẩn hóa đã lưu; có sai số float32 và được ghi rõ trên hình. Hình này không lấy từ test và không được xem là kết quả cải thiện của mô hình. Sau log, em tiếp tục z-score theo giao thức.

**Chỉ vào hình:** So sánh trục ngang và mức tập trung của hai histogram; mỗi hình dùng miền giá trị riêng.

**Chuyển ý:** log1p nén giá trị lớn, còn AFN đưa các nhóm giao thức về thang thống kê phù hợp.

**Nguồn:** fl_ddos/multidataset_prep.py: log1p_valid; data_paper_multi_4c/main/prep_params.json và train client_1..4.parquet

## 11 · AFN học thống kê từ train theo giao thức

**Giai đoạn:** Chuẩn hóa dữ liệu · **Trạng thái:** Đang bật

**Thông điệp:** Bốn client góp thống kê để có mean/std chung; validation và test chỉ áp dụng lại.

**Mục tiêu:** Mô tả chuẩn hóa liên kết và ranh giới fit/transform.

**Nội dung trên slide:**

- Client tính số quan sát, tổng và tổng bình phương hợp lệ
- Gộp thống kê theo TCP / UDP / ICMP / OTHER
- Missing sau z-score → 0; nhóm thiếu dùng thống kê train dự phòng

**Lời trình bày:**

AFN chuẩn hóa từng đặc trưng sau log theo nhóm giao thức. Mỗi client tính số quan sát hợp lệ, tổng và tổng bình phương cho từng nhóm. Việc gộp các thống kê này cho phép tính mean và độ lệch chuẩn chung mà không cần gửi toàn bộ dòng dữ liệu trong thiết kế thuật toán. Các phép tính hiện được mô phỏng từ artifact train. Một giá trị z được tính bằng x trừ mean rồi chia scale. Nếu độ lệch chuẩn gần không, scale dùng một; nếu thiếu thống kê nhóm, dùng tham số train toàn cục dự phòng. Missing được đưa về không sau z-score. Mọi tham số được cố định trước khi biến đổi validation và test.

**Chỉ vào hình:** Chỉ mũi tên thống kê, công thức z-score, và khóa fit chỉ trên train.

**Chuyển ý:** Khi các giá trị đã chuẩn hóa, em lựa chọn phần thông tin cần đưa vào mô hình.

**Nếu thầy hỏi:** Không có secure aggregation hoặc differential privacy trong thí nghiệm này; việc gửi thống kê không tự bảo đảm riêng tư tuyệt đối.

**Nguồn:** fl_ddos/multidataset_prep.py: afn_stats, aggregate_afn, apply_afn

## 12 · DAS giữ thông tin liên quan, lọc phần dư thừa

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

## 13 · Từ tiêu chí đến quyết định giữ hoặc loại

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

## 14 · ALL và DAS khác nhau ở bộ đầu vào

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

## 15 · ResVGG-SwinNet học trên biểu diễn của flow

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Một lớp Linear chiếu vector đặc trưng thành lưới 8×8 trước các khối ResNet, VGG và Swin.

**Mục tiêu:** Hiểu vai trò kiến trúc và tránh nhầm dữ liệu flow là ảnh gốc.

**Nội dung trên slide:**

- ResNet: học đặc trưng với đường nối tắt
- VGG: hai lớp convolution 3×3
- Swin: attention cửa sổ thường và cửa sổ dịch

**Lời trình bày:**

Mô hình nhận vector mười tám hoặc hai mươi ba đặc trưng tùy cấu hình. Một lớp Linear học phép chiếu thành sáu mươi tư giá trị rồi sắp thành lưới tám nhân tám. Lưới này không phải ảnh lưu lượng có sẵn; đây là biểu diễn do mô hình học. Phần ResNet có hai residual block để trích xuất với đường nối tắt. Hai lớp convolution kiểu VGG tiếp tục biến đổi biểu diễn, sau đó hai Swin block học quan hệ trong cửa sổ thường và cửa sổ dịch. Cuối cùng lấy trung bình token và dùng đầu Linear để tạo ba logits. Kiến trúc được triển khai theo hướng tham khảo paper, không khẳng định tái hiện tuyệt đối mọi chi tiết chưa được paper mô tả.

**Chỉ vào hình:** Theo mũi tên qua các khối; nhấn mạnh chữ “lưới học được” tại 8×8.

**Chuyển ý:** Một lượt forward cho thấy chính xác hình dạng dữ liệu qua từng thành phần.

**Nguồn:** fl_ddos/models.py: ResVGGSwinNet

## 16 · Theo dõi một lượt forward

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Kích thước dữ liệu thay đổi có chủ đích; đầu ra mô hình là logits, chưa phải xác suất.

**Mục tiêu:** Có thể giải thích cách đưa dữ liệu bảng vào kiến trúc và tính xác suất đầu ra.

**Nội dung trên slide:**

- B×F → B×1×8×8 → B×32×8×8 → B×64×8×8
- 64 token, mỗi token 64 chiều → pooling → B×3
- Softmax được dùng trong loss hoặc khi dự đoán

**Lời trình bày:**

Với batch có B flow và F đặc trưng, đầu vào có hình dạng B nhân F. Sau lớp chiếu và reshape, dữ liệu thành B nhân một nhân tám nhân tám. Phần ResNet tạo ba mươi hai kênh, phần VGG tăng lên sáu mươi bốn kênh mà vẫn giữ lưới tám nhân tám. Khi chuyển sang Swin, sáu mươi tư vị trí trở thành sáu mươi tư token. Trung bình token tạo một vector sáu mươi bốn chiều cho mỗi flow, rồi đầu phân loại xuất ba logits. CrossEntropyLoss nhận logits trực tiếp; lúc đánh giá mới chuyển sang xác suất softmax. Dự đoán ba lớp dùng argmax, còn các nhiệm vụ nhị phân dùng điểm xác suất và ngưỡng riêng.

**Chỉ vào hình:** Đọc dãy kích thước trên sơ đồ và chỉ vị trí softmax nằm ngoài forward.

**Chuyển ý:** Cùng một kiến trúc được dùng trong các cách tổ chức huấn luyện khác nhau.

**Nguồn:** fl_ddos/models.py: ResVGGSwinNet.forward; fl_ddos/task.py: train, predict

## 17 · Local, centralized và FL tổ chức việc học ra sao?

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

**Nguồn:** baselines/multidataset_baselines.py; fl_ddos/multidataset_server.py; https://proceedings.mlr.press/v54/mcmahan17a.html

## 18 · Một vòng FedAvg: gửi, học, nhận, tổng hợp

**Giai đoạn:** Xây dựng & huấn luyện · **Trạng thái:** Đang bật

**Thông điệp:** Cả bốn client tham gia mỗi vòng; server gộp trọng số theo số mẫu train.

**Mục tiêu:** Mô tả vòng lặp và phân biệt trọng số client với trọng số lớp trong loss.

**Nội dung trên slide:**

- 30 vòng × 5 epoch cục bộ; Adam, lr 0,001
- Batch 64, dropout 0,3, weighted cross-entropy
- 50.000 mẫu/client → trọng số tổng hợp 25% mỗi client

**Lời trình bày:**

Đầu vòng, server gửi cùng một mô hình toàn cục đến bốn client. Mỗi client huấn luyện năm epoch trên train của mình, sử dụng Adam và loss có trọng số lớp. Sau đó client gửi trọng số cùng số mẫu, server kiểm tra đủ bốn PID và tổng hợp theo số mẫu thực. Vì bốn client cùng có năm mươi nghìn mẫu train, hệ số ở phép trung bình là một phần tư cho mỗi client; tính theo nguồn thì CIC và UNSW vẫn mỗi bên một nửa. Đây là trọng số tổng hợp mô hình, khác với class weight trong loss. Quy trình lặp ba mươi vòng; sau mỗi lần tổng hợp, mô hình được đánh giá trên validation của bốn client và điểm chọn mô hình là trung bình theo nguồn. Các nút trên hình lần lượt mở từng bước để dễ theo dõi luồng.

**Chỉ vào hình:** Bấm các bước 1–4; đọc công thức FedAvg và phân biệt với bảng class weight.

**Chuyển ý:** Để so sánh công bằng, em cố định ma trận thí nghiệm và quy tắc chọn checkpoint.

**Nguồn:** fl_ddos/multidataset_server.py; fl_ddos/task.py: train; configs/multidataset.json: fl

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

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/status_snapshot.json; results_modal_multidataset/20261122_235344_298853/status_snapshot.json; baselines/multidataset_baselines.py

## 20 · Ba câu hỏi đánh giá, ba cách đọc kết quả

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

## 21 · Học liên kết chỉ vượt local rõ rệt khi dùng FedProx

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

## 22 · Local gặp khó khi chuyển sang nguồn chưa học

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

## 23 · Với 4 client, DAS không nâng F1 tổng hợp

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

## 24 · DAS giảm F1, đổi lại ít báo động giả hơn

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

## 25 · Chung đầu vào chưa làm hai nguồn học giống nhau

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

**Chuyển ý:** FedProx bổ sung một ràng buộc để client không đi quá xa mô hình chung đầu vòng.

**Nếu thầy hỏi:** Validation CIC cao hơn test CIC nhiều vì test CIC là ngày thu thập khác; em không dùng validation để suy ra điểm test.

**Nguồn:** results_modal_multidataset/20261122_152058_5ec64a/main/das/fl/*_rounds.csv; results_modal_multidataset/20261122_152058_5ec64a/main/all/fl/*_rounds.csv

## 26 · FedProx thêm một điểm neo cho quá trình học cục bộ

**Giai đoạn:** Đánh giá kết quả · **Trạng thái:** Đang bật

**Thông điệp:** Client tối ưu loss dữ liệu cộng μ/2 · ‖w − w_global‖²; server vẫn tổng hợp theo FedAvg.

**Mục tiêu:** Hiểu chính xác vị trí và tác dụng mong muốn của số hạng proximal.

**Nội dung trên slide:**

- Mốc tham chiếu là trọng số toàn cục ở đầu mỗi vòng
- μ = 0 trở về loss cục bộ của cấu hình FedAvg
- Thí nghiệm dùng μ = 0,1; không phải cơ chế chống đầu độc

**Lời trình bày:**

FedProx thay đổi mục tiêu học tại client bằng cách cộng một số hạng phạt khoảng cách bình phương từ trọng số hiện tại đến mô hình toàn cục đầu vòng. Client vẫn muốn giảm lỗi trên dữ liệu riêng, đồng thời phải trả chi phí khi đi quá xa điểm khởi đầu chung. Khi μ bằng không thì không còn số hạng này. Trong thử nghiệm, μ là 0,1 và server vẫn dùng phép trung bình có trọng số như FedAvg. Ràng buộc này nhằm xử lý khó khăn tối ưu với dữ liệu không đồng nhất, nhưng không loại bỏ khác biệt miền và không tự bảo đảm chống client độc hại. Tác dụng cuối cùng vẫn phải đọc từ kết quả và các đánh đổi.

**Chỉ vào hình:** Chỉ hai thành phần loss và sơ đồ điểm neo; hình hướng cập nhật chỉ là minh họa.

**Chuyển ý:** Giữ nguyên bộ DAS, em so sánh kết quả FedProx với FedAvg và centralized.

**Nguồn:** fl_ddos/task.py: train; fl_ddos/multidataset_server.py; https://arxiv.org/abs/1812.06127

## 27 · FedProx tăng F1-macro, đổi lại DoS-F1 giảm và báo động giả tăng

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

## 28 · Nhìn vào lỗi để hiểu giới hạn của điểm tổng hợp

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

## 29 · Đóng góp nằm ở cả pipeline và cách kiểm chứng

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

## 30 · Từ kết quả thực nghiệm đến bước phát triển tiếp

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
