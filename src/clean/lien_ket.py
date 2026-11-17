"""Bước 5: liên kết hướng dẫn <-> Điều luật, xuất kết quả cuối.

Đơn vị đưa cho agent là CẢ MỘT ĐIỀU (luật hoặc hướng dẫn), kèm liên kết hai chiều; chunk chỉ để tìm kiếm
và luôn trỏ về Điều cha.

Liên kết lấy từ chữ của văn bản hướng dẫn (không đoán):
    - nguon "dan_chieu": đoạn hướng dẫn nêu rõ "… điểm b khoản 1 Điều 51 của Bộ luật Hình sự", "Điều 65 BLHS",
      "Tội … (Điều 248)".
    - nguon "trich_yeu": tên văn bản nêu Điều ("Hướng dẫn áp dụng Điều 65 của Bộ luật Hình sự") -> mọi đoạn
      của văn bản đó hướng dẫn Điều này.
    - trang_thai "khop" / "viet_cho_ban_cu": Điều luật có (hoặc không) phiên bản mới sau ngày hướng dẫn có hiệu lực.

Kết quả cuối (data/processed/):
    dieu_luat.jsonl        mỗi dòng một phiên bản Điều luật hoàn chỉnh + huong_dan (mọi Điều hướng dẫn liên quan,
                           ghi rõ Khoản/Điểm luật được hướng dẫn và chỗ hướng dẫn)
    huong_dan.jsonl        mỗi dòng một phiên bản Điều của văn bản hướng dẫn hoàn chỉnh + huong_dan_cho
    chunk_luat.jsonl       chunk tìm kiếm cắt từ Điều luật; dieu_id = Điều cha
    chunk_huong_dan.jsonl  chunk tìm kiếm cắt từ hướng dẫn; dieu_luat = các Điều luật mà đoạn này hướng dẫn
    van_ban.jsonl          thông tin mọi văn bản; thong_ke.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_goc import read_jsonl, write_jsonl  # noqa: E402
from cau_truc import render_dieu_body  # noqa: E402
from chunking import _header, _trich_dan  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed"
TG = OUT / "trung_gian"
GOC = ("91/2015/QH13", "92/2015/QH13", "100/2015/QH13", "101/2015/QH13")

D = r"[a-zđ]"
N = r"\d+[a-zđ]?"
SEP = r"(?:\s*,\s*|\s*,?\s*(?:và|hoặc)\s+)"
LD = rf"{D}(?:{SEP}(?:điểm\s+)?{D}(?!\w))*"
LK = rf"\d+(?:{SEP}(?:khoản\s+)?\d+(?!\w))*"
LN = rf"{N}(?:{SEP}(?:Điều\s+)?{N}(?!\w))*"
RE_REF = re.compile(
    r"(?<!\w)(?=(?:các\s+)?(?:điểm|khoản|Điều|điều)\s)"
    rf"(?:(?:các\s+)?điểm\s+(?:từ\s+điểm\s+(?P<d1>{D})\s+đến\s+điểm\s+(?P<d2>{D})|(?P<d>{LD}))(?!\w)\s*,?\s*)?"
    rf"(?:(?:của\s+)?(?:các\s+)?khoản\s+(?:từ\s+khoản\s+(?P<k1>\d+)\s+đến\s+khoản\s+(?P<k2>\d+)|(?P<k>{LK}))(?!\w)\s*,?\s*)?"
    rf"(?:(?:của\s+)?(?P<cac>các\s+)?(?:Điều|điều)\s+(?:từ\s+Điều\s+(?P<n1>\d+)\s+đến\s+Điều\s+(?P<n2>\d+)|(?P<n>{LN}))(?!\w))"
    r"(?=(?P<tail>[^;:()]{0,60}))"          # chỉ nhìn trước, không nuốt cụm sau
)
BO_LUAT = [(r"(?:Bộ\s+luật\s+tố\s+tụng\s+hình\s+sự|BLTTHS)", "101/2015/QH13"),
           (r"(?:Bộ\s+luật\s+tố\s+tụng\s+dân\s+sự|BLTTDS)", "92/2015/QH13"),
           (r"(?:Bộ\s+luật\s+hình\s+sự|BLHS)", "100/2015/QH13"),
           (r"(?:Bộ\s+luật\s+dân\s+sự|BLDS)", "91/2015/QH13")]
DIEM_ORDER = "abcdđeghiklmnopqrstuvxy"


def _list(s: str) -> list[str]:
    parts = re.split(r"\s*,\s*|\s*,?\s*(?:và|hoặc)\s+", s.strip())
    return [re.sub(r"^(?:điểm|khoản|Điều)\s+", "", x) for x in parts if x]


def luat_o_duoi(tail: str) -> str | None:
    """Bộ luật gốc nêu ngay sau cụm vị trí ("… của Bộ luật Hình sự", "… BLHS năm 2015"). Năm khác 2015 -> None."""
    for rx, sh in BO_LUAT:
        m = re.match(rf"\s*,?\s*(?:(?:của|tại|thuộc|trong)\s+)?{rx}(?P<sau>[^,;.]{{0,30}})", tail, re.I)
        if m:
            nam = re.search(r"năm\s+(\d{4})|số\s+\d+/(\d{4})", m.group("sau"))
            if nam and (nam.group(1) or nam.group(2)) != "2015":
                return None
            return sh
    return None


def dan_chieu(text: str) -> list[tuple[str, str, str | None, str | None]]:
    """Các (bộ luật, Điều, Khoản, Điểm) được nêu rõ trong đoạn chữ."""
    out, cho = [], []        # cho: cụm chưa có bộ luật, chờ cụm sau ("khoản 5 Điều 131, … Điều 141 Bộ luật …")
    for m in RE_REF.finditer(text):
        g = m.groupdict()
        sh = luat_o_duoi(g["tail"] or "")
        if not sh:
            cho = cho + [g] if re.match(r"\s*(?:,|và\b|hoặc\b)", g["tail"] or "") else []
            continue
        for g0 in cho + [g]:
            out += _mo_rong(sh, g0)
        cho = []
    return out


def _mo_rong(sh: str, g: dict) -> list[tuple]:
    """Một cụm vị trí -> các (bộ luật, Điều, Khoản, Điểm). "khoản 2 Điều 5 và Điều 7": khoản chỉ thuộc
    Điều đầu; "khoản 1 các điều 134, 135": khoản thuộc từng Điều."""
    ns = [str(x) for x in range(int(g["n1"]), int(g["n2"]) + 1)] if g["n1"] else _list(g["n"])
    ks = ([str(x) for x in range(int(g["k1"]), int(g["k2"]) + 1)] if g["k1"]
          else _list(g["k"]) if g["k"] else [None])
    ps = (list(DIEM_ORDER[DIEM_ORDER.index(g["d1"]):DIEM_ORDER.index(g["d2"]) + 1]) if g["d1"]
          else _list(g["d"]) if g["d"] else [None])
    out = []
    for i, n in enumerate(ns):
        if i == 0 or g["cac"]:
            out += [(sh, n, k, p) for k in ks for p in ps]
        else:
            out.append((sh, n, None, None))
    return out


def _giao(a: dict, b: dict) -> bool:
    """Hai khoảng hiệu lực [valid_from, valid_to) giao nhau."""
    return (a["valid_to"] is None or b["valid_from"] < a["valid_to"]) and \
           (b["valid_to"] is None or a["valid_from"] < b["valid_to"])


def _dieu(vb: dict, r: dict) -> dict:
    """Bản ghi Điều hoàn chỉnh (luật hoặc hướng dẫn) từ một phiên bản Điều."""
    body = render_dieu_body(r) if r["trang_thai"] == "hieu_luc" else "(Điều này đã bị bãi bỏ)"
    return {"phien_ban_id": r["phien_ban_id"], "dieu_id": r["dieu_id"], "so_hieu": r["so_hieu"],
            "so_dieu": r["so_dieu"], "tieu_de": r["tieu_de"], "trich_dan": _trich_dan(vb, r["so_dieu"]),
            "ten_van_ban": vb["ten"], "text": _header(vb, r) + "\n" + body,
            "trang_thai": r["trang_thai"], "valid_from": r["valid_from"], "valid_to": r["valid_to"],
            "nguon_thay_doi": r["nguon_thay_doi"], "url": vb.get("url")}


def main() -> int:
    vb_goc = read_jsonl(TG / "goc_van_ban.jsonl")
    vb_hd = read_jsonl(TG / "huong_dan_van_ban.jsonl")
    vb = {r["so_hieu"]: r for r in vb_goc + vb_hd}
    chunks = read_jsonl(TG / "chunks_phien_ban.jsonl")
    dieu_pb = [r for r in read_jsonl(TG / "dieu_phien_ban.jsonl") if not r["chua_tung_ap_dung"]]
    luat_pb = defaultdict(list)            # dieu_id luật -> các phiên bản
    for r in dieu_pb:
        if r["so_hieu"] in GOC:
            luat_pb[r["dieu_id"]].append(r)

    def trang_thai(dieu_id: str, ref: dict) -> str:
        """Điều luật có phiên bản mới bắt đầu sau ngày hướng dẫn có hiệu lực (khi hướng dẫn còn hiệu lực)?"""
        doi = any(v["valid_from"] > ref["valid_from"] and (ref["valid_to"] is None or v["valid_from"] < ref["valid_to"])
                  for v in luat_pb[dieu_id])
        return "viet_cho_ban_cu" if doi else "khop"

    # 1) liên kết ở mức chunk hướng dẫn (chỗ nêu Điều luật)
    for c in chunks:
        if c["nhom"] != "huong_dan":
            continue
        v = vb[c["so_hieu"]]
        links = []
        so_dieu_trich_yeu = len({(sh, n) for sh, n, _, _ in dan_chieu(v["trich_yeu"])})
        for nguon, text in (("dan_chieu", c["noi_dung"]), ("trich_yeu", v["trich_yeu"])):
            # Tên văn bản nêu MỘT Điều (NQ 02/2018 -> Điều 65): mọi đoạn đều hướng dẫn Điều đó.
            # Tên nêu NHIỀU Điều (NQ 04/2025 -> Điều 51, 52): chỉ dùng cho đoạn không tự nêu Điều nào.
            if nguon == "trich_yeu" and so_dieu_trich_yeu > 1 and links:
                continue
            refs = dan_chieu(text)
            # Văn bản hướng dẫn BLHS ghi tội kèm số Điều trong ngoặc: "Tội sản xuất trái phép chất ma túy (Điều 248)"
            if "100/2015/QH13" in v["huong_dan_bo_luat"]:
                refs += [("100/2015/QH13", m.group(1), None, None)
                         for m in re.finditer(r"\bTội\s[^()]{3,150}?\(\s*(?:quy định tại\s+)?Điều\s+(\d+[a-zđ]?)\s*\)", text)]
            for sh, n, k, p in dict.fromkeys(refs):
                did = f"{sh}#D{n}"
                if did not in luat_pb or any(l["dieu_id"] == did and l["khoan"] in (k, None) for l in links):
                    continue
                links.append({"dieu_id": did, "khoan": k, "diem": p, "nguon": nguon})
        c["lien_ket"] = links

    # 2) Điều hướng dẫn hoàn chỉnh: gom liên kết của các chunk thuộc Điều đó (cùng thời gian)
    chunk_by_dieu = defaultdict(list)
    for c in chunks:
        chunk_by_dieu[c["dieu_id"]].append(c)
    huong_dan = []
    for r in dieu_pb:
        if r["so_hieu"] in GOC:
            continue
        rec = _dieu(vb[r["so_hieu"]], r)
        cho = []
        for c in chunk_by_dieu[r["dieu_id"]]:
            if not _giao(c, r):
                continue
            for l in c["lien_ket"]:
                e = {**l, "cho_huong_dan": c["trich_dan"], "chunk_id": c["chunk_id"],
                     "trang_thai": trang_thai(l["dieu_id"], r)}
                if e not in cho:
                    cho.append(e)
        rec["huong_dan_cho"] = cho
        huong_dan.append(rec)

    # 3) Điều luật hoàn chỉnh: mọi Điều hướng dẫn có liên kết tới Điều này, khi hai khoảng hiệu lực giao nhau
    hd_by_luat = defaultdict(list)
    for h in huong_dan:
        for l in h["huong_dan_cho"]:
            hd_by_luat[l["dieu_id"]].append((h, l))
    dieu_luat = []
    for r in dieu_pb:
        if r["so_hieu"] not in GOC:
            continue
        rec = _dieu(vb[r["so_hieu"]], r)
        nhom = {}
        for h, l in hd_by_luat[r["dieu_id"]]:
            if not _giao(h, r):
                continue
            g = nhom.setdefault(h["phien_ban_id"], {
                "huong_dan_id": h["phien_ban_id"], "so_hieu": h["so_hieu"], "trich_dan": h["trich_dan"],
                "valid_from": h["valid_from"], "valid_to": h["valid_to"],
                "trang_thai": "viet_cho_ban_cu" if r["valid_from"] > h["valid_from"] else "khop", "chi_tiet": []})
            ct = {"khoan": l["khoan"], "diem": l["diem"], "cho_huong_dan": l["cho_huong_dan"], "nguon": l["nguon"]}
            if ct not in g["chi_tiet"]:
                g["chi_tiet"].append(ct)
        rec["huong_dan"] = list(nhom.values())
        dieu_luat.append(rec)

    # 4) chunk tìm kiếm
    giu = ("chunk_id", "phien_ban_id", "dieu_id", "so_hieu", "cap", "trich_dan", "text", "so_tu", "valid_from", "valid_to")
    chunk_luat = [{k: c[k] for k in giu} for c in chunks if c["nhom"] == "goc"]
    chunk_hd = [{**{k: c[k] for k in giu}, "dieu_luat": [{k: l[k] for k in ("dieu_id", "khoan", "diem")} for l in c["lien_ket"]]}
                for c in chunks if c["nhom"] == "huong_dan"]

    write_jsonl(OUT / "dieu_luat.jsonl", dieu_luat)
    write_jsonl(OUT / "huong_dan.jsonl", huong_dan)
    write_jsonl(OUT / "chunk_luat.jsonl", chunk_luat)
    write_jsonl(OUT / "chunk_huong_dan.jsonl", chunk_hd)
    write_jsonl(OUT / "van_ban.jsonl", vb_goc + vb_hd)
    nk = read_jsonl(TG / "ap_lenh_nhat_ky.jsonl")
    tk = {"dieu_luat": len(dieu_luat), "dieu_luat_dang_hieu_luc": sum(r["valid_to"] is None for r in dieu_luat),
          "dieu_luat_co_huong_dan": sum(bool(r["huong_dan"]) for r in dieu_luat),
          "huong_dan": len(huong_dan), "huong_dan_co_lien_ket": sum(bool(r["huong_dan_cho"]) for r in huong_dan),
          "chunk_luat": len(chunk_luat), "chunk_huong_dan": len(chunk_hd),
          "chunk_huong_dan_co_lien_ket": sum(bool(c["dieu_luat"]) for c in chunk_hd),
          "van_ban_huong_dan": len(vb_hd),
          "thao_tac_sua_doi_da_ap": sum(e["ket_qua"] == "da_ap" for e in nk),
          "thao_tac_sua_doi_chua_ap": sum(e["ket_qua"] == "loi" for e in nk)}
    (OUT / "thong_ke.json").write_text(json.dumps(tk, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  dieu_luat {tk['dieu_luat']} ({tk['dieu_luat_co_huong_dan']} có hướng dẫn) | huong_dan {tk['huong_dan']} "
          f"({tk['huong_dan_co_lien_ket']} có liên kết) | chunk_luat {tk['chunk_luat']} | chunk_huong_dan {tk['chunk_huong_dan']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
