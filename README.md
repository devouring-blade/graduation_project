# Đồ án tốt nghiệp – Hỏi đáp pháp luật dân sự, hình sự (RAG)

Phạm vi: 4 bộ luật gốc – Dân sự (91/2015/QH13), Tố tụng dân sự (92/2015/QH13),
Hình sự (100/2015/QH13), Tố tụng hình sự (101/2015/QH13) – cùng văn bản sửa đổi và hướng dẫn.

Giả thiết: văn bản trong `data/raw/` đã được kiểm tra thủ công và đúng; code chỉ đọc và xử lý.

## Chạy

```
venv\Scripts\python.exe src\chay.py
```

Xoá `data/processed/` rồi chạy một mạch 5 bước (khoảng 10 giây); bước nào lỗi thì dừng.

| Bước | File | Việc |
| --- | --- | --- |
| 1 | `src/clean/build_goc.py` | Tách 4 bộ luật gốc thành Điều/Khoản/Điểm |
| 2 | `src/clean/build_huong_dan.py` | Tách các văn bản hướng dẫn |
| 3 | `src/clean/doc_lenh.py` (+ `vi_tri.py`) | Đọc câu lệnh trong văn bản sửa đổi |
| 4 | `src/clean/ap_lenh.py` (+ `chunking.py`) | Áp sửa đổi, dựng phiên bản theo thời gian, cắt chunk |
| 5 | `src/clean/lien_ket.py` | Liên kết hướng dẫn ↔ Điều luật, xuất kết quả |

Dùng chung: `html_text.py` (HTML → dòng chữ), `cau_truc.py` (dòng → cây Điều/Khoản/Điểm).

## Kết quả (`data/processed/`)

Đơn vị đưa cho agent là **cả một Điều**; chunk chỉ để tìm kiếm và luôn trỏ về Điều.

| File | Mỗi dòng | Dùng để |
| --- | --- | --- |
| `dieu_luat.jsonl` | Một **Điều luật hoàn chỉnh** (một phiên bản, `valid_from`/`valid_to`) + `huong_dan`: các Điều hướng dẫn liên quan, ghi rõ Khoản/Điểm luật được hướng dẫn và chỗ hướng dẫn | Đưa cho agent |
| `huong_dan.jsonl` | Một **Điều của văn bản hướng dẫn hoàn chỉnh** (một phiên bản) + `huong_dan_cho`: các Điều luật nó hướng dẫn | Đưa cho agent |
| `chunk_luat.jsonl` | Chunk cắt từ Điều luật; `dieu_id` = Điều cha | Tìm kiếm |
| `chunk_huong_dan.jsonl` | Chunk cắt từ hướng dẫn; `dieu_luat` = các Điều luật đoạn này hướng dẫn | Tìm kiếm |
| `van_ban.jsonl` | Thông tin văn bản (tên, loại, ngày hiệu lực, đường dẫn vbpl) | Hiển thị, trích dẫn |
| `thong_ke.json` | Số liệu tổng hợp | |

`trung_gian/` chứa dữ liệu giữa các bước (cây Điều, câu lệnh sửa đổi, phiên bản Điều, nhật ký áp lệnh).

Chunk theo cấu trúc: Điều ngắn (≤ 400 từ) = 1 chunk; Điều dài → mỗi Khoản (kèm tên Điều, câu dẫn
Điều); Khoản dài → mỗi Điểm (kèm tên Điều, câu dẫn Điều, câu dẫn Khoản).

Liên kết hướng dẫn → Điều luật chỉ lấy từ chữ của văn bản (không đoán): đoạn nêu rõ "… Điều 65 của Bộ luật
Hình sự" (`dan_chieu`), hoặc tên văn bản nêu Điều (`trich_yeu`; tên nêu một Điều → mọi đoạn; nêu nhiều Điều →
chỉ đoạn không tự nêu Điều nào).

## Chiến lược truy xuất (thiết kế cho bước tiếp theo)

Đầu vào: câu hỏi, ngày của sự việc (mặc định hôm nay), số Điều cần lấy K.

1. Tìm trên `chunk_luat` và `chunk_huong_dan` (chỉ chunk có hiệu lực tại ngày đó), xếp theo điểm.
2. Lấy dần chunk theo thứ tự điểm và cộng điểm cho **Điều luật**:
   - chunk luật → cộng vào Điều cha (`dieu_id`);
   - chunk hướng dẫn → cộng vào các Điều luật trong `dieu_luat` (có thể nhân hệ số nhỏ hơn).
3. Dừng khi đã có **đủ K Điều luật khác nhau** (không cố định top-k chunk).
4. Lấy K Điều hoàn chỉnh từ `dieu_luat.jsonl` (phiên bản tại ngày đó) kèm các Điều hướng dẫn trong
   `huong_dan` (lọc theo ngày; đọc nguyên văn từ `huong_dan.jsonl`).
5. Agent chọn Điều phù hợp câu hỏi, trả lời dẫn căn cứ Điều luật trước, hướng dẫn sau, kèm trích dẫn
   và đường dẫn vbpl.

## Cấu hình và đầu vào

- `config/van_ban_goc.json` – thông tin 4 bộ luật code không tự đọc được (tên, ngày hiệu lực thực tế, số Điều).
- `config/van_ban_huong_dan.json` – ngày hiệu lực văn bản hướng dẫn không ghi trong văn bản (có nguồn).
- `data/raw/manifest.jsonl` – danh mục văn bản đầu vào; `data/raw/SUA_TAY.jsonl` – các chỗ đã sửa tay trong raw.

## Trạng thái

- 2.425 phiên bản Điều luật (211 có hướng dẫn), 355 phiên bản Điều hướng dẫn (213 có liên kết) từ 31 văn bản;
  3.445 chunk luật, 854 chunk hướng dẫn.
- 464 thao tác sửa đổi đã áp. Chưa áp 4: BLTTHS Điều 333, 454, 496 (mốc chèn xuất hiện nhiều lần);
  NQ 03/2024 Điều 3 khoản 3 (không có cụm cần thay).
- `02/2020/NQ-HĐTP` chưa đưa vào: file thực chất là Thông tư 02/2020/TT-TANDTC, không hướng dẫn 4 bộ luật.
- Chưa làm: liên kết gợi ý (bằng embedding) cho chunk hướng dẫn chưa có liên kết; embedding; truy xuất; benchmark.
