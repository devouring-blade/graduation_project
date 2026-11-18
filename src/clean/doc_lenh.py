"""Bước 3: đọc câu lệnh sửa đổi từ mọi văn bản trong sua_doi/ và lien_quan/.

Không mặc định văn bản nào sửa luật nào: mỗi câu lệnh tự xác định luật bị sửa từ chính câu
("… Điều 32 của Bộ luật Tố tụng dân sự số 92/2015/QH13 …") hoặc từ dòng phạm vi bao ngoài
("Điều 1. Sửa đổi, bổ sung một số điều của Bộ luật Hình sự", "1. Sửa đổi … của Luật X …:").

Mỗi câu lệnh -> một bản ghi trong data/processed/trung_gian/lenh_sua_doi.jsonl:
    id, van_ban, ngay_hieu_luc, bo_luat (số hiệu luật bị sửa, hoặc "ngoai:<tên>"),
    loai: sua | bo_sung | bai_bo | cum_tu | khung (dòng phạm vi, không tự sửa gì)
    vi_tri: [{dieu, khoan, diem, ten}], chuong: [...], noi_dung: [dòng] (nội dung trong ngoặc kép),
    cum_tu: [{thao_tac, cum, cum_moi, neo, neo_cum, vi_tri, bo_luat}]  (cho loai=cum_tu)
    cau_goc, trang_thai: ok | can_duyet, ly_do
Câu nào không hiểu chắc -> trang_thai can_duyet, không đoán.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from html_text import read_lines  # noqa: E402
from vi_tri import doc_vi_tri  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
TG = DATA / "processed" / "trung_gian"
CONFIG = ROOT / "config" / "sua_doi.json"

# ------------------------------------------------------------------ nhận diện luật
BO_LUAT = [  # (regex trên tên, số hiệu) – thứ tự quan trọng: "Tố tụng" trước
    (re.compile(r"Bộ luật\s+[Tt]ố tụng hình sự|101/2015/QH13"), "101/2015/QH13"),
    (re.compile(r"Bộ luật\s+[Tt]ố tụng dân sự|92/2015/QH13"), "92/2015/QH13"),
    (re.compile(r"Bộ luật\s+[Hh]ình sự|100/2015/QH13"), "100/2015/QH13"),
    (re.compile(r"Bộ luật\s+[Dd]ân sự|91/2015/QH13"), "91/2015/QH13"),
]
# Văn bản có số hiệu: "Luật Tổ chức Cơ quan điều tra hình sự số 99/2015/QH13", "Nghị quyết số 02/2018/NQ-HĐTP"
RE_LUAT_SO = re.compile(r"(Bộ luật|Luật|Pháp lệnh|Nghị quyết|Nghị định|Thông tư liên tịch|Thông tư)\b[^;:]{0,140}?\bsố\s+"
                        r"(\d+/\d{4}/[A-ZĐa-zđ0-9\-_]+)")
# Văn bản không ghi số: "của Luật Ngân sách nhà nước", "Luật Phá sản"
RE_LUAT_TEN = re.compile(r"(Bộ luật|Luật|Pháp lệnh)\s+(?!này\b)([A-ZĐ][^,;:()]{2,80})")


def nhan_luat(text: str) -> str | None:
    """Văn bản được nhắc ĐẦU TIÊN trong đoạn chữ. 4 bộ luật gốc -> số hiệu; văn bản khác -> 'ngoai:…'."""
    cands = []
    for rx, sh in BO_LUAT:
        m = rx.search(text)
        if m:
            cands.append((m.start(), sh))
    m = RE_LUAT_SO.search(text)
    if m:
        so = m.group(2)
        sh = next((s for _, s in BO_LUAT if s == so), None)
        cands.append((m.start(), sh or f"ngoai:{so}"))
    m = RE_LUAT_TEN.search(text)
    if m:
        cands.append((m.start() + 0.5, f"ngoai:{m.group(0)[:60]}"))   # thua BO_LUAT nếu cùng vị trí
    if not cands:
        return None
    return min(cands)[1]


# ------------------------------------------------------------------ câu lệnh
RE_MARK = re.compile(r"^(?:(?P<dieu>Điều\s+\d+[a-zđ]?\.)|(?P<k>\d+[a-zđ]?\.)|(?P<d>[a-zđ]\)))\s*")
# Động từ câu lệnh PHẢI đi kèm đối tượng sửa, để "Thay mặt…", "Thay đổi…", "Bỏ trốn…",
# "Bổ sung thông tin", "Sửa lỗi kỹ thuật" không bị coi là câu lệnh.
OBJ = r"(?:các\s+|một\s+số\s+|tên\s+|toàn\s+bộ\s+)?(?:điểm|khoản|Điều|điều|chương|Chương|mục|Mục|phần|Phần|từ|cụm\s+từ|dấu|đoạn|Phụ\s+lục|phụ\s+lục|Mẫu|mẫu|biểu\s+mẫu)\b"
RE_VERB = re.compile(
    r"^(?:Sửa đổi|Bổ sung|Bãi bỏ|Thay thế|Thay|Bỏ|Hủy bỏ|Huỷ bỏ)"
    r"(?:(?:\s*,\s*|\s+và\s+)(?:sửa đổi|bổ sung|bãi bỏ|thay thế|hủy bỏ|huỷ bỏ|bỏ))*"
    rf"\s+{OBJ}")
Q = r"[\"“”]([^\"“”]*)[\"“”]"
WORD = r"(?:các\s+)?(?:từ|cụm\s+từ|dấu|ký\s+tự|chữ)"
RE_OP = re.compile(
    rf"(?P<them>(?:Bổ sung\s+)?{WORD}\s+{Q}\s+vào\s+(?P<them_neo>đầu|cuối|sau|trước)(?:\s+{WORD}\s+{Q})?)"
    rf"|(?P<thay>(?:Thay thế\s+|Thay\s+)?{WORD}\s+{Q}\s+bằng\s+{WORD}\s+{Q}(?:\s+(?P<thay_neo>sau|trước)\s+{WORD}\s+{Q})?)"
    rf"|(?P<bo>(?:Bỏ\s+|Bãi bỏ\s+)?{WORD}\s+{Q}(?:\s+(?P<bo_neo>sau|trước)\s+{WORD}\s+{Q})?)"
)
RE_TOAN_BO = re.compile(r"(trong|tại|ở)\s+(toàn bộ|các điều,? khoản,? điểm của|toàn văn)", re.I)


def _strip_cua(text: str) -> tuple[str, str | None]:
    """Cắt phần "của <luật>…" khỏi cụm vị trí; trả về (cụm vị trí, luật)."""
    m = re.search(r"\s+(?:của|thuộc)\s+(?=(?:Bộ luật|Luật|Pháp lệnh|Nghị quyết|Nghị định))", text)
    if not m:
        return text, None
    return text[:m.start()], nhan_luat(text[m.end():])


def _split_top(text: str, sep: str = ";") -> list[str]:
    """Tách theo ';' nhưng không tách trong ngoặc kép."""
    out, buf, inq = [], [], False
    for ch in text:
        if ch in "\"“”":
            inq = (ch == "“") or (ch == '"' and not inq)
            if ch == "”":
                inq = False
        if ch == sep and not inq:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [x.strip() for x in out if x.strip()]


def doc_cum_tu(text: str, luat_mac_dinh: str | None, dieu_mac_dinh: str | None):
    """Câu lệnh sửa từ/cụm từ -> danh sách thao tác. Trả về (ops, lỗi)."""
    ops, last_op = [], None
    for clause in _split_top(text):
        found = []
        for m in RE_OP.finditer(clause):
            truoc = clause[:m.start()]
            co_dong_tu = bool(re.match(r"(Bổ sung|Thay thế|Thay|Bỏ|Bãi bỏ)\s", m.group(0)))
            # Cụm đứng sau "trước/sau/bằng/vào" là mốc hoặc giá trị mới, KHÔNG phải câu lệnh
            if re.search(r"(?:trước|sau|bằng|vào)\s*$", truoc):
                continue
            # 'bỏ' không có động từ chỉ hợp lệ khi thao tác trước cũng là 'bỏ'
            if m.group("bo") and not co_dong_tu and not (found and found[-1][1] == "bo"
                                                         or not found and last_op and last_op["thao_tac"] == "bo"):
                continue
            found.append((m, "them" if m.group("them") else "thay" if m.group("thay") else "bo"))
        # Mốc nối tiếp: "… trước cụm từ "A" tại điểm i, trước cụm từ "B" tại điểm m và trước cụm từ "C" tại điểm n"
        spans = [(m.start(), m.end()) for m, _ in found]
        for m in re.finditer(rf"(?<!\w)(?P<neo>trước|sau)\s+{WORD}\s+{Q}", clause):
            if not any(a <= m.start() < b for a, b in spans):
                found.append((m, "neo_tiep"))
        found.sort(key=lambda x: x[0].start())
        found = [m for m, _ in found]
        if not found:
            # Mệnh đề chỉ có vị trí (vd. "; điểm a khoản 3 Điều 23 của Luật Thủy lợi…") -> dùng thao tác trước
            if last_op is None:
                return None, f"không đọc được mệnh đề: {clause[:80]}"
            found_spans = [(None, 0)]
        else:
            found_spans = [(m, m.end()) for m in found]
        for i, (m, end) in enumerate(found_spans):
            nxt = found_spans[i + 1][0].start() if i + 1 < len(found_spans) else len(clause)
            loc_text = clause[end:nxt]
            if m is None:
                op = dict(last_op)
            elif "neo" in m.re.groupindex:
                if last_op is None or last_op.get("neo") not in ("trước", "sau"):
                    return None, f"mốc không gắn với thao tác nào: {m.group(0)[:60]}"
                op = dict(last_op)
                op.update(neo=m.group("neo"), neo_cum=re.findall(Q, m.group(0))[0])
            elif m.group("them"):
                g = m.group("them")
                cum = re.findall(Q, g)
                op = {"thao_tac": "them", "cum": cum[0], "neo": m.group("them_neo"),
                      "neo_cum": cum[1] if len(cum) > 1 else None}
                # "vào đầu điểm c khoản 2": vị trí nằm ngay sau 'đầu'
            elif m.group("thay"):
                cum = re.findall(Q, m.group("thay"))
                op = {"thao_tac": "thay", "cum": cum[0], "cum_moi": cum[1],
                      "neo": m.group("thay_neo"), "neo_cum": cum[2] if len(cum) > 2 else None}
            else:
                cum = re.findall(Q, m.group("bo"))
                op = {"thao_tac": "bo", "cum": cum[0], "neo": m.group("bo_neo"),
                      "neo_cum": cum[1] if len(cum) > 1 else None}
            last_op = {k: v for k, v in op.items()}
            loc_text = re.sub(r"^\s*(?:quy định\s+)?(?:tại|ở|trong)?\s*", "", loc_text)
            loc_part, luat = _strip_cua(loc_text)
            if RE_TOAN_BO.search(loc_text):
                op["vi_tri"] = "TOAN_BO"
            else:
                vt, _ = doc_vi_tri(loc_part)
                op["vi_tri"] = vt
            op["bo_luat"] = luat or luat_mac_dinh
            op["_loc_text"] = loc_text.strip()
            ops.append(op)
        # "Thay thế từ A bằng B và dấu "," bằng từ "hoặc" … tại khoản 1 Điều 285":
        # thao tác không có vị trí riêng (chỉ "và"/",") dùng chung vị trí của thao tác sau trong mệnh đề.
        clause_ops = ops[len(ops) - len(found_spans):]
        for a, b in zip(reversed(clause_ops[:-1]), reversed(clause_ops[1:])):
            if not a["vi_tri"] and re.fullmatch(r"[\s,]*(?:và)?[\s,]*", a["_loc_text"]):
                a["vi_tri"] = [dict(v) for v in b["vi_tri"]] if b["vi_tri"] != "TOAN_BO" else "TOAN_BO"
                a["bo_luat"] = b["bo_luat"]
    # "Thay thế cụm từ A bằng B; cụm từ C bằng D tại ví dụ khoản 3 Điều 3": vế không có vị trí
    # (kể cả khác mệnh đề) dùng chung vị trí của thao tác sau gần nhất
    for i, a in enumerate(ops):
        if not a["vi_tri"] and not a["_loc_text"].strip(" ,;và"):
            b = next((b for b in ops[i + 1:] if b["vi_tri"]), None)
            if b:
                a["vi_tri"] = [dict(v) for v in b["vi_tri"]] if b["vi_tri"] != "TOAN_BO" else "TOAN_BO"
                a["bo_luat"] = b["bo_luat"]
    # Vị trí thiếu Điều: mượn Điều của vị trí sau gần nhất (trong cùng câu lệnh), hoặc Điều mặc định
    flat = [(o, v) for o in ops if o["vi_tri"] != "TOAN_BO" for v in o["vi_tri"]]
    for i, (o, v) in enumerate(flat):
        if v["dieu"] is None:
            w = next((w for _, w in flat[i + 1:] if w["dieu"]), None)
            v["dieu"] = w["dieu"] if w else dieu_mac_dinh
            # "tại điểm a và cụm từ … tại điểm b khoản 3 Điều 369": điểm a mượn cả khoản 3
            if v["diem"] and not v["khoan"] and w and w["khoan"]:
                v["khoan"] = w["khoan"]
    for o in ops:
        if o["vi_tri"] != "TOAN_BO" and (not o["vi_tri"] or any(v["dieu"] is None for v in o["vi_tri"])):
            return ops, f"thao tác '{o['cum'][:30]}' thiếu vị trí: {o['_loc_text'][:80]}"
    return ops, None


# ------------------------------------------------------------------ văn bản
RE_HIEU_LUC = re.compile(r"(?:Luật|Bộ luật|Nghị quyết|Nghị định|Pháp lệnh|Thông tư liên tịch|Thông tư) này\b[^.]{0,200}?"
                         r"có hiệu lực(?: thi hành)?(?: kể)? từ ngày\s+"
                         r"(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})(?P<sau>[^.]*)")


def _quote_start(t: str) -> bool:
    return t[:1] in "\"“"


def _quote_end(t: str) -> bool:
    return bool(re.search(r"[\"”]\s*[.;,]*\s*$", t))


def _is_cmd(t: str) -> bool:
    m = RE_MARK.match(t)
    rest = t[m.end():] if m else t
    return bool(RE_VERB.match(rest))


def doc_van_ban(path: Path, so_hieu: str, cfg: dict, nhom: str = "sua_doi") -> tuple[list[dict], dict]:
    lines = [ln.text for ln in read_lines(path)]
    n = len(lines)
    in_quote = [False] * n
    content_of: dict[int, list[str]] = {}

    # --- 1. nội dung trong ngoặc kép, gắn vào câu lệnh đứng trước
    i = 0
    while i < n:
        t = lines[i]
        inline = re.search(r"như sau\s*:?\s*[\"“]", t)
        opens = re.search(r"(:|như sau)\s*$", t.rstrip())
        if _is_cmd(t) and (inline or (opens and i + 1 < n and _quote_start(lines[i + 1]))):
            start = i if inline else i + 1
            buf, j = [], start
            first = lines[start][inline.end() - 1:] if inline else lines[start]
            while j < n:
                cur = first if j == start else lines[j]
                buf.append(cur)
                if j > i:
                    in_quote[j] = True
                nxt = lines[j + 1] if j + 1 < n else ""
                # Hết nội dung: dòng kết thúc bằng ngoặc đóng VÀ dòng sau là câu lệnh mới / Điều mới / hết văn bản
                if _quote_end(cur) and (j + 1 >= n or _is_cmd(nxt) or re.match(r"^Điều\s+\d+[a-zđ]?\.", nxt)
                                        or re.match(r"^(?:\d+\.\s*)?(?:Luật|Bộ luật|Nghị quyết|Nghị định|Pháp lệnh) này\b", nxt)):
                    break
                j += 1
            # bỏ ngoặc mở/đóng
            if buf:
                buf[0] = re.sub(r"^[\"“]", "", buf[0])
                buf[-1] = re.sub(r"[\"”]\s*[.;,]*\s*$", "", buf[-1])
            content_of[i] = [x for x in buf if x.strip()]
            i = j + 1
            continue
        i += 1

    # --- 2. ngày hiệu lực
    hl = None
    for k, t in enumerate(lines):
        if in_quote[k]:
            continue
        m = RE_HIEU_LUC.search(t)
        if m:
            d, mo, y = (int(x) for x in m.groups()[:3])
            hl = {"ngay": f"{y:04d}-{mo:02d}-{d:02d}", "cau": t.strip()}
            break
    meta = {"so_hieu": so_hieu, "hieu_luc": hl}
    o = cfg.get(so_hieu, {})
    ngay = o.get("ngay_hieu_luc") or (hl["ngay"] if hl else None)

    # --- 3. câu lệnh, theo cấp: 0 = Điều của văn bản sửa, 1 = "N.", 2 = "a)"
    scope = {0: (None, None), 1: (None, None), 2: (None, None)}   # cấp -> (luật, Điều mặc định)
    out = []
    for k, t in enumerate(lines):
        if in_quote[k]:
            continue
        m = RE_MARK.match(t)
        lvl = 0 if (m and m.group("dieu")) else 1 if (m and m.group("k")) else 2 if (m and m.group("d")) else None
        rest = t[m.end():] if m else t
        if lvl is not None:
            for L in range(lvl, 3):
                scope[L] = (None, None)
        # phạm vi kế thừa
        luat_cha, dieu_cha = None, None
        for L in range(0, (lvl if lvl is not None else 3)):
            if scope[L][0]:
                luat_cha = scope[L][0]
            if scope[L][1]:
                dieu_cha = scope[L][1]
        if not RE_VERB.match(rest):
            # Tiêu đề Điều có thể khai báo phạm vi ("Điều 1. Sửa đổi … của Bộ luật Hình sự")
            continue
        # Luật bị sửa = văn bản được nhắc đầu tiên trong câu (trước phần nội dung trong ngoặc kép)
        luat_cau = nhan_luat(re.split(r"[\"“]", rest)[0])
        if luat_cau is None and RE_OP.search(rest):
            # Câu sửa cụm từ ghi tên luật sau phần ngoặc kép ("Thay thế cụm từ "…" bằng … tại … của Luật X")
            luat_cau = nhan_luat(re.sub(Q, " ", rest))
        luat = luat_cau or luat_cha
        if luat is None and nhom == "lien_quan":
            # Luật khác: chỉ phần "sửa đổi luật có liên quan" mới là câu lệnh; câu thường của luật đó thì bỏ qua
            continue
        rid = f"{so_hieu}#L{k}"
        base = {"id": rid, "van_ban": so_hieu, "ngay_hieu_luc": ngay, "dong": k, "cap": lvl,
                "cau_goc": t, "bo_luat": luat, "trang_thai": "ok", "ly_do": None}

        # Thay/bỏ biểu mẫu kèm theo văn bản: biểu mẫu không nằm trong dữ liệu -> ghi nhận, không áp
        if re.match(r"^(?:Thay thế|Bãi bỏ|Bỏ|Bổ sung|Sửa đổi)[^.:]*?\b(?:mẫu số|Mẫu số|biểu mẫu|một số mẫu)", rest):
            out.append({**base, "loai": "mau"})
            continue
        has_content = k in content_of
        phrase = bool(RE_OP.search(rest)) and not has_content
        # Điều mặc định cho câu lệnh con: "Sửa đổi, bổ sung một số khoản của Điều 123 …" / "Sửa đổi, bổ sung Điều 3 như sau:" (khung)
        head = re.split(r"\s+như sau|\s+(?:của|thuộc)\s+(?=(?:Bộ luật|Luật|Pháp lệnh|Nghị quyết|Nghị định))", rest)[0]
        is_khung = (bool(re.search(r"một số|các điều,? khoản|sau đây", head)) and not has_content and not phrase) \
            or (lvl == 0 and not has_content)          # tiêu đề Điều của văn bản sửa chỉ là khung
        vt, chuong = doc_vi_tri(head)
        dieu_khung = vt[0]["dieu"] if (len({v["dieu"] for v in vt}) == 1 and vt and vt[0]["dieu"]) else None
        if lvl is not None:
            scope[lvl] = (luat_cau or luat, dieu_khung or dieu_cha)

        if is_khung or (not has_content and not phrase and rest.rstrip().endswith(":")):
            out.append({**base, "loai": "khung", "vi_tri": vt, "chuong": chuong})
            continue
        if phrase:
            ops, err = doc_cum_tu(rest, luat, dieu_khung or dieu_cha)
            rec = {**base, "loai": "cum_tu", "cum_tu": ops or []}
            if err:
                rec.update(trang_thai="can_duyet", ly_do=err)
            out.append(rec)
            continue
        # câu lệnh cấu trúc
        loai = ("bai_bo" if re.match(r"^(Bãi bỏ|Bỏ|Hủy bỏ|Huỷ bỏ)", rest)
                else "bo_sung" if re.match(r"^Bổ sung", rest) else "sua")
        if loai == "bo_sung" and re.search(r"\s+vào\s+", head):
            # "Bổ sung điểm p vào sau điểm o khoản 1": đích = điểm p; phần sau "vào" chỉ chỗ chứa/chỗ chèn
            moi, cho = re.split(r"\s+vào\s+", head, maxsplit=1)
            vt, chuong = doc_vi_tri(moi)
            cv, _ = doc_vi_tri(cho)
            c0 = cv[-1] if cv else {}
            for v in vt:
                if v["diem"] and not v["khoan"]:
                    v["khoan"] = c0.get("khoan")
                if v["dieu"] is None:
                    v["dieu"] = c0.get("dieu")
        for v in vt:
            if v["dieu"] is None:
                v["dieu"] = dieu_cha
        rec = {**base, "loai": loai, "vi_tri": vt, "chuong": chuong,
               "noi_dung": content_of.get(k, [])}
        if loai in ("sua", "bo_sung") and not rec["noi_dung"]:
            rec.update(trang_thai="can_duyet", ly_do="câu lệnh sửa/bổ sung nhưng không tìm thấy nội dung trong ngoặc kép")
        elif not vt and not chuong:
            rec.update(trang_thai="can_duyet", ly_do="không đọc được vị trí")
        elif any(v["dieu"] is None for v in vt):
            rec.update(trang_thai="can_duyet", ly_do="vị trí thiếu Điều")
        out.append(rec)

    if not ngay:
        for r in out:
            r.update(trang_thai="can_duyet", ly_do=(r["ly_do"] or "") + " | văn bản chưa có ngày hiệu lực")
    return out, meta


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    rows = [json.loads(x) for x in (DATA / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    all_cmd, n_vb = [], 0
    for r in rows:
        if r["nhom"] not in ("sua_doi", "lien_quan"):
            continue
        cmds, _ = doc_van_ban(DATA / r["file"], r["so_hieu"], cfg, r["nhom"])
        all_cmd += cmds
        n_vb += 1
    TG.mkdir(parents=True, exist_ok=True)
    with (TG / "lenh_sua_doi.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for c in all_cmd:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  {len(all_cmd)} câu lệnh từ {n_vb} văn bản sửa đổi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
