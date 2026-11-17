"""Tách một văn bản (danh sách dòng) thành cây Phần / Chương / Mục / Điều / Khoản / Điểm.

Không dựa vào class prov-*; tách theo chữ (BAO_CAO_DU_LIEU.md mục 7).

Kết quả của parse_van_ban():
    {
      "dau_van_ban": [...],        # các dòng trước Điều 1 (quốc hiệu, tên, căn cứ)
      "cuoi_van_ban": [...],       # các dòng sau Điều cuối (thông qua, chữ ký)
      "dieu": [ {so_dieu, thu_tu, tieu_de, vi_tri, doan_dan, diem, khoan}, ... ],
      "canh_bao": [ {loai, dieu, chi_tiet}, ... ]
    }

Một Điều:
    doan_dan : chữ nằm trước Khoản 1 (hoặc toàn bộ nội dung nếu Điều không chia Khoản)
    diem     : các Điểm nằm thẳng dưới Điều (Điều không chia Khoản nhưng có a), b)...)
    khoan    : [{so, noi_dung, diem: [{ky_hieu, noi_dung}], doan_sau}]
               doan_sau = chữ nằm sau Điểm cuối của Khoản (ít gặp)
"""
from __future__ import annotations

import re

from html_text import Line

DIEM_ORDER = "abcdđeghiklmnopqrstuvxy"

RE_DIEU = re.compile(r"^Điều\s+(\d+)([a-zđ]?)\s*\.\s*(.*)$")
RE_PHAN = re.compile(r"^(Phần\s+thứ\s+\S+)\s*[.:]?\s*(.*)$", re.I)
RE_CHUONG = re.compile(r"^(Chương\s+[IVXLC]+)\s*[.:]?\s*(.*)$", re.I)
RE_MUC = re.compile(r"^(Mục\s+(?:\d+|[IVXLC]+))\s*[.:]?\s*(.*)$")          # BLTTHS dùng "Mục I"
RE_TIEU_MUC = re.compile(r"^(Tiểu\s+mục\s+\d+)\s*[.:]?\s*(.*)$", re.I)     # BLDS
RE_KHOAN = re.compile(r"^(\d+)\.(?!\d)\s*(.*)$")   # tránh "1.000.000 đồng"
RE_KHOAN_THIEU_CHAM = re.compile(r"^(\d+)\s+(?=[A-ZĐÀ-Ỹ])(.*)$")   # "1 Trường hợp..." (lỗi nguồn)
RE_DIEM = re.compile(r"^([a-zđ])\)\s*(.*)$")
_THONG_QUA = r"(?:Bộ luật|Luật|Nghị quyết|Nghị định|Thông tư liên tịch|Thông tư) này (?:đã )?được [^.]*thông qua"
RE_CUOI = re.compile(
    rf"^({_THONG_QUA}|CHỦ TỊCH|TM\.|KT\.|Nơi nhận)"
    r"|^[_\-–—*=.\s]{5,}$",            # dòng gạch ngăn cách trước phần ký
    re.I)
# Câu "… này đã được … thông qua" nằm chung dòng với khoản cuối (vd. BLTTHS Điều 510)
RE_CUOI_GIUA = re.compile(rf"(?<=[.;])\s+(?={_THONG_QUA})")
# Chỗ hai Điểm dính trên cùng một dòng: "...; d) Lợi dụng..."
RE_DIEM_DINH = re.compile(r"(?<=[;.:])\s+([a-zđ])\)\s+")


def _diem_idx(c: str) -> int:
    return DIEM_ORDER.index(c) if c in DIEM_ORDER else -1


def _thu_tu(so: int, hau_to: str) -> float:
    """Điều 46a -> 46.01 để sắp sau Điều 46, trước Điều 47."""
    return so + (0.01 * (_diem_idx(hau_to) + 1) if hau_to else 0)


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


def _tach_diem_dinh(text: str, next_letter_idx: int) -> list[str]:
    """Tách dòng có nhiều Điểm dính nhau, chỉ khi chữ cái kế tiếp đúng thứ tự."""
    parts = [text]
    while True:
        last = parts[-1]
        m = None
        for mm in RE_DIEM_DINH.finditer(last):
            if _diem_idx(mm.group(1)) == next_letter_idx:
                m = mm
                break
        if not m:
            return parts
        parts[-1] = last[:m.start()].rstrip()
        parts.append(last[m.start():].lstrip())
        next_letter_idx += 1


