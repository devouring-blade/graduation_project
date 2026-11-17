"""Cắt chunk theo cấu trúc (BAO_CAO_DU_LIEU.md mục 6.2).

- Điều ngắn (<= NGUONG_DIEU từ): cả Điều là 1 chunk.
- Điều dài: mỗi Khoản 1 chunk; Khoản dài (> NGUONG_KHOAN từ) và có Điểm: mỗi Điểm 1 chunk.
- Điều dài không chia Khoản nhưng có Điểm: mỗi Điểm 1 chunk.
- Mỗi chunk có dòng đầu (tên văn bản – Chương, rồi "Điều N. Tên"), lặp lại đoạn dẫn của Điều
  và đoạn dẫn của Khoản khi cắt tới Điểm.
- Không ghi ngày vào chữ của chunk.
"""
from __future__ import annotations

import hashlib

from cau_truc import render_diem, render_dieu_body, render_khoan

NGUONG_DIEU = 400
NGUONG_KHOAN = 400


def so_tu(text: str) -> int:
    return len(text.split())


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _header(vb: dict, dieu: dict) -> str:
    vt = dieu["vi_tri"]
    nhom = vt.get("chuong") or vt.get("phan")
    line1 = vb["ten"] + (f" – {nhom}" if nhom else "")
    return f"{line1}\nĐiều {dieu['so_dieu']}. {dieu['tieu_de']}".rstrip()


def _trich_dan(vb: dict, so_dieu: str, khoan=None, diem=None) -> str:
    parts = []
    if diem:
        parts.append(f"Điểm {diem}")
    if khoan is not None:
        parts.append(f"khoản {khoan}" if parts else f"Khoản {khoan}")
    parts.append(f"Điều {so_dieu}")
    return " ".join(parts) + f" {vb['ten']} {vb['nam']}"


def chunk_dieu(vb: dict, dieu: dict) -> list[dict]:
    """Trả về các chunk (chưa có trường hiệu lực) của một phiên bản Điều."""
    head = _header(vb, dieu)
    body = render_dieu_body(dieu)
    did = dieu["dieu_id"]
    dan = dieu["doan_dan"]
    out = []

    def add(suffix, cap, noi_dung, khoan=None, diem=None, context=""):
        text = "\n".join(p for p in (head, context, noi_dung) if p)
        out.append({
            "chunk_id": did + suffix,
            "dieu_id": did,
            "cap": cap,
            "trich_dan": _trich_dan(vb, dieu["so_dieu"], khoan, diem),
            "text": text,
            "noi_dung": noi_dung,
            "so_tu": so_tu(text),
        })

    if so_tu(body) <= NGUONG_DIEU or (not dieu["khoan"] and not dieu["diem"]):
        add("", "dieu", body)
        return out

    if not dieu["khoan"]:                       # Điều chỉ có Điểm
        for d in dieu["diem"]:
            add(f"#E{d['ky_hieu']}", "diem", render_diem(d), diem=d["ky_hieu"], context=dan)
        return out

    for k in dieu["khoan"]:
        kt = render_khoan(k)
        if so_tu(kt) <= NGUONG_KHOAN or not k["diem"]:
            add(f"#K{k['so']}", "khoan", kt, khoan=k["so"], context=dan)
            continue
        dan_k = f"{k['so']}. {k['noi_dung']}"
        ctx = "\n".join(p for p in (dan, dan_k) if p)
        for d in k["diem"]:
            nd = render_diem(d)
            if d is k["diem"][-1] and k["doan_sau"]:
                nd += "\n" + k["doan_sau"]
            add(f"#K{k['so']}#E{d['ky_hieu']}", "diem", nd, khoan=k["so"], diem=d["ky_hieu"], context=ctx)
    # Đoạn dẫn của Điều dài đã lặp lại trong từng chunk; không cần chunk riêng.
    return out
