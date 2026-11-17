"""Tách một văn bản (danh sách dòng) thành cây Phần / Chương / Mục / Điều / Khoản / Điểm.

Giả thiết: văn bản đầu vào đã đúng (đã kiểm tra thủ công). Tách theo chữ, không dựa vào class prov-*.

parse_van_ban() trả về:
    {"dau_van_ban": [...], "cuoi_van_ban": [...],
     "dieu": [{so_dieu, thu_tu, tieu_de, vi_tri, doan_dan, diem, khoan}, ...]}
Một Điều:
    doan_dan : chữ trước Khoản đầu tiên (hoặc toàn bộ nội dung nếu Điều không chia Khoản)
    diem     : Điểm nằm thẳng dưới Điều (Điều không chia Khoản)
    khoan    : [{so, noi_dung, diem: [{ky_hieu, noi_dung}], doan_sau}]
               doan_sau = chữ nằm sau Điểm cuối của Khoản
"""
from __future__ import annotations

import re

from html_text import Line

DIEM_ORDER = "abcdđeghiklmnopqrstuvxy"

RE_DIEU = re.compile(r"^Điều\s+(\d+)([a-zđ]?)\s*(?:\.\s*(.*)|$)")       # "Điều 1." hoặc "Điều 1" (NQ 103, 110/2015)
RE_PHAN = re.compile(r"^(Phần\s+thứ\s+\S+)\s*[.:]?\s*(.*)$", re.I)
RE_CHUONG = re.compile(r"^(Chương\s+[IVXLC]+)\s*[.:]?\s*(.*)$", re.I)
RE_MUC = re.compile(r"^(Mục\s+(?:\d+|[IVXLC]+))\s*[.:]?\s*(.*)$")          # BLTTHS dùng "Mục I"
RE_TIEU_MUC = re.compile(r"^(Tiểu\s+mục\s+\d+)\s*[.:]?\s*(.*)$", re.I)     # BLDS
RE_KHOAN = re.compile(r"^(\d+[a-zđ]?)\.(?!\d)\s*(.*)$")                   # "1." "1a."; tránh "1.000.000"
RE_DIEM = re.compile(r"^([a-zđ])\)\s*(.*)$")
RE_CUOI = re.compile(
    r"^((?:Bộ luật|Luật|Nghị quyết|Nghị định|Thông tư liên tịch|Thông tư) này (?:đã )?được [^.]*thông qua"
    r"|CHỦ TỊCH|TM\.|KT\.|Nơi nhận)"
    r"|^[_\-–—*=.\s]{5,}$",            # dòng gạch ngăn cách trước phần ký
    re.I)


def khoa_khoan(so) -> tuple:
    """Khóa sắp xếp số khoản: 1 < 1a < 1b < 2."""
    s = str(so)
    num = int(re.match(r"\d+", s).group())
    suf = s[len(str(num)):]
    return (num, DIEM_ORDER.index(suf) + 1 if suf else 0)


def _thu_tu(so: int, hau_to: str) -> float:
    """Điều 46a -> 46.01 để sắp sau Điều 46, trước Điều 47."""
    return so + (0.01 * (DIEM_ORDER.index(hau_to) + 1) if hau_to else 0)


def _heading(line: Line):
    if not line.bold:
        return None
    for kind, rx in (("phan", RE_PHAN), ("chuong", RE_CHUONG), ("muc", RE_MUC), ("tieu_muc", RE_TIEU_MUC)):
        m = rx.match(line.text)
        if m:
            return kind, m.group(1), m.group(2).strip()
    return None


def _is_heading_title(line: Line) -> bool:
    """Dòng tên Chương/Phần/Mục nằm riêng (in đậm, không phải Điều, không phải heading khác)."""
    if not line.bold or RE_DIEU.match(line.text) or _heading(line):
        return False
    letters = [c for c in line.text if c.isalpha()]
    return line.center or (letters and sum(c.isupper() for c in letters) / len(letters) > 0.8)


