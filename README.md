# Đồ án tốt nghiệp – Hỏi đáp pháp luật dân sự, hình sự (RAG)

Phạm vi: 4 bộ luật gốc – Dân sự (91/2015/QH13), Tố tụng dân sự (92/2015/QH13),
Hình sự (100/2015/QH13), Tố tụng hình sự (101/2015/QH13) – cùng văn bản sửa đổi và hướng dẫn.

- `data/raw/` – 56 văn bản HTML tải từ vbpl.vn, chia 5 nhóm; xem `data/raw/README.md`.
- `data/processed/` – corpus đã làm sạch (sinh ra bằng code, không đưa vào git).
- `config/van_ban_goc.json` – thông tin 4 bộ luật mà code không tự đọc được (ngày hiệu lực thực tế…).
- `src/clean/` – code lớp clean:
  - `html_text.py` – HTML → danh sách dòng chữ
  - `cau_truc.py` – dòng → cây Phần/Chương/Mục/Điều/Khoản/Điểm
  - `chunking.py` – cắt chunk theo cấu trúc
  - `build_goc.py` – Phần 1: dựng corpus 4 bộ luật gốc
- `BAO_CAO_DU_LIEU.md` – báo cáo đầy đủ: thu thập, thiết kế, kết quả, việc còn lại.

## Chạy

```
venv\Scripts\python.exe src\clean\build_goc.py
```

## Trạng thái (17/11/2026)

- Raw: xong.
- Clean Phần 1 (4 bộ luật gốc, chưa ghép sửa đổi): xong – 2.142 Điều, 3.170 chunk, đạt mọi kiểm tra.
- Clean Phần 2–4, embedding, truy xuất, benchmark: chưa làm.
