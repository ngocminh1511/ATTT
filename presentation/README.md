# Thuyết trình pipeline học liên kết

Mở **index.html** bằng trình duyệt. File này chứa giao diện, nội dung dành cho người nghe, số liệu và SVG; có thể chép riêng sang máy khác và dùng offline. Không cần server, Node, CDN hay raw dataset để trình chiếu. Kịch bản lời nói chỉ nằm trong **kich_ban.md**.

Bản hiện tại trình bày pipeline **4 client**: CIC-DDoS2019 → client 1, 2; UNSW-NB15 → client 3, 4 (mỗi client 50.000 train / 10.000 validation, chia phân tầng theo nhãn gốc; test giữ theo nguồn). Trang đầu là pipeline 9 giai đoạn. Bấm một giai đoạn để vào nhóm slide; phần so sánh phương pháp nằm trong giai đoạn 8. Có 24 trang (00–23), 8 giai đoạn, không có phụ lục và chương kết luận; ma trận nhầm lẫn nằm trong giai đoạn 8.

Giao diện trình chiếu dùng nền sáng, chữ tối và các hình giải thích lớn. Trang đầu có hình minh họa mạng học liên kết và pipeline SVG với các gói cập nhật chuyển động. Toàn bộ slide chính dùng sơ đồ, ví dụ trực quan hoặc biểu đồ. Hiệu ứng xuất hiện, đường truyền, bộ lọc và đường học dùng CSS/SVG; tự giảm chuyển động theo thiết lập hệ điều hành.

## Điều khiển

| Thao tác | Phím/nút |
|---|---|
| Slide trước / tiếp | ← / →, PageUp / PageDown |
| Về pipeline | H |
| Bật/tắt toàn màn hình | F |
| Đóng bảng đang mở | Esc |
| Nhảy đến trang bất kỳ | Danh mục |

Trong phần kết quả có menu riêng. Một số biểu đồ có bộ chọn nguồn, chỉ số, mô hình hoặc cách chuẩn hóa. Màn hình chiếu chỉ chứa nội dung dành cho người nghe, không có nút lời nói hoặc khung hướng dẫn thuyết trình. Toàn bộ kịch bản và ghi chú chỉ nằm trong `kich_ban.md` và file nguồn, không nhúng vào HTML.

Mỗi slide có tên giai đoạn làm tiêu đề lớn và tiêu đề slide ngắn bên dưới. Chương 1 là một slide hai bộ dữ liệu kèm biểu đồ nhãn; chương 2 dùng bảng gọn Trước → Sau. Trang forward có nút chọn từng phần của minh họa. Trang FedAvg có bốn bước mô phỏng. Đường validation hiển thị đủ 30 vòng, có thể kéo thanh vòng để đọc điểm CIC, UNSW (trung bình hai client cùng nguồn) và trung bình. Biểu đồ ALL/DAS dùng các điểm nối để thấy mức thay đổi theo nguồn. Hình AI ở trang mở đầu là minh họa khái niệm; số liệu biểu đồ vẫn lấy từ snapshot thật.

## Sửa và lược bỏ nội dung

Sửa `src/slides.json`: tiêu đề, thông điệp, các ý ngắn, lời nói (`speech`), vị trí chỉ vào hình (`point`), chuyển ý (`transition`), phản biện (`defense`). Giữ nguyên `id` và `view` nếu không thay kiểu hình minh họa.

Để bỏ qua một slide, đổi `enabled` thành `false`, rồi build lại. Danh mục, trước/tiếp và liên kết giai đoạn tự bỏ qua slide đã tắt. Nếu tắt toàn bộ một giai đoạn, giai đoạn đó không xuất hiện trong điều hướng. Số hiệu gốc của các trang còn lại được giữ để dễ đối chiếu kịch bản.

Từ thư mục gốc dự án:

```powershell
python presentation/build.py
python presentation/build.py --check
```