def _parse_body(lines: list[str], tu_do: bool = False, khoan_cho_phep: set | None = None) -> dict:
    """Thân một Điều -> doan_dan / diem / khoan.

    Văn bản thường: khoản đánh số liên tục 1, 2, 3…
    tu_do=True (nội dung trong câu lệnh sửa đổi): khoản bắt đầu từ số bất kỳ, có thể có chữ ("1a"),
    chỉ cần tăng dần (và thuộc khoan_cho_phep nếu có).
    """
    out = {"doan_dan": [], "diem": [], "khoan": []}
    k_cur = None
    d_list = out["diem"]
    for t in lines:
        mk = RE_KHOAN.match(t)
        if mk:
            lab = mk.group(1)
            if tu_do:
                ok = (khoan_cho_phep is None or lab in khoan_cho_phep) and \
                     (k_cur is None or khoa_khoan(lab) > khoa_khoan(k_cur["so"]))
            else:
                ok = lab.isdigit() and int(lab) == (k_cur["so"] + 1 if k_cur else 1)
            if ok:
                k_cur = {"so": int(lab) if lab.isdigit() else lab, "noi_dung": mk.group(2).strip(),
                         "diem": [], "doan_sau": []}
                out["khoan"].append(k_cur)
                d_list = k_cur["diem"]
                continue
        md = RE_DIEM.match(t)
        if md:
            d_list.append({"ky_hieu": md.group(1), "noi_dung": md.group(2).strip()})
            continue
        # đoạn văn thường
        if k_cur is None:
            if d_list:       # chữ sau các Điểm của Điều -> nối vào Điểm cuối
                d_list[-1]["noi_dung"] += "\n" + t
            else:
                out["doan_dan"].append(t)
        elif k_cur["diem"]:
            k_cur["doan_sau"].append(t)
        else:
            k_cur["noi_dung"] += "\n" + t
    out["doan_dan"] = "\n".join(out["doan_dan"])
    for k in out["khoan"]:
        k["doan_sau"] = "\n".join(k["doan_sau"])
    return out


def parse_van_ban(lines: list[Line], tu_do: bool = False, khoan_cho_phep: set | None = None) -> dict:
    vi_tri = {"phan": None, "chuong": None, "muc": None, "tieu_muc": None}
    dau, cuoi, dieu_list = [], [], []
    cur = None            # (meta, body_lines)
    pending_title = None  # heading đang chờ dòng tên
    ended = False
    prev_so = 0
    # Câu "Nghị quyết này đã được … thông qua …" có thể nằm TRONG Điều hiệu lực (văn bản HĐTP),
    # nên chỉ coi là hết văn bản khi phía sau không còn tiêu đề Điều nào.
    cuoi_dieu = max((i for i, ln in enumerate(lines) if ln.bold and RE_DIEU.match(ln.text)), default=-1)

    def flush():
        if cur is not None:
            meta, body = cur
            meta.update(_parse_body(body, tu_do, khoan_cho_phep))
            dieu_list.append(meta)

    for i, ln in enumerate(lines):
        t = ln.text
        if ended:
            cuoi.append(t)
            continue
        if cur is not None and i > cuoi_dieu and RE_CUOI.match(t):
            ended = True
            cuoi.append(t)
            continue
        # Dòng tên của heading vừa gặp (tên dài có thể chiếm nhiều dòng)
        if pending_title and _is_heading_title(ln):
            kind, label = pending_title
            vi_tri[kind] = f"{vi_tri[kind]} {t}" if vi_tri[kind] != label else f"{label} – {t}"
            continue
        pending_title = None

        h = _heading(ln)
        if h:
            kind, label, title = h
            reset = {"phan": ("phan", "chuong", "muc", "tieu_muc"), "chuong": ("chuong", "muc", "tieu_muc"),
                     "muc": ("muc", "tieu_muc"), "tieu_muc": ("tieu_muc",)}[kind]
            vi_tri.update({k: None for k in reset})
            vi_tri[kind] = f"{label} – {title}" if title else label
            pending_title = (kind, label)
            continue

        m = RE_DIEU.match(t)
        if m and ln.bold and int(m.group(1)) >= prev_so and not t.startswith(("“", '"')):
            flush()
            so = int(m.group(1))
            prev_so = so
            cur = ({"so_dieu": f"{so}{m.group(2)}", "thu_tu": _thu_tu(so, m.group(2)),
                    "tieu_de": (m.group(3) or "").strip(), "vi_tri": dict(vi_tri)}, [])
            continue

        if cur is None:
            dau.append(t)
        else:
            cur[1].append(t)
    flush()
    return {"dau_van_ban": dau, "cuoi_van_ban": cuoi, "dieu": dieu_list}


# ---------------------------------------------------------------- hiển thị lại
def render_diem(d: dict) -> str:
    return f"{d['ky_hieu']}) {d['noi_dung']}"


def render_khoan(k: dict) -> str:
    parts = [f"{k['so']}. {k['noi_dung']}".rstrip()]
    parts += [render_diem(d) for d in k["diem"]]
    if k.get("doan_sau"):
        parts.append(k["doan_sau"])
    return "\n".join(p for p in parts if p)


def render_dieu_body(d: dict) -> str:
    parts = [d["doan_dan"]] if d["doan_dan"] else []
    parts += [render_diem(x) for x in d["diem"]]
    parts += [render_khoan(k) for k in d["khoan"]]
    return "\n".join(parts)
