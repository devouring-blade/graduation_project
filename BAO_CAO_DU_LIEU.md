# Báo cáo: thu thập dữ liệu và thiết kế corpus pháp luật dân sự – hình sự

Ngày lập: 17/11/2026. Thư mục dự án: `E:\Work_Space\graduation_project`.

Báo cáo này ghi lại toàn bộ những gì đã làm, dữ liệu đang có, các quyết định đã chốt và
những việc còn lại, để có thể tự làm tiếp mà không cần đọc lại cuộc trao đổi.

---

## 1. Tóm tắt trong 5 dòng

1. Đề tài: hệ thống hỏi đáp pháp luật (RAG) cho lĩnh vực **dân sự và hình sự**, có hiểu
   luật thay đổi theo thời gian.
2. Phạm vi đã chốt: **4 bộ luật gốc** – Dân sự, Tố tụng dân sự, Hình sự, Tố tụng hình sự –
   cùng văn bản sửa đổi và văn bản hướng dẫn của chúng.
3. Đã xong lớp **raw**: 56 văn bản HTML tải từ vbpl.vn, chia 5 nhóm, có file kiểm kê và mã băm.
4. Đã thiết kế xong lớp **clean** (cắt chunk, ghép sửa đổi, liên kết hướng dẫn) và đã chạy
   thử một phiên bản code; code đó đã bị xóa khi chốt lại phạm vi, cần viết lại theo thiết kế
   ở mục 6.
5. Chưa làm: đánh chỉ mục (embedding), truy xuất, trả lời, benchmark.

---

## 2. Cấu trúc thư mục hiện tại

```
E:\Work_Space\graduation_project\
├── BAO_CAO_DU_LIEU.md      ← báo cáo này
├── README.md               ← giới thiệu ngắn
├── venv\                   ← môi trường Python 3.13 (không nộp)
└── data\
    └── raw\
        ├── goc\            4 file
        ├── huong_dan\     32 file
        ├── sua_doi\        7 file
        ├── lien_quan\     11 file
        ├── doi_chieu\      2 file HTML (+2 file JSON đi kèm)
        ├── manifest.jsonl  56 dòng, mỗi dòng một văn bản
        └── README.md       mô tả lớp raw
```

Dung lượng: khoảng 11,6 MB HTML.

---

## 3. Quá trình thu thập dữ liệu

### 3.1. Nguồn

Toàn bộ văn bản lấy từ **Cơ sở dữ liệu quốc gia về pháp luật – vbpl.vn**. Không thu thập tự
động từ các trang thương mại (Thư viện pháp luật, LuatVietnam, aitracuuluat…).

### 3.2. Bước tìm văn bản (discovery)

1. Bắt đầu từ các luật gốc.
2. Trên vbpl.vn, trang mỗi luật có mục văn bản liên quan, trong đó vbpl tự liệt kê văn bản
   **sửa đổi** và văn bản **hướng dẫn** luật đó. Lấy toàn bộ danh sách này, cùng kết quả tìm
   theo tiêu đề và số hiệu.
3. Phân loại tự động thành GIỮ / XEM XÉT / LOẠI theo quy tắc: loại văn bản địa phương
   (UBND, HĐND); loại nghị quyết Hội đồng Thẩm phán ban hành trước 2016 (hướng dẫn luật cũ);
   loại văn bản đã hết hiệu lực; biểu mẫu và xử phạt hành chính để "xem xét".
4. Văn bản GIỮ được tải về. Thư mục kết quả của bước này đã xóa sau khi chốt danh sách.

### 3.3. Cách tải

vbpl.vn là ứng dụng Next.js; toàn văn nằm sẵn trong dữ liệu trang dưới dạng HTML có gắn
class `prov-part`, `prov-chapter`, `prov-section`, `prov-article`, `prov-clause`,
`prov-item`. Toàn văn được đọc thẳng từ dữ liệu đó qua trình duyệt, không cào màn hình.

| Cách lấy (`nguon_noi_dung` trong manifest) | Số văn bản | Ghi chú |
| --- | --- | --- |
| `rsc_html` – HTML có sẵn trong dữ liệu trang | 47 | Cách chính |
| `rendered_panel` – lưu khung "Nội dung" sau khi trang hiển thị | 5 | Trang không có HTML trong dữ liệu |
| Chuyển từ file Word bằng pandoc | 2 | 105/2025/QH15, 04/2025/NQ-HĐTP – vbpl không có HTML; file Word gốc đã xóa nên HTML là bản duy nhất, không có url |
| Lấy lại từ bản làm trước | 2 | 2 văn bản hợp nhất trong `doi_chieu/` |

