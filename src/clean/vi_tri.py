"""Đọc cụm chỉ vị trí trong câu lệnh sửa đổi thành danh sách (Điều, Khoản, Điểm).

Ví dụ:
  "điểm s và điểm t khoản 1 Điều 51"              -> (51,1,s) (51,1,t)
  "khoản 1 và khoản 2 Điều 66"                    -> (66,1,-) (66,2,-)
  "điểm đ khoản 2, điểm b khoản 3 Điều 172"       -> (172,2,đ) (172,3,b)
  "các điều 248, 249, 250, 251 và 252"            -> (248,-,-) ... (252,-,-)
  "khoản 1 Điều 219, khoản 1 Điều 220"            -> (219,1,-) (220,1,-)
  "tên điều và khoản 1 Điều 245"                  -> (245,TEN,-) (245,1,-)
  "chương XII"                                    -> chuong XII
Mục trong cùng nhóm chưa có Điều thì nhận Điều đứng sau gần nhất ("điểm c khoản 2, … Điều 29").
"""
from __future__ import annotations

import re

D = r"[a-zđ]"
TOKEN = re.compile(
    r"(?P<ten>tên\s+(?:điều|Điều|chương|Chương|mục|Mục))"
    r"|(?P<doan>đoạn\s+(?:mở\s+đầu|dẫn|đầu|thứ\s+\w+|\d+))"
    r"|(?:các\s+)?điểm\s+(?P<diem>{d}(?:(?:\s*,\s*|\s+và\s+|\s+hoặc\s+)(?:điểm\s+)?{d}(?!\w))*)(?!\w)"
    r"|(?:các\s+)?khoản\s+(?P<khoan>\d+[a-zđ]?(?:(?:\s*,\s*|\s+và\s+|\s+hoặc\s+)(?:khoản\s+)?\d+[a-zđ]?(?!\w))*)(?!\w)"
    r"|(?P<cac>các\s+)?(?:Điều|điều)\s+(?P<dieu>\d+[a-zđ]?(?:(?:\s*,\s*|\s+và\s+|\s+hoặc\s+)(?:Điều\s+)?\d+[a-zđ]?(?!\w))*)(?!\w)"
    r"|(?:các\s+)?(?:mục|Mục)\s+(?P<muc>\d+|[IVXLC]+)(?!\w)"
    r"|(?:các\s+)?(?:chương|Chương)\s+(?P<chuong>[IVXLC]+(?:(?:\s*,\s*|\s+và\s+)(?:chương\s+|Chương\s+)?[IVXLC]+)*)(?!\w)"
    .replace("{d}", D)
)


def _items(s: str) -> list[str]:
    parts = re.split(r"\s*,\s*|\s+và\s+|\s+hoặc\s+", s.strip())
    return [re.sub(r"^(?:điểm|khoản|Điều|điều|chương|Chương)\s+", "", p) for p in parts if p]


def doc_vi_tri(text: str) -> tuple[list[dict], list[str]]:
    """Trả về (danh sách vị trí, danh sách chương). Mỗi vị trí: {dieu, khoan, diem, ten}."""
    out: list[dict] = []
    chuong: list[str] = []
    pending: list[dict] = []
    cur: dict = {}

    def push():
        nonlocal cur
        if cur:
            pending.append(cur)
        cur = {}

    for m in TOKEN.finditer(text):
        g = m.groupdict()
        if g["ten"]:
            push()
            cur = {"ten": True}
            push()
        elif g["doan"]:
            push()
            cur = {"doan": g["doan"]}
        elif g["diem"]:
            if cur.get("khoan") or cur.get("diem"):
                push()
            cur["diem"] = _items(g["diem"])
        elif g["khoan"]:
            ks = _items(g["khoan"])
            if cur.get("khoan") and not cur.get("diem") and not cur.get("doan"):
                cur["khoan"] += ks
            elif cur.get("khoan"):
                push()
                cur["khoan"] = ks
            elif (cur.get("diem") or cur.get("doan")) and len(ks) > 1:
                # "điểm a khoản 2 và khoản 3": điểm a chỉ thuộc khoản 2, khoản 3 là cả khoản
                cur["khoan"] = ks[:1]
                push()
                for k in ks[1:]:
                    cur = {"khoan": [k]}
                    push()
            else:
                cur["khoan"] = ks
        elif g["dieu"]:
            push()
            ds = _items(g["dieu"])
            if not pending:
                pending = [{}]
            # "khoản 1 các điều 134, 135": khoản áp cho từng Điều.
            # "điểm c khoản 1 Điều 192 và Điều 205": chỉ Điều đầu nhận khoản/điểm, Điều sau là cả Điều.
            chi_ten = all(p.get("ten") for p in pending if p)   # "tên điều Điều 220 và Điều 221": tên của cả hai
            for i, d in enumerate(ds):
                if i == 0 or g["cac"] or chi_ten:
                    out += [{**p, "dieu": d} for p in pending]
                else:
                    out.append({"dieu": d})
            pending = []
        elif g["chuong"]:
            push()
            chuong += _items(g["chuong"])
        elif g["muc"]:
            push()
            cur = {"muc": g["muc"]}
    push()
    # Mục chưa có Điều (sẽ mượn Điều từ mệnh đề sau, hoặc lỗi)
    out += [{**p, "dieu": None} for p in pending if p.get("khoan") or p.get("diem") or p.get("ten")]
    # Trải phẳng khoan/diem
    flat = []
    for o in out:
        ks = o.get("khoan") or [None]
        ds = o.get("diem") or [None]
        for k in ks:
            for d in ds:
                flat.append({"dieu": o["dieu"], "khoan": k, "diem": d, "ten": bool(o.get("ten")),
                             "doan": o.get("doan"), "muc": o.get("muc")})
    return flat, chuong
