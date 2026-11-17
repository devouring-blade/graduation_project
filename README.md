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

| File | Nội dung | Dùng để |
| --- | --- | --- |
| `corpus_luat.jsonl` | Chunk Điều luật, có `valid_from`/`valid_to` | **Tìm kiếm** |
| `corpus_huong_dan.jsonl` | Chunk văn bản hướng dẫn | Tìm phụ; chunk trúng → kéo Điều luật cha qua `huong_dan_cho` |
| `huong_dan_toan_van.jsonl` | Toàn văn từng văn bản hướng dẫn theo phiên bản | Đưa cho agent khi đã có Điều luật: lấy `so_hieu` trong `huong_dan_boi`, chọn bản có hiệu lực tại ngày cần hỏi |
| `van_ban.jsonl` | Thông tin mọi văn bản (tên, loại, ngày hiệu lực…) | Hiển thị, trích dẫn |
| `thong_ke.json` | Số liệu tổng hợp | |

`trung_gian/` chứa dữ liệu giữa các bước (cây Điều, câu lệnh sửa đổi, phiên bản Điều, nhật ký áp lệnh).

Chunk theo cấu trúc: Điều ngắn (≤ 400 từ) = 1 chunk; Điều dài → mỗi Khoản (kèm tên Điều, câu dẫn
Điều); Khoản dài → mỗi Điểm (kèm tên Điều, câu dẫn Điều, câu dẫn Khoản).

## Cấu hình và đầu vào

- `config/van_ban_goc.json` – thông tin 4 bộ luật code không tự đọc được (tên, ngày hiệu lực thực tế, số Điều).
- `config/van_ban_huong_dan.json` – ngày hiệu lực văn bản hướng dẫn không ghi trong văn bản (có nguồn).
- `data/raw/manifest.jsonl` – danh mục văn bản đầu vào; `data/raw/SUA_TAY.jsonl` – các chỗ đã sửa tay trong raw.

## Trạng thái

- 3.445 chunk luật, 854 chunk hướng dẫn (537 có liên kết tới Điều luật), toàn văn 31 văn bản hướng dẫn.
- 464 thao tác sửa đổi đã áp. Chưa áp 4: BLTTHS Điều 333, 454, 496 (mốc chèn xuất hiện nhiều lần);
  NQ 03/2024 Điều 3 khoản 3 (không có cụm cần thay).
- `02/2020/NQ-HĐTP` chưa đưa vào: file thực chất là Thông tư 02/2020/TT-TANDTC, không hướng dẫn 4 bộ luật.
- Chưa làm: liên kết gợi ý (bằng embedding) cho chunk hướng dẫn chưa có liên kết; embedding; truy xuất; benchmark.