Mọi văn bản được quy về **một định dạng duy nhất là HTML**, giữ nguyên như nguồn trả về,
không sửa chữ nào.

### 3.4. Quá trình thu hẹp phạm vi

| Thời điểm | Số văn bản | Thay đổi |
| --- | --- | --- |
| 15/11/2026 | 107 | Tải về theo phạm vi 7 luật gốc (thêm HNGĐ, Đất đai, Nhà ở) + 10 văn bản từ bản làm trước |
| 16/11/2026 | 97 | Bỏ 10 văn bản ngoài phạm vi |
| 16/11/2026 | 78 | Chốt **4 bộ luật gốc**; xóa 19 văn bản hướng dẫn Đất đai, Nhà ở, HNGĐ |
| 16/11/2026 | **56** | Xóa 22 văn bản không sửa gì vào 4 bộ luật gốc (gồm Luật Đất đai, Nhà ở, HNGĐ và các luật khác mảng) |

Lý do chốt 4 bộ luật: tiêu chí rõ ràng, nói được trong một câu – *"hai bộ luật nội dung và
hai bộ luật tố tụng của lĩnh vực dân sự và hình sự"* – không còn trường hợp lưng chừng.

---

## 4. Dữ liệu đang có (56 văn bản)

### 4.1. Năm nhóm và vai trò

| Thư mục | Số | Vai trò | Vào corpus? |
| --- | --- | --- | --- |
| `goc/` | 4 | 4 bộ luật gốc | **Có** |
| `huong_dan/` | 32 | Giải thích cách áp dụng 4 bộ luật gốc | **Có** |
| `sua_doi/` | 7 | Chỉ chứa câu lệnh sửa văn bản khác | Không – nội dung được ghép vào văn bản bị sửa |
| `lien_quan/` | 11 | Luật khác có một Điều sửa 4 bộ luật gốc | Không – chỉ lấy Điều sửa đổi đó |
| `doi_chieu/` | 2 | Văn bản hợp nhất chính thức | Không – dùng để kiểm tra kết quả ghép |

**Vì sao văn bản sửa đổi không vào corpus?** Nó chỉ gồm câu lệnh kiểu *"Sửa đổi khoản 3
Điều 40 như sau…"*, đọc riêng không hiểu. Nội dung của nó được ghép vào luật gốc thành
phiên bản mới của Điều, và phiên bản đó mới vào corpus.

**Vì sao có nhóm `lien_quan`?** Ở Việt Nam, một luật mới có thể sửa luật khác cùng cấp. Cuối
luật mới thường có Điều *"Sửa đổi, bổ sung một số điều của các luật có liên quan"*. Ví dụ
Luật Tư pháp người chưa thành niên, Điều 177, khoản 1 điểm a: **"Bãi bỏ chương XII"** Bộ luật
Hình sự (chương về người dưới 18 tuổi phạm tội), có hiệu lực 01/01/2026.

### 4.2. Danh sách

**goc/ (4)**

| Số hiệu | Tên | Số Điều | Hiệu lực |
| --- | --- | --- | --- |
| 91/2015/QH13 | Bộ luật Dân sự | 689 | 01/01/2017 |
| 92/2015/QH13 | Bộ luật Tố tụng dân sự | 517 | 01/07/2016 |
| 100/2015/QH13 | Bộ luật Hình sự | 426 | 01/07/2016 |
| 101/2015/QH13 | Bộ luật Tố tụng hình sự | 510 | 01/07/2016 |

**sua_doi/ (7)**

| Số hiệu | Sửa văn bản nào |
| --- | --- |
| 12/2017/QH14 | Bộ luật Hình sự |
| 86/2025/QH15 | Bộ luật Hình sự (hiệu lực 01/07/2025) |
| 02/2021/QH15 | Bộ luật Tố tụng hình sự |
| 99/2025/QH15 | Bộ luật Tố tụng hình sự |
| 85/2025/QH15 | Bộ luật Tố tụng dân sự và 4 luật khác |
| 01/2022/NQ-HĐTP | Nghị quyết 02/2018/NQ-HĐTP (án treo) |
| 02/2025/NQ-HĐTP | Một số nghị quyết của Hội đồng Thẩm phán |

