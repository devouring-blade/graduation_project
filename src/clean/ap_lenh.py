"""Bước 4: áp câu lệnh sửa đổi lên bộ luật gốc và văn bản hướng dẫn, dựng phiên bản theo thời gian,
cắt chunk cho từng phiên bản.

Đầu vào/ra: data/processed/trung_gian/
    vào: goc_*.jsonl, huong_dan_*.jsonl, lenh_sua_doi.jsonl
    ra : dieu_phien_ban.jsonl    mỗi dòng một phiên bản Điều [valid_from, valid_to)
         chunks_phien_ban.jsonl  chunk theo phiên bản; chunk không đổi chữ thì giữ một bản (kéo dài hiệu lực)
    Thao tác sửa đổi không áp được in ra màn hình kèm lý do.
Nguyên tắc:
- Câu lệnh áp theo thứ tự ngày hiệu lực; không sửa đè – phiên bản cũ đóng lại bằng valid_to.
- Câu lệnh nào không áp được chắc chắn -> ghi lỗi, KHÔNG áp, không đoán.
- Phiên bản có valid_to == valid_from (vd. bản gốc BLHS 2015 của Điều bị Luật 12/2017 sửa, cùng
  hiệu lực 01/01/2018) -> chua_tung_ap_dung = true; giữ trong dieu_phien_ban, không sinh chunk.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cau_truc import (DIEM_ORDER, _parse_body, _thu_tu, khoa_khoan,  # noqa: E402
                      parse_van_ban, render_dieu_body)
from build_goc import read_jsonl, write_jsonl  # noqa: E402
from chunking import chunk_dieu, sha  # noqa: E402
from html_text import Line, norm  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TG = ROOT / "data" / "processed" / "trung_gian"
RE_DIEU_HEAD = re.compile(r"^Điều\s+\d+[a-zđ]?\s*\.")


class Loi(Exception):
    pass


# ------------------------------------------------------------------ tiện ích cây Điều
def _key_dieu(so: str):
    m = re.match(r"(\d+)([a-zđ]?)", so)
    return _thu_tu(int(m.group(1)), m.group(2))


def _tim_khoan(art: dict, so) -> dict | None:
    return next((k for k in art["khoan"] if str(k["so"]) == str(so)), None)


def _tim_diem(lst: list, c: str) -> dict | None:
    return next((d for d in lst if d["ky_hieu"] == c), None)


def _sap_xep(art: dict):
    art["khoan"].sort(key=lambda k: khoa_khoan(k["so"]))
    for k in art["khoan"]:
        k["diem"].sort(key=lambda d: DIEM_ORDER.index(d["ky_hieu"]))
    art["diem"].sort(key=lambda d: DIEM_ORDER.index(d["ky_hieu"]))


def _lay_dieu(state: dict, so: str) -> dict:
    a = state.get(so)
    if a is None or a["trang_thai"] == "bai_bo":
        raise Loi(f"không có Điều {so} (hoặc đã bị bãi bỏ)")
    return a


def _hash_art(a: dict | None) -> str | None:
    if a is None:
        return None
    keep = {k: a[k] for k in ("tieu_de", "doan_dan", "diem", "khoan", "trang_thai")}
    return hashlib.sha256(json.dumps(keep, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ nội dung trong ngoặc kép
def _doc_noi_dung(lines: list[str], khoan_cho_phep: set | None):
    L = [norm(x) for x in lines if norm(x)]
    if not L:
        raise Loi("nội dung rỗng")
    if RE_DIEU_HEAD.match(L[0]):
        parsed = parse_van_ban([Line(t, bold=bool(RE_DIEU_HEAD.match(t))) for t in L], tu_do=True)
        if not parsed["dieu"]:
            raise Loi("không tách được Điều trong nội dung")
        return "dieu", parsed["dieu"]
    return "body", _parse_body(L, tu_do=True, khoan_cho_phep=khoan_cho_phep)


# ------------------------------------------------------------------ lệnh cấu trúc
def ap_cau_truc(state: dict, c: dict) -> set[str]:
    vt, chuong, loai = c["vi_tri"], c.get("chuong", []), c["loai"]
    touched: set[str] = set()

    if loai == "bai_bo":
        for ch in chuong:
            hit = [s for s, a in state.items() if a["trang_thai"] != "bai_bo"
                   and re.match(rf"^Chương\s+{ch}\b", (a["vi_tri"] or {}).get("chuong") or "")]
            if not hit:
                raise Loi(f"không tìm thấy Điều nào thuộc Chương {ch}")
            for s in hit:
                _bai_bo_dieu(state[s])
                touched.add(s)
        for v in vt:
            if v["ten"] or v.get("doan"):
                raise Loi("bãi bỏ tên/đoạn – chưa hỗ trợ")
            a = _lay_dieu(state, v["dieu"])
            if v["khoan"] is None and v["diem"] is None:
                _bai_bo_dieu(a)
            elif v["diem"] is None:
                k = _tim_khoan(a, v["khoan"])
                if k is None:
                    raise Loi(f"Điều {v['dieu']} không có khoản {v['khoan']}")
                a["khoan"].remove(k)
            else:
                lst = a["diem"] if v["khoan"] is None else (_tim_khoan(a, v["khoan"]) or {}).get("diem")
                d = _tim_diem(lst or [], v["diem"])
                if d is None:
                    raise Loi(f"không có điểm {v['diem']} khoản {v['khoan']} Điều {v['dieu']}")
                lst.remove(d)
            touched.add(v["dieu"])
        return touched

    # sua / bo_sung: nội dung quyết định đơn vị nào được thay/thêm
    listed_k = {str(v["khoan"]) for v in vt if v["khoan"] and not v["diem"]}
    kind, parsed = _doc_noi_dung(c["noi_dung"], listed_k or None)
    dieus = list(dict.fromkeys(v["dieu"] for v in vt))
    cho_phep_them = loai == "bo_sung" or bool(re.search(r"\bbổ sung (?:các |thêm )?(?:khoản|điểm|Điều)", c["cau_goc"]))

    if kind == "dieu":
        for A in parsed:
            so = A["so_dieu"]
            vts = [v for v in vt if v["dieu"] == so]
            if not vts:
                raise Loi(f"nội dung có Điều {so} nhưng câu lệnh không nêu Điều này")
            whole = any(v["khoan"] is None and v["diem"] is None and not v["ten"] for v in vts)
            if whole:
                if so in state and state[so]["trang_thai"] != "bai_bo":
                    if loai == "bo_sung":
                        raise Loi(f"bổ sung Điều {so} nhưng Điều này đã có")
                    old = state[so]
                    old.update(tieu_de=A["tieu_de"], doan_dan=A["doan_dan"], diem=A["diem"], khoan=A["khoan"])
                else:
                    if loai != "bo_sung":
                        raise Loi(f"sửa Điều {so} nhưng Điều này chưa có")
                    state[so] = _dieu_moi(state, so, A)
            else:
                a = _lay_dieu(state, so)
                if any(v["ten"] for v in vts):
                    a["tieu_de"] = A["tieu_de"]
                for v in vts:
                    if v["khoan"] and not v["diem"]:
                        K = _tim_khoan(A, v["khoan"])
                        if K is None:
                            raise Loi(f"nội dung không có khoản {v['khoan']}")
                        _upsert_khoan(a, K, cho_phep_them, them_ok={str(v["khoan"])})
            _sap_xep(state[so])
            touched.add(so)
        return touched

    # nội dung không có tiêu đề Điều
    if len(dieus) != 1 or dieus[0] is None:
        raise Loi(f"nội dung không có tiêu đề Điều nhưng câu lệnh nêu {len(dieus)} Điều")
    so = dieus[0]
    a = _lay_dieu(state, so)
    body = parsed
    whole = all(v["khoan"] is None and v["diem"] is None and not v["ten"] and not v.get("doan") for v in vt)
    if whole:
        a.update(doan_dan=body["doan_dan"], diem=body["diem"], khoan=body["khoan"])
    elif body["khoan"]:
        if body["doan_dan"] or body["diem"]:
            raise Loi("nội dung có đoạn/điểm nằm trước khoản – chưa rõ đặt vào đâu")
        chi_doan_dau = {str(v["khoan"]) for v in vt if v["khoan"] and v.get("doan")}
        them_ok = {str(v["khoan"]) for v in vt if v["khoan"]}
        for K in body["khoan"]:
            if str(K["so"]) in chi_doan_dau:
                # "Sửa đổi đoạn mở đầu khoản 1": chỉ thay câu dẫn, GIỮ các điểm và đoạn sau điểm
                if _so_doan(next(v["doan"] for v in vt if str(v["khoan"]) == str(K["so"]))) != 1:
                    raise Loi("sửa đoạn không phải đoạn mở đầu – chưa hỗ trợ")
                if K["diem"]:
                    raise Loi("sửa đoạn mở đầu nhưng nội dung có cả điểm")
                old = _tim_khoan(a, K["so"])
                if old is None:
                    raise Loi(f"không có khoản {K['so']}")
                old["noi_dung"] = K["noi_dung"]
                continue
            _upsert_khoan(a, K, cho_phep_them, them_ok)
    elif body["diem"]:
        if body["doan_dan"]:
            raise Loi("nội dung có đoạn văn trước điểm – chưa rõ đặt vào đâu")
        ks = {v["khoan"] for v in vt}
        if len(ks) != 1:
            raise Loi("nội dung là điểm nhưng câu lệnh nêu nhiều khoản")
        kso = ks.pop()
        lst = a["diem"] if kso is None else (_tim_khoan(a, kso) or {}).get("diem")
        if lst is None:
            raise Loi(f"Điều {so} không có khoản {kso}")
        them_ok = {v["diem"] for v in vt if v["diem"]}
        for P in body["diem"]:
            old = _tim_diem(lst, P["ky_hieu"])
            if old is not None:
                if loai == "bo_sung":
                    raise Loi(f"bổ sung điểm {P['ky_hieu']} nhưng điểm này đã có")
                old["noi_dung"] = P["noi_dung"]
            else:
                if not (cho_phep_them and P["ky_hieu"] in them_ok):
                    raise Loi(f"sửa điểm {P['ky_hieu']} khoản {kso} nhưng điểm này chưa có")
                lst.append({"ky_hieu": P["ky_hieu"], "noi_dung": P["noi_dung"]})
    else:
        # chỉ là một đoạn văn: đoạn mở đầu của khoản ("Sửa đổi đoạn mở đầu khoản 1 …") hoặc khoản không chia điểm
        vs = [v for v in vt if v["khoan"] and not v["diem"]]
        if len(vs) == 1 and v_doan(vs[0]):
            K = _tim_khoan(a, vs[0]["khoan"])
            if K is None:
                raise Loi(f"không có khoản {vs[0]['khoan']}")
            K["noi_dung"] = body["doan_dan"]
        else:
            raise Loi("nội dung là đoạn văn không đánh số – chưa rõ thay vào đâu")
    _sap_xep(a)
    return {so}


def v_doan(v) -> bool:
    return bool(v.get("doan"))


def _upsert_khoan(a: dict, K: dict, cho_phep_them: bool, them_ok: set):
    old = _tim_khoan(a, K["so"])
    new = {"so": K["so"], "noi_dung": K["noi_dung"], "diem": K["diem"], "doan_sau": K.get("doan_sau", "")}
    if old is not None:
        old.clear()
        old.update(new)
    else:
        if not (cho_phep_them and str(K["so"]) in them_ok):
            raise Loi(f"sửa khoản {K['so']} nhưng khoản này chưa có")
        a["khoan"].append(new)


def _bai_bo_dieu(a: dict):
    a.update(trang_thai="bai_bo", doan_dan="", diem=[], khoan=[])


def _dieu_moi(state: dict, so: str, A: dict) -> dict:
    tt = _key_dieu(so)
    prev = max((x for x in state.values() if x["thu_tu"] < tt), key=lambda x: x["thu_tu"], default=None)
    return {"so_dieu": so, "thu_tu": tt, "tieu_de": A["tieu_de"],
            "vi_tri": copy.deepcopy(prev["vi_tri"]) if prev else {},
            "doan_dan": A["doan_dan"], "diem": A["diem"], "khoan": A["khoan"], "trang_thai": "hieu_luc"}


# ------------------------------------------------------------------ lệnh cụm từ
class O:
    """Một ô chữ có thể đọc/ghi: cả trường, hoặc một dòng (đoạn) trong trường nhiều dòng."""

    def __init__(self, obj: dict, key: str, line: int | None = None):
        self.obj, self.key, self.line = obj, key, line

    def get(self) -> str:
        t = self.obj[self.key]
        return t if self.line is None else t.split("\n")[self.line]

    def set(self, s: str):
        if self.line is None:
            self.obj[self.key] = s
        else:
            parts = self.obj[self.key].split("\n")
            parts[self.line] = s
            self.obj[self.key] = "\n".join(parts)


def _o_khoan(k: dict, theo_doan: bool) -> list[O]:
    if not theo_doan:
        return [O(k, "noi_dung")] + [O(d, "noi_dung") for d in k["diem"]] + ([O(k, "doan_sau")] if k.get("doan_sau") else [])
    out = [O(k, "noi_dung", i) for i in range(len(k["noi_dung"].split("\n")))]
    out += [O(d, "noi_dung") for d in k["diem"]]
    if k.get("doan_sau"):
        out += [O(k, "doan_sau", i) for i in range(len(k["doan_sau"].split("\n")))]
    return out


def _so_doan(s: str) -> int:
    m = re.search(r"\d+", s)
    if m:
        return int(m.group())
    if re.search(r"mở đầu|dẫn|đầu", s):
        return 1
    raise Loi(f"chưa hiểu '{s}'")


def _don_vi(a: dict, v: dict) -> list[O]:
    """Các ô chữ thuộc vị trí v."""
    if v["ten"]:
        return [O(a, "tieu_de")]
    if v["diem"]:
        lst = a["diem"] if v["khoan"] is None else (_tim_khoan(a, v["khoan"]) or {}).get("diem")
        d = _tim_diem(lst or [], v["diem"])
        if d is None:
            raise Loi(f"không có điểm {v['diem']} khoản {v['khoan']} Điều {a['so_dieu']}")
        return [O(d, "noi_dung")]
    if v["khoan"]:
        k = _tim_khoan(a, v["khoan"])
        if k is None:
            raise Loi(f"không có khoản {v['khoan']} Điều {a['so_dieu']}")
        if v.get("doan"):
            # "đoạn 2 khoản 2": đoạn đếm theo thứ tự: các dòng đầu khoản, từng điểm, các dòng sau điểm
            cells = _o_khoan(k, True)
            n = _so_doan(v["doan"])
            if not 1 <= n <= len(cells):
                raise Loi(f"khoản {v['khoan']} Điều {a['so_dieu']} không có {v['doan']} (có {len(cells)} đoạn)")
            return [cells[n - 1]]
        return _o_khoan(k, False)
    out = [O(a, "doan_dan")] if a["doan_dan"] else []
    out += [O(d, "noi_dung") for d in a["diem"]]
    for k in a["khoan"]:
        out += _o_khoan(k, False)
    return out


def _bien(s: str, dau: bool) -> str:
    """Ranh giới trọn từ ở đầu/cuối cụm (tránh "Điều 13" khớp trong "Điều 135")."""
    ch = s[:1] if dau else s[-1:]
    if not re.match(r"\w", ch):
        return ""
    return r"(?<!\w)" if dau else r"(?!\w)"


def _chuan(s: str | None) -> str | None:
    return None if s is None else s.replace("²", "2").replace("³", "3")


PUNCT = ",.;:"


def _don_dep(s: str) -> str:
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"[ \t]+([,.;:])", r"\1", s)
    return s.strip()


def ap_cum_tu(state: dict, op: dict) -> tuple[set[str], dict]:
    """Trả về (Điều bị chạm, ghi chú). Lỗi -> Loi."""
    if op["vi_tri"] == "TOAN_BO":
        locs = [{"dieu": s, "khoan": None, "diem": None, "ten": False} for s, a in state.items() if a["trang_thai"] != "bai_bo"]
        bat_buoc = False
    else:
        locs, bat_buoc = op["vi_tri"], True
    cum, moi, neo_cum = _chuan(op["cum"]), _chuan(op.get("cum_moi")), _chuan(op.get("neo_cum"))
    neo, tt = op["neo"], op["thao_tac"]
    touched, ghi_chu = set(), {"so_lan": 0}
    for v in locs:
        a = _lay_dieu(state, v["dieu"])
        units = _don_vi(a, v)
        if tt == "them" and neo in ("đầu", "cuối"):
            if not units:
                raise Loi("vị trí rỗng")
            o = units[0] if neo == "đầu" else units[-1]
            txt = o.get()
            if neo == "đầu":
                o.set(cum + ("" if cum[-1:] in "(" else " ") + txt)
                ghi_chu["chen_dau_cau"] = True   # chữ hoa đầu câu cũ giữ nguyên – cần đối chiếu
            else:
                m = re.search(r"[.;:]\s*$", txt)
                o.set((txt[:m.start()] if m else txt).rstrip() + ("" if cum[:1] in PUNCT else " ") + cum
                      + (m.group(0).strip() if m else ""))
                ghi_chu["chen_cuoi"] = True
            ghi_chu["so_lan"] += 1
            touched.add(v["dieu"])
            continue
        # các thao tác dựa trên mẫu
        if tt == "them":
            pat = _bien(neo_cum, True) + re.escape(neo_cum) + _bien(neo_cum, False)
            if neo == "sau":
                rep = lambda m: m.group(0) + ("" if cum[:1] in PUNCT else " ") + cum  # noqa: E731
            else:
                rep = lambda m: cum + ("" if cum[-1:] in "(" else " ") + m.group(0)  # noqa: E731
        else:
            target = _bien(cum, True) + re.escape(cum) + _bien(cum, False)
            if neo == "sau":
                # "Bỏ cụm từ X sau cụm từ Y": giữa Y và X có thể có dấu phẩy ("…dân sự, kinh tế, lao động")
                pat = rf"(?<={re.escape(neo_cum)})(?P<sep>[\s,;]*){target}"
            elif neo == "trước":
                pat = rf"{target}(?=[\s,;]*{re.escape(neo_cum)})"
            else:
                pat = target
            if tt == "thay":
                r = moi
                if cum[:1] in PUNCT and moi[:1] not in PUNCT:
                    r = " " + moi              # dấu "," -> từ "hoặc"
                keep_sep = neo == "sau"
                rep = lambda m, r=r, k=keep_sep: ((m.group("sep") or " ") if k and r[:1] not in PUNCT else "") + r  # noqa: E731
            else:
                rep = lambda m: ""  # noqa: E731
        flags = 0
        n_hit = sum(len(re.findall(pat, o.get())) for o in units)
        if n_hit == 0:
            # Văn bản sửa đổi đôi khi trích cụm từ khác chữ hoa/thường với bản gốc ("Ủy ban tư pháp" / "Ủy ban Tư pháp")
            n_hit = sum(len(re.findall(pat, o.get(), re.IGNORECASE)) for o in units)
            if n_hit:
                flags = re.IGNORECASE
                ghi_chu["khop_khong_phan_biet_hoa"] = True
        if n_hit == 0:
            raise Loi(f"không tìm thấy {'mốc' if tt == 'them' else 'cụm'} "
                      f"\"{(neo_cum if tt == 'them' else cum)[:50]}\" tại {_ten_vt(v)}")
        if tt == "them" and n_hit > 1:
            raise Loi(f"mốc \"{neo_cum[:50]}\" xuất hiện {n_hit} lần tại {_ten_vt(v)} – không biết chèn chỗ nào")
        for o in units:
            o.set(_don_dep(re.sub(pat, rep, o.get(), flags=flags)))
        ghi_chu["so_lan"] += n_hit
        touched.add(v["dieu"])
    if bat_buoc and not touched:
        raise Loi("không chạm vị trí nào")
    return touched, ghi_chu


def _ten_vt(v) -> str:
    s = "tên " if v["ten"] else ""
    s += f"điểm {v['diem']} " if v["diem"] else ""
    s += f"khoản {v['khoan']} " if v["khoan"] else ""
    return s + f"Điều {v['dieu']}"


# ------------------------------------------------------------------ dựng phiên bản
def _cung_vb(nhan: str | None, so_hieu: str) -> bool:
    """Nhãn văn bản bị sửa trong lenh_sua_doi ("100/2015/QH13" hoặc "ngoai:02/2018/NQ-HĐTP") khớp số hiệu."""
    return bool(nhan) and nhan.removeprefix("ngoai:") == so_hieu


def main() -> int:
    # Bộ luật gốc (Phần 1) + văn bản hướng dẫn (Phần 3): cùng được áp sửa đổi, dựng phiên bản, cắt chunk
    vb = {r["so_hieu"]: r for r in read_jsonl(TG / "goc_van_ban.jsonl") + read_jsonl(TG / "huong_dan_van_ban.jsonl")}
    base = defaultdict(dict)
    for r in read_jsonl(TG / "goc_dieu.jsonl") + read_jsonl(TG / "huong_dan_dieu.jsonl"):
        base[r["so_hieu"]][r["so_dieu"]] = {k: r[k] for k in ("so_dieu", "thu_tu", "tieu_de", "vi_tri", "doan_dan", "diem", "khoan", "trang_thai")}
    lenh = read_jsonl(TG / "lenh_sua_doi.jsonl")
    thu_tu_vb = {v: i for i, v in enumerate(dict.fromkeys(c["van_ban"] for c in lenh))}

    nhat_ky, dieu_rows, chunk_rows, loi = [], [], [], []
    tk = {}

    for sh, state0 in base.items():
        ngay0 = vb[sh]["ngay_hieu_luc"]
        # Gom thao tác nhắm bộ luật này
        viec = []    # (ngày, thứ tự, lệnh, op|None)
        for c in lenh:
            if c["loai"] in ("khung", "mau"):
                continue
            if c["loai"] == "cum_tu":
                for i, op in enumerate(c["cum_tu"]):
                    if _cung_vb(op["bo_luat"], sh):
                        viec.append((c["ngay_hieu_luc"], thu_tu_vb[c["van_ban"]], c["dong"], i, c, op))
            elif _cung_vb(c["bo_luat"], sh):
                viec.append((c["ngay_hieu_luc"], thu_tu_vb[c["van_ban"]], c["dong"], -1, c, None))
        viec.sort(key=lambda x: (x[0] or "9999", x[1], x[2], x[3]))

        state = copy.deepcopy(state0)
        lich_su = {s: [(ngay0, copy.deepcopy(a), [])] for s, a in state.items()}
        dates = sorted({x[0] for x in viec if x[0]})
        for d in dates:
            new = copy.deepcopy(state)
            cham = defaultdict(list)
            for ngay, _, _, i, c, op in [x for x in viec if x[0] == d]:
                ent = {"lenh_id": c["id"], "op": i, "van_ban": c["van_ban"], "bo_luat": sh, "ngay": d,
                       "loai": c["loai"], "cau_goc": c["cau_goc"]}
                if c["trang_thai"] != "ok":
                    ent.update(ket_qua="loi", ly_do=f"câu lệnh cần duyệt: {c['ly_do']}")
                    nhat_ky.append(ent)
                    continue
                trial = copy.deepcopy(new)
                try:
                    if op is None:
                        t = ap_cau_truc(trial, c)
                        gc = {}
                    else:
                        t, gc = ap_cum_tu(trial, op)
                        ent["thao_tac"] = {k: op[k] for k in ("thao_tac", "cum", "neo") if k in op} | {"cum_moi": op.get("cum_moi"), "neo_cum": op.get("neo_cum")}
                    new = trial
                    for s in t:
                        cham[s].append({"lenh_id": c["id"], "van_ban": c["van_ban"]})
                    ent.update(ket_qua="da_ap", dieu=sorted(t, key=_key_dieu), **({"ghi_chu": gc} if gc else {}))
                except Loi as e:
                    ent.update(ket_qua="loi", ly_do=str(e))
                nhat_ky.append(ent)
            for s, srcs in cham.items():
                if _hash_art(new.get(s)) != _hash_art(state.get(s)):
                    lich_su.setdefault(s, []).append((d, copy.deepcopy(new[s]), srcs))
            state = new

        # --- xuất phiên bản
        n_pb, n_ctua = 0, 0
        for s, hist in sorted(lich_su.items(), key=lambda kv: _key_dieu(kv[0])):
            did = f"{sh}#D{s}"
            for j, (vf, a, srcs) in enumerate(hist):
                vt_ = hist[j + 1][0] if j + 1 < len(hist) else None
                ctua = vt_ == vf
                n_ctua += ctua
                body = render_dieu_body(a)
                rec = {"dieu_id": did, "phien_ban_id": f"{did}@{vf}", "so_hieu": sh, **a,
                       "valid_from": vf, "valid_to": vt_, "chua_tung_ap_dung": ctua,
                       "nguon_thay_doi": [dict(t) for t in {tuple(x.items()) for x in srcs}],
                       "sha256": sha(f"Điều {s}. {a['tieu_de']}\n{body}")}
                dieu_rows.append(rec)
                n_pb += 1
        tk[sh] = {"so_phien_ban_dieu": n_pb, "so_dieu_co_thay_doi": sum(len(h) > 1 for h in lich_su.values()),
                             "phien_ban_chua_tung_ap_dung": n_ctua}

    # --- chunk theo phiên bản, gộp chunk không đổi chữ
    by_dieu = defaultdict(list)
    for r in dieu_rows:
        by_dieu[r["dieu_id"]].append(r)
    for did, vers in by_dieu.items():
        timeline = {}   # chunk_id -> list of records
        for r in vers:
            if r["chua_tung_ap_dung"] or r["trang_thai"] == "bai_bo":
                # Điều bãi bỏ: đóng mọi chunk đang mở
                for lst in timeline.values():
                    if lst[-1]["valid_to"] is None or lst[-1]["valid_to"] > r["valid_from"]:
                        lst[-1]["valid_to"] = r["valid_from"]
                continue
            v = vb[r["so_hieu"]]
            chs = chunk_dieu(v, r)
            # mọi dòng của Điều phải nằm trong ít nhất một chunk
            all_text = "\n".join(ch["text"] for ch in chs)
            loi += [f"{r['phien_ban_id']}: dòng bị mất khi cắt chunk: {line[:60]}"
                    for line in render_dieu_body(r).split("\n") if line.strip() and line not in all_text]
            ids_now = set()
            for ch in chs:
                h = sha(ch["text"])
                ids_now.add(ch["chunk_id"])
                lst = timeline.setdefault(ch["chunk_id"], [])
                if lst and lst[-1]["sha256"] == h and lst[-1]["valid_to"] in (None, r["valid_from"]):
                    lst[-1]["valid_to"] = r["valid_to"]           # cùng chữ -> kéo dài
                    continue
                if lst and (lst[-1]["valid_to"] is None or lst[-1]["valid_to"] > r["valid_from"]):
                    lst[-1]["valid_to"] = r["valid_from"]
                lst.append({"chunk_id": ch["chunk_id"], "phien_ban_id": f"{ch['chunk_id']}@{r['valid_from']}",
                            "dieu_id": did, "dieu_phien_ban_id": r["phien_ban_id"], "so_hieu": r["so_hieu"],
                            "nhom": v["nhom"], "loai_van_ban": v["loai"], "linh_vuc": v["linh_vuc"], "cap": ch["cap"],
                            "trich_dan": ch["trich_dan"], "text": ch["text"], "noi_dung": ch["noi_dung"],
                            "so_tu": ch["so_tu"], "valid_from": r["valid_from"], "valid_to": r["valid_to"],
                            "nguon_thay_doi": r["nguon_thay_doi"], "sha256": h,
                            "huong_dan_boi": [], "huong_dan_cho": []})
            # chunk của phiên bản trước không còn trong phiên bản này (vd. khoản bị bãi bỏ) -> đóng
            for cid, lst in timeline.items():
                if cid not in ids_now and (lst[-1]["valid_to"] is None or lst[-1]["valid_to"] > r["valid_from"]):
                    lst[-1]["valid_to"] = r["valid_from"]
        for lst in timeline.values():
            chunk_rows += [x for x in lst if x["valid_to"] != x["valid_from"]]

    # --- kiểm tra
    for rows, key in ((dieu_rows, "dieu_id"), (chunk_rows, "chunk_id")):
        by = defaultdict(list)
        for r in rows:
            if not r.get("chua_tung_ap_dung"):
                by[r[key]].append((r["valid_from"], r["valid_to"] or "9999-12-31"))
        for k, iv in by.items():
            iv.sort()
            for (a1, b1), (a2, _) in zip(iv, iv[1:]):
                if a2 < b1:
                    loi.append(f"{k}: [{a1},{b1}) chồng [{a2},…)")
    dup = [k for k, n in Counter(r["phien_ban_id"] for r in chunk_rows).items() if n > 1]
    loi += [f"trùng phien_ban_id chunk: {k}" for k in dup]

    if loi:
        print("  KIỂM TRA KHÔNG ĐẠT:", *loi[:20], sep="\n    ")
        return 1
    write_jsonl(TG / "dieu_phien_ban.jsonl", dieu_rows)
    write_jsonl(TG / "chunks_phien_ban.jsonl", chunk_rows)
    kq = Counter((e["bo_luat"], e["ket_qua"]) for e in nhat_ky)
    for sh, t in tk.items():
        if kq[(sh, "da_ap")] or kq[(sh, "loi")]:
            print(f"  {sh:<16} áp {kq[(sh, 'da_ap')]:>3} thao tác, lỗi {kq[(sh, 'loi')]}, "
                  f"{t['so_dieu_co_thay_doi']} Điều có thay đổi")
    for e in nhat_ky:
        if e["ket_qua"] == "loi":
            print(f"  CHƯA ÁP {e['bo_luat']} ← {e['van_ban']}: {e['ly_do'][:100]}")
    print(f"  {len(chunk_rows)} chunk theo phiên bản")
    return 0


if __name__ == "__main__":
    sys.exit(main())
