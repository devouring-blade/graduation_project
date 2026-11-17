"""Chạy toàn bộ xử lý dữ liệu một mạch: data/raw -> data/processed.

    venv\\Scripts\\python.exe src\\chay.py

Xoá data/processed rồi chạy lần lượt; bước nào lỗi thì dừng.
  1. build_goc        tách 4 bộ luật gốc thành Điều/Khoản/Điểm
  2. build_huong_dan  tách các văn bản hướng dẫn
  3. doc_lenh         đọc câu lệnh trong các văn bản sửa đổi
  4. ap_lenh          áp sửa đổi, dựng phiên bản theo thời gian, cắt chunk
  5. lien_ket         liên kết hướng dẫn <-> Điều luật, xuất kết quả cuối

Kết quả cuối (data/processed/): dieu_luat.jsonl, huong_dan.jsonl, chunk_luat.jsonl, chunk_huong_dan.jsonl,
van_ban.jsonl, thong_ke.json. Dữ liệu trung gian: data/processed/trung_gian/.
"""
from __future__ import annotations

import importlib
import shutil
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC / "clean"))
OUT = SRC.parent / "data" / "processed"

BUOC = [("build_goc", "Tách 4 bộ luật gốc"),
        ("build_huong_dan", "Tách văn bản hướng dẫn"),
        ("doc_lenh", "Đọc câu lệnh sửa đổi"),
        ("ap_lenh", "Áp sửa đổi, dựng phiên bản, cắt chunk"),
        ("lien_ket", "Liên kết hướng dẫn ↔ Điều luật, xuất kết quả")]


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    t0 = time.time()
    for i, (mod, ten) in enumerate(BUOC, 1):
        print(f"[{i}/{len(BUOC)}] {ten}")
        rc = importlib.import_module(mod).main()
        if rc:
            print(f"DỪNG: bước {mod} lỗi (mã {rc})")
            return rc
    print(f"Xong sau {time.time() - t0:.0f} giây. Kết quả: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