**lien_quan/ (11)** – mỗi luật có Điều sửa bộ luật gốc

| Số hiệu | Tên | Sửa |
| --- | --- | --- |
| 59/2024/QH15 | Luật Tư pháp người chưa thành niên | BLHS (bãi bỏ Chương XII), BLTTHS |
| 34/2024/QH15 | Luật Tổ chức Tòa án nhân dân | BLTTDS, BLTTHS |
| 106/2025/QH15 | Luật Thi hành án dân sự | BLTTHS |
| 128/2025/QH15 | Luật Thi hành tạm giữ, tạm giam và cấm đi khỏi nơi cư trú | BLTTHS (Điều 123) |
| 103/2025/QH15 | Luật Tương trợ tư pháp về hình sự | BLTTHS |
| 105/2025/QH15 | Luật Giám định tư pháp | BLTTHS (khoản 1 Điều 136) |
| 13/2022/QH15 | Luật Phòng, chống bạo lực gia đình | BLTTDS (Điều 135) |
| 19/2023/QH15 | Luật Bảo vệ quyền lợi người tiêu dùng | BLTTDS |
| 46/2024/QH15 | Luật Công chứng | BLTTDS (khoản 1 Điều 398) |
| 45/2019/QH14 | Bộ luật Lao động | BLTTDS (Điều 32) |
| 59/2020/QH14 | Luật Doanh nghiệp | BLTTDS |

**huong_dan/ (32)**

- Mảng hình sự (23): Nghị quyết HĐTP 01/2016, 01/2018 (tha tù trước hạn), 01/2021 (cho vay
  nặng lãi), 02/2018 (án treo), 02/2019 (mua bán người), 02/2024 (Điều 313), 03/2019 (rửa
  tiền), 03/2020 (tham nhũng), 03/2022 (Điều 304–308), 03/2024 (thời hiệu thi hành án),
  03/2025 (chuyển tử hình thành chung thân), 04/2024 (thủy sản), 04/2025 (tình tiết giảm
  nhẹ, tăng nặng), 05/2018 (động vật hoang dã), 05/2019 (bảo hiểm), 06/2019 (xâm hại tình
  dục người dưới 18 tuổi), 07/2019 (Điều 299, 300); Thông tư liên tịch 01/2021, 02/2018,
  04/2026; Nghị quyết 110/2015/QH13 (thi hành BLTTHS); Nghị quyết 08/2021/NQ-UBTVQH15
  (giải thích Điều 289).
- Mảng dân sự (9): Nghị quyết HĐTP 01/2019 (lãi suất), 01/2020 (tài sản chung dòng họ),
  02/2016, 02/2020 (hòa giải, đối thoại), 02/2022 (bồi thường ngoài hợp đồng), 03/2018 (nợ
  xấu), 04/2016 (gửi, nhận đơn kiện, tống đạt), 04/2017 (trả lại đơn kiện); Nghị quyết
  103/2015/QH13 (thi hành BLTTDS); Nghị định 21/2021/NĐ-CP (bảo đảm thực hiện nghĩa vụ).

**doi_chieu/ (2)**: 105/VBHN-VPQH (Luật Tư pháp người chưa thành niên hợp nhất),
02/VBHN-TANDTC (Nghị quyết 02/2018 về án treo hợp nhất).

### 4.3. Kiểm tra đầy đủ của văn bản sửa đổi

Các văn bản ban hành sau thường ghi ở phần căn cứ *"Bộ luật … đã được sửa đổi, bổ sung theo
Luật số …"*. Gom các danh sách này lại và so với kho:

| Bộ luật | Các văn bản đã sửa (theo căn cứ) | Có đủ trong kho? |
| --- | --- | --- |
| Tố tụng dân sự | 45/2019, 59/2020, 13/2022, 19/2023, 34/2024, 46/2024, 85/2025 | Đủ |
| Tố tụng hình sự | 02/2021, 34/2024, 59/2024, 99/2025, 103/2025 (+105, 106, 128/2025) | Đủ |
| Hình sự | 12/2017, 59/2024, 86/2025 | Đủ |
| Dân sự | Không có – Bộ luật Dân sự 2015 chưa từng bị sửa | – |

Giới hạn: cách kiểm này không phát hiện văn bản sửa đổi quá mới mà chưa văn bản nào trong
kho nhắc tới. Nên mở trang 4 bộ luật trên vbpl.vn xem mục văn bản sửa đổi một lần.

