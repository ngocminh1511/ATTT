# Chương 9 (bản nháp) — Cách xây dựng trang web demo

Kịch bản để bổ sung vào deck. Gồm 1 stage mới (`demo`) + 3 slide. Văn phong và
các trường (message / bullets / goal / speech / point / transition / defense)
khớp với `src/slides.json`. Số liệu lấy từ demo thật trong `../demo_live/`.

> Chèn thật cần: thêm stage thứ 9, nới ràng buộc `len(stages)==8 / len(slides)==24`
> trong `build.py`, và cho 3 slide này một `view` (dùng lại view sẵn có hoặc thêm
> render mới). Phần này làm sau khi anh/chị duyệt nội dung.

---

## Stage mới

```json
{"id":"demo","title":"Demo trực tiếp hai máy","short":"Demo",
 "description":"Web tích hợp model gác cửa và kịch bản tấn công",
 "output":"Thấy mô hình quyết định cho qua / chặn theo thời gian thực"}
```

---

## 9.1 · Demo hai máy: web có model gác cửa

**Giai đoạn:** Demo · **Trạng thái:** Đang bật

**Thông điệp:** Một thiết bị chạy web có mô hình gác cửa, một thiết bị bắn lưu
lượng; mô hình quyết định cho qua hay chặn ngay khi có truy cập.

**Mục tiêu:** Cho thầy thấy mô hình đã huấn luyện được đặt vào một luồng xử lý
thật, không chỉ là bảng số.

**Nội dung trên slide:**

- Máy A (server): web + mô hình ResVGG-SwinNet gác cửa, có dashboard
- Máy B (attack): script bắn 3 pha, chỉ dùng thư viện chuẩn Python
- Hai máy cùng mạng LAN; quyết định ALLOW / BLOCK hiển thị thời gian thực

**Lời trình bày:**

Để kiểm chứng mô hình trong một tình huống gần thực tế, nhóm em dựng một demo
gồm hai thiết bị cùng một mạng. Thiết bị A chạy một trang web, nhưng trước mỗi
truy cập, luồng được đưa qua mô hình ResVGG-SwinNet đã huấn luyện như một lá
chắn: nếu không có dấu hiệu bất thường thì cho vào, nếu có dấu hiệu tấn công thì
từ chối. Thiết bị B đóng vai kẻ tấn công, chạy một kịch bản bắn lưu lượng. Màn
hình bên phải là bảng điều khiển của máy A, đếm số lượt cho qua và số lượt bị
chặn, kèm nhật ký từng truy cập theo thời gian thực. Điểm cần nhấn mạnh: mô hình
ở đây chạy suy luận thật trên từng luồng, không phải kết quả tính sẵn.

**Chỉ vào hình:** Chỉ hai khối máy A và máy B, rồi mũi tên lưu lượng đi từ B sang
A và điểm ra quyết định ở A.

**Chuyển ý:** Vấn đề mấu chốt là mô hình nhận đầu vào gì, nên tiếp theo em giải
thích cách một truy cập được đưa vào mô hình.

**Phòng thủ:** Demo là IDS mô phỏng ở mức ứng dụng, không phải thiết bị chặn gói
inline; mục tiêu là minh họa mô hình ra quyết định, không phải đo throughput.

**Nguồn:** demo_live/May_server/serve.py; demo_live/May_attack/attack.py

---

## 9.2 · Từ một truy cập đến quyết định của mô hình

**Giai đoạn:** Demo · **Trạng thái:** Đang bật

**Thông điệp:** Mỗi truy cập được quy thành một flow 8 trường, chuẩn hóa đúng
scaler đã học, rồi mô hình phân loại: BENIGN thì cho qua, tấn công thì chặn 403.

**Mục tiêu:** Làm rõ mô hình không đọc gói thô mà đọc đặc trưng flow, và vì sao
demo phát lại flow thật từ tập test.

**Nội dung trên slide:**

- Request → 1 flow 8 trường → chuẩn hóa (log1p + AFN) → mô hình → ALLOW/BLOCK
- Dùng checkpoint FedProx μ=0,1 của run 4 client (đổi được sang FedAvg DAS)
- Đặc trưng lấy từ flow thật trong tập test, không tự đo gói tại chỗ

**Lời trình bày:**

