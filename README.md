# Đồ án tốt nghiệp – Hỏi đáp pháp luật dân sự, hình sự (RAG)

Phạm vi: 4 bộ luật gốc – Dân sự (91/2015/QH13), Tố tụng dân sự (92/2015/QH13),
Hình sự (100/2015/QH13), Tố tụng hình sự (101/2015/QH13) – cùng văn bản sửa đổi và hướng dẫn.

Giả thiết: văn bản trong `data/raw/` đã được kiểm tra thủ công và đúng; code chỉ đọc và xử lý.

- `data/raw/` – 56 văn bản HTML, chia 5 nhóm; xem `data/raw/README.md`. Các chỗ đã sửa tay
  so với bản tải về ghi ở `data/raw/SUA_TAY.jsonl`.
- `data/processed/` – kết quả xử lý (sinh ra bằng code, không đưa vào git).
- `config/van_ban_goc.json` – thông tin 4 bộ luật code không tự đọc được (ngày hiệu lực thực tế).
- `src/clean/`:
  - `html_text.py` – HTML → danh sách dòng chữ
  - `cau_truc.py` – dòng → cây Phần/Chương/Mục/Điều/Khoản/Điểm
  - `chunking.py` – cắt chunk theo cấu trúc
  - `build_goc.py` – Phần 1: dựng corpus 4 bộ luật gốc
  - `vi_tri.py`, `doc_lenh.py` – Phần 2: đọc câu lệnh sửa đổi
  - `ap_lenh.py` – Phần 2: áp lệnh, dựng phiên bản theo thời gian
- `BAO_CAO_DU_LIEU.md` – báo cáo thu thập và thiết kế.

## Chạy

```
venv\Scripts\python.exe src\clean\build_goc.py
venv\Scripts\python.exe src\clean\doc_lenh.py
venv\Scripts\python.exe src\clean\ap_lenh.py
```

## Trạng thái

- Phần 1: 2.142 Điều, 3.170 chunk.
- Phần 2: 447 thao tác sửa đổi đã áp; 3 thao tác ở BLTTHS (Điều 333, 454, 496) chưa áp vì mốc
  chèn xuất hiện nhiều lần.
- Phần 3–4, embedding, truy xuất, benchmark: chưa làm.