### 4.4. File kiểm kê `manifest.jsonl`

Mỗi dòng một văn bản. Đường dẫn trong `file` tính từ thư mục `data\`.

| Trường | Ý nghĩa | Ví dụ |
| --- | --- | --- |
| `so_hieu` | Số hiệu, dùng làm khóa | 01/2016/NQ-HĐTP |
| `file` | Đường dẫn file HTML | raw/huong_dan/01_2016_NQ-HĐTP.html |
| `nhom` | Nhóm (trùng tên thư mục) | huong_dan |
| `sha256`, `bytes` | Mã băm và kích thước, để phát hiện file bị đổi | c796b308… |
| `nguon_noi_dung` | Cách lấy nội dung (mục 3.3) | rsc_html |
| `url`, `vbpl_id`, `tieu_de_trang` | Trang gốc trên vbpl | https://vbpl.vn/van-ban/chi-tiet/vb--121223 |
| `fetched_at` | Thời điểm tải | 2026-11-15T10:22:54Z |
| `n_dieu` | Số thẻ `prov-article` đếm được – **không tin được**, xem mục 7 | 8 |

Kiểm tra ngày 17/11/2026: 56 dòng, mỗi dòng trỏ tới file có thật, mã băm khớp 56/56.

---

## 5. Kết quả chạy thử của phiên bản code đầu tiên (đã xóa)

Trước khi thu hẹp phạm vi, đã viết và chạy một bộ code 6 bước (đọc thông tin văn bản → tách
Điều → đọc câu lệnh sửa đổi → dựng phiên bản → liên kết hướng dẫn → cắt chunk). Code đã xóa,
nhưng các kết quả sau chứng minh cách làm khả thi và có thể trích vào luận văn:

- Tách đúng số Điều của cả 4 bộ luật (689 / 517 / 426 / 510), kiểm tra bằng tiêu đề "Điều N."
- Số câu lệnh sửa đổi áp được: Bộ luật Hình sự 343, Tố tụng hình sự 94, Tố tụng dân sự 57.
- Bất biến "một Điều không có hai phiên bản cùng hiệu lực tại một thời điểm": **đạt** trên
  toàn bộ dữ liệu.
- Đối chiếu với bản hợp nhất chính thức 105/VBHN-VPQH: 166/179 Điều giống từng chữ, 176/179
  giống về từ ngữ ≥ 98%.
- Ví dụ thật – Điều 40 Bộ luật Hình sự (Tử hình) có 2 phiên bản:

| | Phiên bản 1 | Phiên bản 2 |
| --- | --- | --- |
| Áp dụng | 01/07/2016 – 30/06/2025 | 01/07/2025 – nay |
| Khoản 3 điểm c | Người bị kết án tử hình về tội tham ô, nhận hối lộ đã nộp lại ít nhất 3/4 tài sản… | Người mắc bệnh ung thư giai đoạn cuối |
| Do | Bộ luật Hình sự 2015 | + Luật 86/2025/QH15, Điều 1 khoản 1 |

Lưu ý: các con số trên tính trên phạm vi cũ (7 luật), chưa phải số liệu cuối cùng.

---

## 6. Thiết kế lớp clean đã chốt (cần viết lại code)

### 6.1. Thứ tự làm

| Phần | Đầu vào | Việc | Đầu ra |
| --- | --- | --- | --- |
| 1 | `goc/` | Tách Điều/Khoản/Điểm, cắt chunk chữ gốc | chunk luật gốc, `valid_to` trống |
| 2 | `sua_doi/`, `lien_quan/` | Đọc câu lệnh sửa, áp vào luật gốc theo ngày hiệu lực | phiên bản mới của các chunk bị sửa |
| 3 | `huong_dan/` | Cắt chunk hướng dẫn, ghép sửa đổi của chính nó, nối với Điều luật gốc | chunk hướng dẫn + liên kết 2 chiều |
| 4 | `doi_chieu/` | Kiểm tra | báo cáo đối chiếu, danh sách cần duyệt |

### 6.2. Quy tắc cắt chunk (theo cấu trúc, không theo số chữ)

- Điều ngắn (dưới ngưỡng, ví dụ 400 từ): cả Điều là 1 chunk.
- Điều dài: **mỗi Khoản là 1 chunk**, không gom nhiều Khoản theo độ dài.
- Khoản quá dài: cắt tiếp theo Điểm.
- Mã chunk theo cấu trúc, ví dụ `100/2015/QH13#D40`, `91/2015/QH13#D3#K12`.
- Mỗi chunk có dòng đầu ghi tên văn bản và tên Điều; lặp lại đoạn dẫn của Điều nếu có.
- **Không ghi ngày vào chữ của chunk**; ngày chỉ nằm ở trường `valid_from`, `valid_to`.

