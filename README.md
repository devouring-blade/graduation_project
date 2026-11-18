# Hỏi đáp pháp luật dân sự, hình sự (RAG)

Phạm vi: Bộ luật Dân sự, Tố tụng dân sự, Hình sự, Tố tụng hình sự (2015) cùng văn bản sửa đổi và hướng dẫn.

## Chạy

```
venv\Scripts\python.exe src\chay.py
```

Đọc `data/raw/` (+ `config/`), ghi kết quả vào `data/processed/`:

| File | Mỗi dòng | Dùng để |
| --- | --- | --- |
| `dieu_luat.jsonl` | Một Điều luật hoàn chỉnh (theo phiên bản thời gian) + danh sách Điều hướng dẫn liên quan | Đưa cho agent |
| `huong_dan.jsonl` | Một Điều của văn bản hướng dẫn hoàn chỉnh + các Điều luật nó hướng dẫn | Đưa cho agent |
| `chunk_luat.jsonl` | Chunk Điều → Khoản → Điểm, trỏ về Điều cha | Tìm kiếm |
| `chunk_huong_dan.jsonl` | Chunk hướng dẫn, trỏ về Điều luật được hướng dẫn | Tìm kiếm |
| `van_ban.jsonl` | Thông tin văn bản (tên, ngày hiệu lực, đường dẫn vbpl) | Trích dẫn |

## Truy xuất (thiết kế)

1. Tìm trên hai kho chunk (chỉ chunk có hiệu lực tại ngày của câu hỏi).
2. Lấy dần chunk theo điểm, cộng điểm cho Điều luật: chunk luật → Điều cha; chunk hướng dẫn → Điều luật nó trỏ tới.
3. Dừng khi đủ K Điều, hoặc khi điểm Điều tiếp theo tụt quá xa so với Điều đứng đầu.
4. Đưa các Điều ứng viên (kèm hướng dẫn) cho agent; agent chọn Điều phù hợp và trả lời.