Mô hình của nhóm không đọc gói tin thô, mà đọc tám trường đặc trưng của một flow,
chính là tám trường chung đã chuẩn hóa ở các chương trước. Vì vậy, khi một truy
cập đến, máy A quy nó thành một flow, chuẩn hóa bằng đúng các tham số đã học trên
train, rồi đưa qua mô hình. Mô hình cho ba xác suất; nếu lớp cao nhất là bình
thường thì trả trang web với mã hai trăm, còn nếu là DoS/DDoS hoặc tấn công khác
thì từ chối với mã bốn linh ba. Một lựa chọn quan trọng để demo trung thực: thay
vì tự đo đặc trưng tại chỗ, vốn cho phân phối lệch với dữ liệu huấn luyện, nhóm
em phát lại các flow có thật trong tập test. Nhờ đó kết quả demo tái lập đúng
năng lực mô hình đã báo cáo, chứ không phụ thuộc may rủi của việc bắt gói.

**Chỉ vào hình:** Đi theo chuỗi mũi tên request → flow → chuẩn hóa → mô hình →
quyết định; dừng ở nhánh rẽ ALLOW và BLOCK.

**Chuyển ý:** Với cơ chế này, em cho chạy ba pha tấn công để xem lá chắn phản ứng
ra sao.

**Phòng thủ:** Dữ liệu không rời máy theo nghĩa demo chỉ truyền nhãn loại và đọc
kết quả; mô hình chạy cục bộ trên máy A, đúng tinh thần học liên kết.

**Nguồn:** demo_live/KICH_BAN_DEMO.md; fl_ddos/multidataset_eval.py

---

## 9.3 · Ba pha tấn công và điều quan sát được

**Giai đoạn:** Demo · **Trạng thái:** Đang bật

**Thông điệp:** Lưu lượng bình thường được cho qua, tấn công UNSW bị chặn tốt;
DDoS của CIC còn bị bỏ sót nhiều, đúng như phần đánh giá đã chỉ ra.

**Mục tiêu:** Dùng demo để xác nhận lại cả điểm mạnh lẫn giới hạn của mô hình một
cách trung thực.

**Nội dung trên slide:**

- Pha benign → cho qua ~86% · Pha DoS UNSW → chặn ~88% · Pha OTHER UNSW → chặn ~81%
- Pha DoS CIC → chỉ chặn ~40%: đúng điểm yếu đã phân tích ở chương 8
- Dashboard cập nhật số cho qua / chặn theo thời gian thực

**Lời trình bày:**

Kịch bản gồm ba pha. Pha một là truy cập bình thường, tốc độ như người dùng
thật, và lá chắn cho qua khoảng tám mươi sáu phần trăm. Pha hai là tấn công
DoS/DDoS: với nguồn UNSW, mô hình chặn khoảng tám mươi tám phần trăm; với pha ba
là các tấn công khác của UNSW cũng chặn khoảng tám mươi mốt phần trăm. Tuy nhiên,
khi bắn DDoS lấy từ CIC, mô hình chỉ chặn được khoảng bốn mươi phần trăm, phần
lớn bị nhận nhầm là bình thường. Đây không phải lỗi demo mà đúng là giới hạn đã
thấy ở chương tám: khi ép hai nguồn về tám trường chung, các đặc trưng phân biệt
DDoS của CIC bị mất, nên ở mức một flow, DDoS phản xạ trông giống một flow nhỏ
bình thường. Em để nguyên quan sát này trong demo để phần trình bày nhất quán
giữa bảng số và thực nghiệm, và nêu đây là hướng cải thiện: dò lại ngưỡng theo
validation và giữ thêm đặc trưng riêng cho từng nguồn.

**Chỉ vào hình:** Chỉ hai ô đếm cho qua và chặn khi chạy từng pha, rồi nhấn vào
chênh lệch giữa pha UNSW và pha CIC.

**Chuyển ý:** Như vậy demo vừa cho thấy mô hình hoạt động được trong luồng thật,
vừa phơi bày đúng giới hạn để làm việc tiếp.

**Phòng thủ:** Số chặn phụ thuộc ngưỡng 50% và cấu hình 4 client, một seed; demo
phát lại mẫu test nên phản ánh đúng chỉ số đã báo cáo, không tối ưu riêng cho
buổi trình bày.

**Nguồn:** demo_live/KICH_BAN_DEMO.md (mục 3 — số đo thật); results_modal_multidataset