Lý do: nếu gom Khoản theo độ dài, sửa một Khoản dài ra hay ngắn đi sẽ làm dịch ranh giới mọi
chunk phía sau, sinh hàng loạt chunk mới không cần thiết. Cắt theo cấu trúc thì sửa Khoản
nào chỉ sinh lại đúng chunk Khoản đó.

### 6.3. Phiên bản theo thời gian

- Không bao giờ sửa đè. Khi một chunk bị sửa: đóng chunk cũ (`valid_to` = ngày sửa đổi có
  hiệu lực), thêm chunk mới (`valid_from` = ngày đó, `valid_to` trống).
- Chunk không đổi chữ (so mã băm) thì giữ nguyên, không tạo bản trùng.
- Khoảng hiệu lực nửa mở `[valid_from, valid_to)`; `valid_to` trống = đang áp dụng.
- Bất biến phải kiểm: mỗi chunk tại một ngày chỉ có đúng một phiên bản.
- Truy vấn theo luật hiện hành: lọc `valid_to` trống. Truy vấn về sự việc năm X: lọc phiên
  bản có khoảng hiệu lực chứa năm X.

### 6.4. Đọc câu lệnh sửa đổi

Câu lệnh theo mẫu soạn thảo thống nhất. Các dạng cần xử lý:

| Dạng | Ví dụ |
| --- | --- |
| Sửa (thay nội dung) | "Sửa đổi, bổ sung khoản 3 Điều 40 như sau: “…”" |
| Bổ sung | "Bổ sung Điều 46a vào sau Điều 46 như sau: “…”" |
| Bãi bỏ Điều/Khoản/Điểm | "Bãi bỏ điểm đ khoản 1 Điều 39" |
| **Bãi bỏ cả Chương** | "Bãi bỏ chương XII" (Luật 59/2024) – code cũ chưa xử lý |
| Thay / bỏ / chèn cụm từ | "Thay thế cụm từ “A” bằng cụm từ “B” tại khoản 1 Điều 5" |
| Đổi tên Điều | "Sửa đổi tên Điều 12 như sau" |

