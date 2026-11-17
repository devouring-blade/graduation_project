"""Bước 5: liên kết hai chiều văn bản hướng dẫn <-> Điều luật, xuất kết quả cuối.

Chunk hướng dẫn: huong_dan_cho = [{dieu_id, khoan, diem, dieu_phien_ban_id, trang_thai, nguon}]
    - nguon "dan_chieu": chunk nêu rõ "… Điều 65 của Bộ luật Hình sự", "Điều 65 BLHS", "Tội … (Điều 248)".
    - nguon "trich_yeu": trích yếu văn bản nêu Điều ("Hướng dẫn áp dụng Điều 65 của Bộ luật Hình sự")
      -> gắn cho mọi chunk của văn bản đó.
    - trang_thai "khop": Điều chưa đổi kể từ khi hướng dẫn có hiệu lực; "viet_cho_ban_cu": Điều có phiên
      bản mới bắt đầu sau ngày hướng dẫn có hiệu lực (khi hướng dẫn còn hiệu lực).
    - Chunk không nêu Điều nào và văn bản có trích yếu chung chung -> huong_dan_cho rỗng.
Chunk Điều luật: huong_dan_boi = [{so_hieu, chunk_id, phien_ban_id, trang_thai}] – gắn vào chunk của đúng
    Điều (đúng Khoản nếu nêu) khi hai khoảng hiệu lực giao nhau.

Kết quả cuối (data/processed/):
    corpus_luat.jsonl        chunk Điều luật – kho dùng để tìm kiếm
    corpus_huong_dan.jsonl   chunk hướng dẫn – tìm phụ / tra theo mã từ huong_dan_boi
    huong_dan_toan_van.jsonl toàn văn từng văn bản hướng dẫn theo phiên bản [valid_from, valid_to) –
                             đưa cho agent khi đã có Điều luật (tra bằng so_hieu + ngày)
    van_ban.jsonl            thông tin mọi văn bản trong corpus
    thong_ke.json
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


def toan_van(vb: dict, dieu_rows: list[dict]) -> list[dict]:
    """Toàn văn một văn bản hướng dẫn cho mỗi khoảng thời gian mà nội dung không đổi."""
    rows = [r for r in dieu_rows if not r["chua_tung_ap_dung"]]
    moc = sorted({r["valid_from"] for r in rows} | {r["valid_to"] for r in rows if r["valid_to"]})
    out = []
    for i, a in enumerate(moc):
        b = moc[i + 1] if i + 1 < len(moc) else None
        hl = sorted((r for r in rows if r["trang_thai"] == "hieu_luc" and r["valid_from"] <= a
                     and (r["valid_to"] is None or a < r["valid_to"])), key=lambda r: r["thu_tu"])
        if not hl:
            continue
        text = vb["ten"] + "\n\n" + "\n\n".join(
            f"Điều {r['so_dieu']}. {r['tieu_de']}".rstrip(". ") + "\n" + render_dieu_body(r) for r in hl)
        if out and out[-1]["text"] == text:
            out[-1]["valid_to"] = b
            continue
        out.append({"phien_ban_id": f"{vb['so_hieu']}@{a}", "so_hieu": vb["so_hieu"], "ten": vb["ten"],
                    "ten_trich_dan": vb["ten_trich_dan"], "loai": vb["loai"],
                    "huong_dan_bo_luat": vb["huong_dan_bo_luat"], "valid_from": a, "valid_to": b,
                    "so_dieu": len(hl), "so_tu": len(text.split()), "text": text})
    return out


def main() -> int:
    vb_goc = read_jsonl(TG / "goc_van_ban.jsonl")
    vb_hd = read_jsonl(TG / "huong_dan_van_ban.jsonl")
    vb = {r["so_hieu"]: r for r in vb_hd}
    chunks = read_jsonl(TG / "chunks_phien_ban.jsonl")
    dieu_pb = read_jsonl(TG / "dieu_phien_ban.jsonl")
    versions = defaultdict(list)          # dieu_id -> [(valid_from, valid_to, phien_ban_id)] của bộ luật gốc
    for r in dieu_pb:
        if r["so_hieu"] in GOC and not r["chua_tung_ap_dung"]:
            versions[r["dieu_id"]].append((r["valid_from"], r["valid_to"], r["phien_ban_id"]))
    for v in versions.values():
        v.sort()

    def lien_ket(sh, n, k, p, gf, gt, nguon):
        did = f"{sh}#D{n}"
        vs = versions.get(did)
        if not vs:
            return None
        at = next((v for v in vs if v[0] <= gf and (v[1] is None or gf < v[1])), None)
        doi_sau = any(v[0] > gf and (gt is None or v[0] < gt) for v in vs)
        return {"dieu_id": did, "khoan": k, "diem": p, "dieu_phien_ban_id": at[2] if at else None,
                "trang_thai": "viet_cho_ban_cu" if doi_sau else "khop", "nguon": nguon}

    tk = Counter()
    for c in chunks:
        if c["nhom"] != "huong_dan":
            continue
        v = vb[c["so_hieu"]]
        links = []
        for nguon, text in (("dan_chieu", c["noi_dung"]), ("trich_yeu", v["trich_yeu"])):
            refs = dan_chieu(text)
            # Văn bản hướng dẫn BLHS ghi tội kèm số Điều trong ngoặc: "Tội sản xuất trái phép chất ma túy (Điều 248)"
            if "100/2015/QH13" in v["huong_dan_bo_luat"]:
                refs += [("100/2015/QH13", m.group(1), None, None)
                         for m in re.finditer(r"\bTội\s[^()]{3,150}?\(\s*(?:quy định tại\s+)?Điều\s+(\d+[a-zđ]?)\s*\)", text)]
            for sh, n, k, p in dict.fromkeys(refs):
                if any(l["dieu_id"] == f"{sh}#D{n}" and l["khoan"] in (k, None) for l in links):
                    continue
                l = lien_ket(sh, n, k, p, c["valid_from"], c["valid_to"], nguon)
                if l:
                    links.append(l)
        c["huong_dan_cho"] = links
        tk["chunk_huong_dan_co_lien_ket"] += bool(links)

    # chiều ngược: gắn vào chunk Điều luật
    by_dieu = defaultdict(list)
    for c in chunks:
        if c["nhom"] == "goc":
            c["huong_dan_boi"] = []
            by_dieu[c["dieu_id"]].append(c)
    for h in chunks:
        if h["nhom"] != "huong_dan":
            continue
        for l in h["huong_dan_cho"]:
            for c in by_dieu.get(l["dieu_id"], []):
                hop_khoan = l["khoan"] is None or c["chunk_id"] == c["dieu_id"] or \
                    c["chunk_id"].startswith(f"{c['dieu_id']}#K{l['khoan']}")
                giao = (c["valid_to"] is None or h["valid_from"] < c["valid_to"]) and \
                       (h["valid_to"] is None or c["valid_from"] < h["valid_to"])
                if hop_khoan and giao and not any(x["phien_ban_id"] == h["phien_ban_id"] for x in c["huong_dan_boi"]):
                    c["huong_dan_boi"].append({"so_hieu": h["so_hieu"], "chunk_id": h["chunk_id"],
                                               "phien_ban_id": h["phien_ban_id"],
                                               "trang_thai": "viet_cho_ban_cu" if c["valid_from"] > h["valid_from"] else "khop"})

    luat = [c for c in chunks if c["nhom"] == "goc"]
    hd = [c for c in chunks if c["nhom"] == "huong_dan"]
    tv = [x for so_hieu, v in vb.items() for x in toan_van(v, [r for r in dieu_pb if r["so_hieu"] == so_hieu])]
    write_jsonl(OUT / "corpus_luat.jsonl", luat)
    write_jsonl(OUT / "corpus_huong_dan.jsonl", hd)
    write_jsonl(OUT / "huong_dan_toan_van.jsonl", tv)
    write_jsonl(OUT / "van_ban.jsonl", vb_goc + vb_hd)
    nk = read_jsonl(TG / "ap_lenh_nhat_ky.jsonl")
    tk.update({"chunk_luat": len(luat), "chunk_luat_dang_hieu_luc": sum(c["valid_to"] is None for c in luat),
               "chunk_luat_co_huong_dan": sum(bool(c["huong_dan_boi"]) for c in luat),
               "chunk_huong_dan": len(hd), "van_ban_huong_dan": len(vb_hd), "toan_van_phien_ban": len(tv),
               "thao_tac_sua_doi_da_ap": sum(e["ket_qua"] == "da_ap" for e in nk),
               "thao_tac_sua_doi_chua_ap": sum(e["ket_qua"] == "loi" for e in nk)})
    (OUT / "thong_ke.json").write_text(json.dumps(tk, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  corpus_luat {tk['chunk_luat']} chunk ({tk['chunk_luat_co_huong_dan']} có hướng dẫn) | "
          f"corpus_huong_dan {tk['chunk_huong_dan']} chunk ({tk['chunk_huong_dan_co_lien_ket']} có liên kết) | "
          f"toàn văn {tk['toan_van_phien_ban']} bản / {tk['van_ban_huong_dan']} văn bản")
    return 0


if __name__ == "__main__":
    sys.exit(main())
