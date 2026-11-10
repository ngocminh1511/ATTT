# Thuyết trình pipeline học liên kết

Mở **index.html** bằng trình duyệt. File này chứa giao diện, nội dung dành cho người nghe, số liệu và SVG; có thể chép riêng sang máy khác và dùng offline. Không cần server, Node, CDN hay raw dataset để trình chiếu. Kịch bản lời nói chỉ nằm trong **kich_ban.md**.

Trang đầu là pipeline 9 giai đoạn. Bấm một giai đoạn để vào nhóm slide; phần so sánh phương pháp nằm trong giai đoạn 8. Có 33 trang chính (00–32) và 6 trang phụ lục (A1–A6).

Giao diện trình chiếu dùng nền sáng, chữ tối và các hình giải thích lớn. Trang đầu có hình minh họa mạng học liên kết và pipeline SVG với các gói cập nhật chuyển động. Toàn bộ slide chính dùng sơ đồ, ví dụ trực quan hoặc biểu đồ; bảng tham chiếu chi tiết nằm ở phụ lục. Hiệu ứng xuất hiện, đường truyền, bộ lọc và đường học dùng CSS/SVG; tự giảm chuyển động theo thiết lập hệ điều hành.

## Điều khiển

| Thao tác | Phím/nút |
|---|---|
| Slide trước / tiếp | ← / →, PageUp / PageDown |
| Về pipeline | H |
| Bật/tắt toàn màn hình | F |
| Đóng bảng đang mở | Esc |
| Nhảy đến trang bất kỳ | Danh mục |

Trong phần kết quả có menu riêng. Một số biểu đồ có bộ chọn nguồn, chỉ số, mô hình hoặc cách chuẩn hóa. Màn hình chiếu chỉ chứa nội dung dành cho người nghe, không có nút lời nói hoặc khung hướng dẫn thuyết trình. Toàn bộ kịch bản và ghi chú chỉ nằm trong `kich_ban.md` và file nguồn, không nhúng vào HTML.

Các trang schema, đổi đơn vị và forward có nút chọn từng phần của minh họa. Trang FedAvg có bốn bước mô phỏng. Đường validation hiển thị đủ 30 vòng, có thể kéo thanh vòng để đọc điểm CIC, UNSW và trung bình. Biểu đồ ALL/DAS dùng các điểm nối để thấy mức thay đổi theo nguồn. Hình AI ở trang mở đầu là minh họa khái niệm; số liệu biểu đồ vẫn lấy từ snapshot thật.

## Sửa và lược bỏ nội dung

Sửa `src/slides.json`: tiêu đề, thông điệp, các ý ngắn, lời nói (`speech`), vị trí chỉ vào hình (`point`), chuyển ý (`transition`), phản biện (`defense`). Giữ nguyên `id` và `view` nếu không thay kiểu hình minh họa.

Để bỏ qua một slide, đổi `enabled` thành `false`, rồi build lại. Danh mục, trước/tiếp và liên kết giai đoạn tự bỏ qua slide đã tắt. Nếu tắt toàn bộ một giai đoạn, giai đoạn đó không xuất hiện trong điều hướng. Số hiệu gốc của các trang còn lại được giữ để dễ đối chiếu kịch bản.

Từ thư mục gốc dự án:

```powershell
python presentation/build.py
python presentation/build.py --check
```

Build thông thường chỉ cần Python chuẩn và snapshot đi kèm; sinh lại `index.html` dành cho người nghe và `kich_ban.md` dành riêng cho người nói. Các trường lời nói, mục tiêu, chuyển ý và hướng dẫn không được nhúng vào HTML. Không sửa trực tiếp file sinh nếu muốn giữ thay đổi sau lần build tiếp theo.

`src/visuals.js` dựng các hình giải thích; `src/app.js` giữ điều hướng, điều khiển và phần phụ lục. `assets/federated-network.png` được nhúng vào HTML để vẫn mở offline. Prompt và nguồn tạo hình nằm trong `assets/README.md`.

Giai đoạn 1 gồm tổng quan hai bộ dữ liệu, CIC-DDoS2019 và UNSW-NB15. `data/datasets.json` lưu bối cảnh benchmark từ UNB/UNSW cùng thống kê đã kiểm kê trên các file đầu vào: CIC 431.371 dòng / 78 cột; UNSW 175.341 + 82.332 dòng / 45 cột. Phân biệt các số này với quy mô benchmark gốc và subset test của bài. Khi thay phiên bản raw, cập nhật lại kiểm kê trong file này trước khi refresh snapshot.

## Cập nhật số liệu

```powershell
.\.venv\Scripts\python.exe presentation/build.py --refresh-data
```

Chế độ refresh cần artifact dự án và pandas trong môi trường hiện có. Không train lại, không tải dữ liệu, không mở raw dataset. Histogram duration được tái dựng từ AFN của 200.000 mẫu train đã lưu, có sai số float32; nguồn được ghi trên hình. Snapshot chỉ chứa thống kê, metric và metadata phục vụ trình bày, không chứa bản ghi flow.

Hai run cố định: `20261109_161229_a7ff36` (đối chứng) và `20261109_193340_f712a4` (FedProx), profile main, seed 0, cùng bundle. Nếu kết quả hoặc best checkpoint thay đổi, bộ kiểm tra dừng để yêu cầu rà lại diễn giải. Khi chủ động dùng thí nghiệm mới, cập nhật nguồn, mốc kiểm tra và lời nhận xét cùng lúc.

Sơ đồ minh họa không phải dữ liệu đo được luôn có nhãn ví dụ. Các bảng phân biệt F1-macro-present trung bình nguồn, pooled, mọi tấn công và riêng DoS/DDoS. Lớp vắng được ghi N/A. Không dùng thời gian trên GPU khác nhau để kết luận về tốc độ.

## Kiểm tra

```powershell
python presentation/build.py --check
node --check presentation/src/app.js
node presentation/check.cjs
```

`check.cjs` kiểm tra render toàn bộ trang, điều hướng, slide tắt, biểu đồ và snapshot bằng Node; đây không phải kiểm tra bố cục trong trình duyệt. Khi cần phục vụ qua HTTP: `python -m http.server 8765 --directory presentation`, sau đó mở `http://127.0.0.1:8765/`.

Không thay đổi mã chuẩn bị dữ liệu hoặc huấn luyện của dự án. Không có hosting hoặc dịch vụ bên ngoài.