Quy trình: tên Điều trong văn bản sửa đổi cho biết **luật nào** bị sửa ("…của Bộ luật Hình
sự") → khoản/điểm cho biết **chỗ nào** ("khoản 3 Điều 40") → câu hiệu lực của văn bản sửa
đổi cho biết **từ ngày nào** → thay vào luật gốc. Câu nào không hiểu chắc thì đưa vào danh
sách cần duyệt, không đoán.

### 6.5. Văn bản hướng dẫn và cách truy xuất (đã chốt)

- Chunk hướng dẫn có trường `huong_dan_cho` (Điều luật gốc nó hướng dẫn); chunk luật gốc có
  `huong_dan_boi` (các Điều hướng dẫn nó). Lấy bằng cách dò cụm "Điều N của Bộ luật …"; nếu
  không ghi tên luật thì lấy theo tên văn bản hướng dẫn.
- Mỗi liên kết có trạng thái: **khớp** / **viết cho bản cũ** (Điều bị sửa sau khi hướng dẫn
  ra đời, vd. NQ 01/2016 với Điều 40 sau 2025) / **không xác định** (vd. "Điều 1. Phạm vi
  điều chỉnh").
- Truy xuất "luật trước, hướng dẫn sau":
  1. Tìm Điều luật gốc trước (lọc theo loại văn bản). Nếu chunk hướng dẫn trúng, truy ngược
     `huong_dan_cho` để kéo Điều luật cha về.
  2. Từ mỗi Điều tìm được, lấy tối đa vài chunk hướng dẫn còn hiệu lực qua `huong_dan_boi`.
  3. Gom thành cụm, đưa cho mô hình theo thứ tự luật trước, hướng dẫn sau:
     ```
     [BLHS Điều 65 – Án treo]                 ← căn cứ gốc
        └─ NQ 02/2018 Điều 2 – Điều kiện hưởng án treo
        └─ NQ 02/2018 Điều 3 – Không cho hưởng án treo
     ```
  4. Công cụ cho mô hình: `search_law(query)`, `get_guidance(article_id)`, tùy chọn
     `search_all(query)`. System prompt: mọi câu trả lời phải dẫn căn cứ từ luật gốc; hướng
     dẫn chỉ dùng để chi tiết hóa.
- Để benchmark lặp lại được, cần thêm một đường chạy cố định không dùng tool (luôn: tìm luật
  → mở rộng hướng dẫn → gom cụm).

### 6.6. Không nạp lại văn bản đã nạp

Mỗi phần giữ một **sổ ghi** (registry): đầu vào, mã băm đầu vào, phiên bản code, đầu ra.
Chạy lại thì đơn vị nào mã băm và phiên bản code không đổi được bỏ qua.

| Phần | Mã băm đầu vào |
| --- | --- |
| Tách văn bản, đọc sửa đổi, đọc hướng dẫn | sha256 của file HTML (đã có trong manifest) |
| Dựng phiên bản | mã băm Điều gốc + mã băm mọi câu lệnh sửa Điều đó |
| Cắt chunk | mã băm nội dung phiên bản + danh sách hướng dẫn |
| Embedding | mã băm chữ của chunk |

Thêm văn bản sửa Điều 51 Bộ luật Hình sự thì chỉ Điều 51 được dựng lại và embed lại. Đổi code
một phần thì tăng số phiên bản code, phần đó và các phần sau làm lại. Văn bản bị xóa khỏi raw
thì xóa đầu ra của nó. Có tùy chọn `--force` để làm lại tất cả.

### 6.7. Quy tắc mở rộng / cập nhật

- Phạm vi cố định ở 4 bộ luật. Chỉ nhận: (1) văn bản sửa 4 bộ luật, (2) văn bản hướng dẫn
  4 bộ luật, (3) văn bản sửa hoặc thay thế văn bản hướng dẫn đã có.
- Văn bản không nối được với bộ luật gốc nào thì không nạp, đưa vào danh sách chờ duyệt.
- Cập nhật do người kích hoạt (tải file, bỏ vào đúng thư mục, thêm dòng manifest, chạy lại),
  không làm bộ tự quét liên tục.
- Benchmark chạy trên một bản dữ liệu đóng băng, ghi rõ ngày.
- Thử nghiệm trình diễn cho luận văn: chạy khi chưa có Luật 86/2025 → hỏi Điều 40 ra bản
  2015; thêm Luật 86/2025, chạy lại → chỉ các Điều bị sửa được xử lý, câu trả lời đổi sang
  bản mới.

---

## 7. Lưu ý kỹ thuật khi viết lại code

- Thư viện cần: `beautifulsoup4`, `lxml`. Đọc file bằng UTF-8, chuẩn hóa Unicode NFC.
- Đọc HTML: chỉ lấy các khối lá (`p`, `div`, `td`…) để không lặp chữ; thẻ `<br>` là xuống
  dòng thật (các điểm a), b) trong đoạn sửa đổi thường nằm chung một `<p>` ngăn bằng `<br>`).
- **Không dựa vào class `prov-*`**: tách Điều theo chữ "Điều N." vì:
  - Bộ luật Dân sự có 753 thẻ `prov-article` cho 689 Điều; dòng có `data-merged="true"` là
    phần nối của dòng trước (tên Chương/Mục bị tách dòng) → gộp vào dòng trước.
  - Một số file không có class nào (văn bản chuyển từ Word, 128/2025, 13/2022, 45/2019).
- vbpl đôi khi chèn khoảng trắng vào số: "Điều 1 4 ." → "Điều 14."; "năm 20 25" → "2025".
- "Điều N" chỉ là Điều mới khi số không nhỏ hơn Điều trước và dòng không nằm trong ngoặc kép
  (nội dung trong ngoặc kép là đoạn sửa đổi của văn bản khác).
- Khoản "N." phải đúng thứ tự 1, 2, 3…; điểm phải đúng thứ tự a, b, c, d, đ, e, g, h, i, k…
- Hai Nghị quyết 103/2015 và 110/2015 viết "Điều 1" không có dấu chấm.
- Ngày hiệu lực: tìm câu "<Loại> này có hiệu lực [thi hành] [kể] từ ngày …"; bỏ qua câu nằm
  trong ngoặc kép; xử lý "từ ngày ký" và "từ ngày <văn bản khác> có hiệu lực".