def _parse_body(lines: list[str], dieu_label: str, canh_bao: list) -> dict:
    out = {"doan_dan": [], "diem": [], "khoan": []}
    k_cur = None      # Khoản hiện tại
    d_list = out["diem"]   # danh sách Điểm đang điền (của Điều hoặc của Khoản)
    last_d = None     # chữ cái Điểm vừa gặp

    def warn(loai, chi_tiet):
        canh_bao.append({"loai": loai, "dieu": dieu_label, "chi_tiet": chi_tiet})

    queue = list(lines)
    while queue:
        t = queue.pop(0)
        # --- Khoản ---
        expect_k = (k_cur["so"] + 1) if k_cur else 1
        mk = RE_KHOAN.match(t)
        loose = False
        if not mk:
            mk = RE_KHOAN_THIEU_CHAM.match(t)
            loose = True
        if mk and int(mk.group(1)) == expect_k:
            if loose:
                warn("khoan_thieu_dau_cham", t[:80])
            k_cur = {"so": expect_k, "noi_dung": mk.group(2).strip(), "diem": [], "doan_sau": []}
            out["khoan"].append(k_cur)
            d_list, last_d = k_cur["diem"], None
            # Khoản có thể chứa luôn điểm a) dính phía sau
            split = _tach_diem_dinh(k_cur["noi_dung"], 0)
            if len(split) > 1:
                k_cur["noi_dung"] = split[0]
                warn("diem_dinh_dong", f"khoản {expect_k}: {len(split) - 1} điểm tách ra")
                queue[0:0] = split[1:]
            continue
        if mk and not loose and int(mk.group(1)) != expect_k:
            warn("khoan_sai_thu_tu", f"mong đợi {expect_k}: {t[:80]}")
        # --- Điểm ---
        md = RE_DIEM.match(t)
        if md:
            c = md.group(1)
            want = 0 if last_d is None else _diem_idx(last_d) + 1
            got = _diem_idx(c)
            if got >= want:
                if got > want:
                    thieu = ", ".join(DIEM_ORDER[want:got])
                    where = f"khoản {k_cur['so']}" if k_cur else "Điều"
                    warn("thieu_diem", f"{where}: thiếu điểm {thieu} (gặp {c}) – lỗi nguồn, cần bổ sung tay")
                split = _tach_diem_dinh(md.group(2), got + 1)
                if len(split) > 1:
                    warn("diem_dinh_dong", f"điểm {c}: {len(split) - 1} điểm tách ra")
                    queue[0:0] = split[1:]
                d_list.append({"ky_hieu": c, "noi_dung": split[0].strip()})
                last_d = c
                continue
            warn("diem_sai_thu_tu", f"sau {last_d}: {t[:80]}")
        # --- Đoạn văn thường ---
        if k_cur is None:
            if d_list:   # chữ sau các Điểm của Điều -> nối vào Điểm cuối
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


def parse_van_ban(lines: list[Line]) -> dict:
    vi_tri = {"phan": None, "chuong": None, "muc": None, "tieu_muc": None}
    dau, cuoi = [], []
    dieu_list = []
    canh_bao: list[dict] = []
    cur = None            # (meta, body_lines)
    pending_title = None  # heading đang chờ dòng tên
    ended = False
    prev_so = 0

    def flush():
        if cur is None:
            return
        meta, body = cur
        meta.update(_parse_body(body, f"Điều {meta['so_dieu']}", canh_bao))
        dieu_list.append(meta)

    for ln in lines:
        t = ln.text
        if ended:
            cuoi.append(t)
            continue
        if cur is not None and RE_CUOI.match(t):
            ended = True
            cuoi.append(t)
            continue
        if cur is not None and (mg := RE_CUOI_GIUA.search(t)):
            cur[1].append(t[:mg.start()].rstrip())
            cuoi.append(t[mg.end():])
            canh_bao.append({"loai": "cuoi_van_ban_chung_dong", "dieu": f"Điều {cur[0]['so_dieu']}",
                             "chi_tiet": "câu thông qua nằm chung dòng với nội dung, đã tách ra"})
            ended = True
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
            if kind == "phan":
                vi_tri.update(phan=None, chuong=None, muc=None, tieu_muc=None)
            elif kind == "chuong":
                vi_tri.update(chuong=None, muc=None, tieu_muc=None)
            elif kind == "muc":
                vi_tri.update(muc=None, tieu_muc=None)
            vi_tri[kind] = f"{label} – {title}" if title else label
            pending_title = (kind, label)
            continue

        m = RE_DIEU.match(t)
        if m and ln.bold and int(m.group(1)) >= prev_so and not t.startswith(("“", '"')):
            flush()
            so = int(m.group(1))
            prev_so = so
            so_dieu = f"{so}{m.group(2)}"
            title = m.group(3).strip()
            if not title:
                canh_bao.append({"loai": "dieu_khong_ten", "dieu": f"Điều {so_dieu}", "chi_tiet": ""})
            cur = ({"so_dieu": so_dieu, "thu_tu": _thu_tu(so, m.group(2)),
                    "tieu_de": title, "vi_tri": dict(vi_tri)}, [])
            continue

        if cur is None:
            dau.append(t)
        else:
            cur[1].append(t)
    flush()
    return {"dau_van_ban": dau, "cuoi_van_ban": cuoi, "dieu": dieu_list, "canh_bao": canh_bao}


# ---------------------------------------------------------------- hiển thị lại

def render_diem(d: dict) -> str:
    return f"{d['ky_hieu']}) {d['noi_dung']}"


def render_khoan(k: dict, diem: list[dict] | None = None) -> str:
    """diem=None -> mọi Điểm; truyền danh sách con để chỉ in một số Điểm."""
    parts = [f"{k['so']}. {k['noi_dung']}".rstrip()]
    parts += [render_diem(d) for d in (k["diem"] if diem is None else diem)]
    if k.get("doan_sau") and (diem is None or (k["diem"] and diem and diem[-1] is k["diem"][-1])):
        parts.append(k["doan_sau"])
    return "\n".join(p for p in parts if p)


def render_dieu_body(d: dict) -> str:
    parts = [d["doan_dan"]] if d["doan_dan"] else []
    parts += [render_diem(x) for x in d["diem"]]
    parts += [render_khoan(k) for k in d["khoan"]]
    return "\n".join(parts)