Build thông thường chỉ cần Python chuẩn và snapshot đi kèm; sinh lại `index.html` dành cho người nghe và `kich_ban.md` dành riêng cho người nói. Các trường lời nói, mục tiêu, chuyển ý và hướng dẫn không được nhúng vào HTML. Không sửa trực tiếp file sinh nếu muốn giữ thay đổi sau lần build tiếp theo.

`src/visuals.js` dựng các hình giải thích; `src/app.js` giữ điều hướng và điều khiển. Trang bìa (slide 00) có thông tin đề tài, GVHD, SVTH, logo `assets/logo-dut.png` (nhúng base64 để mở offline) và hình học liên kết động vẽ bằng SVG (một vòng: gửi mô hình → học cục bộ → gửi trọng số → tổng hợp). Sơ đồ 9 giai đoạn nằm ở slide 01 `pipeline`; phím H quay về slide này. `assets/federated-network.png` không còn được nhúng.

Giai đoạn 1 gồm tổng quan hai bộ dữ liệu, CIC-DDoS2019 và UNSW-NB15. `data/datasets.json` lưu bối cảnh benchmark từ UNB/UNSW cùng thống kê đã kiểm kê trên các file đầu vào: CIC 431.371 dòng / 78 cột; UNSW 175.341 + 82.332 dòng / 45 cột. Phân biệt các số này với quy mô benchmark gốc và subset test của bài. Khi thay phiên bản raw, cập nhật lại kiểm kê trong file này trước khi refresh snapshot.

## Cập nhật số liệu

```powershell
.\.venv\Scripts\python.exe presentation/build.py --refresh-data
```

Chế độ refresh cần artifact dự án và pandas trong môi trường hiện có. Không train lại, không tải dữ liệu, không mở raw dataset. Histogram duration được tái dựng từ AFN của 200.000 mẫu train đã lưu (`client_1..4.parquet`), có sai số float32; nguồn được ghi trên hình. Snapshot chỉ chứa thống kê, metric và metadata phục vụ trình bày, không chứa bản ghi flow.

Dữ liệu chuẩn bị: `data_paper_multi_4c`. Hai run cố định, profile main, seed 0, cùng bundle `1298b6c2…`: `20261122_152058_5ec64a` (FedAvg ALL/DAS, FedProx DAS, 4 local) và `20261122_235344_298853` (centralized DAS, chạy riêng). Tổng cộng 8 mô hình. Nếu kết quả hoặc best checkpoint thay đổi, bộ kiểm tra dừng để yêu cầu rà lại diễn giải. Khi chủ động dùng thí nghiệm mới, cập nhật nguồn, mốc kiểm tra và lời nhận xét cùng lúc.

Sơ đồ minh họa không phải dữ liệu đo được luôn có nhãn ví dụ. Các bảng phân biệt F1-macro-present trung bình nguồn, pooled, mọi tấn công và riêng DoS/DDoS. Lớp vắng được ghi N/A. Không dùng thời gian trên GPU khác nhau để kết luận về tốc độ.

## Kiểm tra

```powershell
python presentation/build.py --check
node --check presentation/src/app.js
node presentation/check.cjs
```

`check.cjs` kiểm tra render toàn bộ trang, điều hướng, slide tắt, biểu đồ và snapshot bằng Node; đây không phải kiểm tra bố cục trong trình duyệt. Khi cần phục vụ qua HTTP: `python -m http.server 8765 --directory presentation`, sau đó mở `http://127.0.0.1:8765/`.

Không thay đổi mã chuẩn bị dữ liệu hoặc huấn luyện của dự án. Không có hosting hoặc dịch vụ bên ngoài.

## Demo trực tiếp hai máy

Demo cũ (`demo.html`) đã bỏ. Demo mới nằm ngoài thư mục này, ở `../demo_live/`:
máy server chạy web có model gác cửa, máy attack bắn lưu lượng theo 3 pha. Xem
[`../demo_live/KICH_BAN_DEMO.md`](../demo_live/KICH_BAN_DEMO.md).