- Phần cuối văn bản (Nơi nhận, chữ ký, Phụ lục) phải tách khỏi Điều cuối.
- Trường `n_dieu` trong manifest không dùng được để kiểm tra.

---

## 7b. Kết quả Clean – Phần 1 (17/11/2026)

Code: `src/clean/` (`build_goc.py` là điểm chạy). Đầu ra trong `data/processed/`:

| File | Nội dung |
| --- | --- |
| `van_ban.jsonl` | 4 dòng – thông tin văn bản, gồm `ngay_hieu_luc` (thực tế) và `ngay_hieu_luc_ghi_trong_vb` |
| `dieu.jsonl` | 2.142 dòng – mỗi dòng một phiên bản Điều, giữ cây `doan_dan` / `khoan[].diem[]` / `doan_sau`, vị trí Phần/Chương/Mục/Tiểu mục |
| `chunks.jsonl` | 3.170 chunk – `text` (đem embed, có dòng đầu tên văn bản – Chương – Điều), `noi_dung` (chữ gốc), `trich_dan`, `valid_from`/`valid_to`, `huong_dan_boi`/`huong_dan_cho` (trống) |
| `canh_bao.jsonl` | 10 cảnh báo, mỗi dòng có `trang_thai`: tu_dong_sua 5, da_bo_sung 2, xac_nhan_khong_loi 1, da_xac_minh 2; còn mở 0 |
| `thong_ke.json` | số liệu + kết quả kiểm tra |

| Bộ luật | Điều | Khoản | Điểm | Chunk (Điều / Khoản / Điểm) | Hiệu lực dùng |
| --- | --- | --- | --- | --- | --- |
| BLDS 91/2015 | 689 | 1.418 | 312 | 703 (686 / 17 / 0) | 01/01/2017 |
| BLTTDS 92/2015 | 517 | 1.362 | 712 | 782 (468 / 254 / 60) | 01/07/2016 |
| BLHS 100/2015 | 426 | 1.397 | 2.946 | 881 (321 / 518 / 42) | 01/01/2018 |
| BLTTHS 101/2015 | 510 | 1.331 | 992 | 804 (455 / 253 / 96) | 01/01/2018 |

Độ dài chunk (số từ, gồm dòng đầu): nhỏ nhất 32, trung vị 138, p95 350, lớn nhất 545.

Kiểm tra tự động (đạt hết): số Điều đúng và liên tục 1..N; mã băm file khớp manifest; mọi dòng
nội dung của Điều có mặt trong ít nhất một chunk; không trùng `phien_ban_id`; không chunk rỗng;
mỗi chunk/Điều chỉ một phiên bản tại một ngày.

Phát hiện thêm khi viết code:
- `data-merged="true"` không chỉ đánh dấu tên Chương bị tách dòng mà đôi khi cả dòng nội dung
  (Điều 682 BLDS) → không gộp theo thuộc tính này; nối tên Chương/Mục theo chữ.
- BLTTHS đánh số "Mục I"; BLDS có cấp "Tiểu mục"; tên Chương/Mục dài có thể chiếm 2 dòng.
- **Lỗi nguồn vbpl** (ghi trong `canh_bao.jsonl`, mỗi dòng có `trang_thai`):
  - BLHS Điều 251 và 252, khoản 3: **mất điểm a, b, c** → **đã bổ sung** (xem dưới).
  - BLHS Điều 278 khoản 2: không có điểm đ → **xác nhận không phải lỗi**: bản luatvietnam cũng
    không có; hai nguồn độc lập giống nhau.
  - BLHS Điều 142, 175, 243, 397: hai Điểm dính trên một dòng → code tự tách (`tu_dong_sua`).
  - BLTTDS Điều 162: "1 Trường hợp…" thiếu dấu chấm → code nhận là Khoản 1 (`tu_dong_sua`).
- **Ngày hiệu lực – đã xác minh** bằng văn bản gốc (lưu ở `data/bo_sung_tay/*.doc`):
  NQ 144/2016/QH13 Điều 1 khoản 2 lùi hiệu lực BLHS và BLTTHS từ 01/07/2016; NQ 41/2017/QH14
  Điều 1 khoản 1: từ 01/01/2018 có hiệu lực "Bộ luật Hình sự số 100/2015/QH13 đã được sửa đổi,
  bổ sung một số điều theo Luật số 12/2017/QH14" và BLTTHS 101/2015/QH13.
  Ví dụ Điều 40 ở mục 5 vì thế bắt đầu từ 01/01/2018, không phải 01/07/2016.
  - Ngoại lệ chưa mô hình hóa: NQ 144/2016 Điều 1 khoản 4 – từ 01/07/2016 đã áp dụng các quy
    định có lợi cho người phạm tội (khoản 3 Điều 7 BLHS 2015).
  - **Hệ quả cho Phần 2**: BLHS bắt đầu có hiệu lực ở dạng đã sửa theo Luật 12/2017. Các Điều
    bị Luật 12/2017 sửa chưa bao giờ được áp dụng ở dạng nguyên bản 2015 → khi ghép, phiên bản
    gốc của chúng có khoảng hiệu lực rỗng; phiên bản 12/2017 bắt đầu từ 01/01/2018.

### Bổ sung tay (`config/bo_sung_tay.json`)

Nguyên tắc: không sửa `data/raw`; chữ bổ sung **không chép vào config** mà code đọc thẳng từ file
bằng chứng `data/bo_sung_tay/luatvietnam_BLHS_D251_D252_D278.txt` (người dùng chép từ
luatvietnam.vn ngày 17/11/2026, đã bỏ 2 dòng quảng cáo). Mỗi Điểm chèn vào có trường
`nguon_bo_sung`; Điều có trường `bo_sung_tay`. Build báo lỗi nếu vbpl đã có Điểm đó, nếu các
Điểm vbpl có sẵn khác bằng chứng, hoặc nếu sau bổ sung vẫn còn thiếu.

Đối chiếu trước khi nhận nguồn:
- Mọi đơn vị (tên, Khoản, Điểm) vbpl có của Điều 251 (40), 252 (48), 278 (27) trùng từng chữ với
  luatvietnam; khác duy nhất "phá hủy" (vbpl) / "phá huỷ" (luatvietnam) ở Điều 278 – giữ vbpl.
- Bản luatvietnam là **bản gốc 2015**, không phải bản sửa theo Luật 12/2017 (khoản 68, 69, 90
  của Luật 12/2017 sửa đúng 3 Điều này): bản 12/2017 viết "Heroine, Cocaine, … hoặc XLR-11",
  "từ 10 năm đến 15 năm", Điều 278 có 5 khoản; luatvietnam viết như vbpl gốc.

Phát hiện cho Phần 2 (chưa xử lý): văn bản 12/2017 trên vbpl có lỗi chữ "Quà/Quá thuốc phiện",
"1)" thay cho "l)" (khoản 2 Điều 252), và khoản 4 Điều 252 (bản sửa) không có điểm e.

## 8. Việc còn lại

| Việc | Trạng thái |
| --- | --- |
| Raw | Xong |
| Clean – phần 1: cắt chunk 4 bộ luật gốc | **Xong** (mục 7b), không còn cảnh báo mở |
| Clean – phần 2: ghép sửa đổi (gồm bãi bỏ Chương) | Đã thiết kế, cần viết code |
| Clean – phần 3: hướng dẫn + liên kết 2 chiều | Đã thiết kế, cần viết code |
| Clean – phần 4: kiểm tra với 2 văn bản hợp nhất | Đã thiết kế |
| Chọn mô hình embedding | Chưa – đề xuất `BAAI/bge-m3` (tiếng Việt tốt, đọc đoạn dài) |
| Đánh chỉ mục: vector + từ khóa (BM25) | Chưa |
| Truy xuất "luật trước, hướng dẫn sau", lọc theo ngày | Đã thiết kế |
| Benchmark | Chưa – soạn khoảng 100 câu hỏi có đáp án là Điều nào; so sánh (A) chỉ luật + liên kết, (B) trộn chung, (C) kết hợp |

## 9. Hạn chế đã biết của dữ liệu

1. Văn bản sửa đổi và hướng dẫn mới nhất chưa đối chiếu lại với trang vbpl của 4 bộ luật.
2. 2 văn bản chuyển từ Word không có url nguồn; không kiểm chứng được với bản gốc.
3. Dữ liệu đúng tại thời điểm tải (15/11/2026).
4. Văn bản hướng dẫn chưa theo dõi được thời điểm hết hiệu lực (khi bị văn bản mới thay thế).
