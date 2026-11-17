"""Clean – Phần 3, bước 2: liên kết hai chiều văn bản hướng dẫn <-> Điều của bộ luật gốc.

Chạy sau ap_lenh.py:  venv\\Scripts\\python.exe src\\clean\\lien_ket.py

Chunk hướng dẫn: huong_dan_cho = [{dieu_id, khoan, diem, dieu_phien_ban_id, trang_thai}]
    - Dẫn chiếu nêu rõ bộ luật ("điểm b khoản 1 Điều 65 của Bộ luật Hình sự", "Điều 65 BLHS") ->
      trang_thai "khop" (Điều chưa đổi kể từ khi hướng dẫn có hiệu lực) hoặc "viet_cho_ban_cu"
      (Điều có phiên bản mới bắt đầu sau ngày hướng dẫn có hiệu lực, khi hướng dẫn còn hiệu lực).
    - Điều nêu trong trích yếu văn bản ("Hướng dẫn áp dụng Điều 65 của Bộ luật Hình sự") -> gắn cho
      mọi chunk của văn bản đó (nguon "trich_yeu"); dẫn chiếu trong chunk có nguon "dan_chieu".
    - Văn bản có trích yếu chung chung ("một số quy định của Bộ luật Dân sự") và chunk không dẫn chiếu
      Điều nào -> huong_dan_cho rỗng (không xác định được Điều).
Chunk bộ luật gốc: huong_dan_boi = [{chunk_id, phien_ban_id, trang_thai}] –
    gắn vào chunk của đúng Điều (và đúng Khoản nếu nêu), khi hai khoảng hiệu lực giao nhau.
Dẫn chiếu tới bộ luật năm khác (vd. "Bộ luật Dân sự năm 2005") bị bỏ qua.

Đầu ra: data/processed/corpus_luat.jsonl (chunk Điều luật – dùng để tìm kiếm),
        corpus_huong_dan.jsonl (chunk hướng dẫn – chỉ tra theo mã), thong_ke_lien_ket.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed"

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
    out = []
    if True:
        ns = [str(x) for x in range(int(g["n1"]), int(g["n2"]) + 1)] if g["n1"] else _list(g["n"])
        ks = ([str(x) for x in range(int(g["k1"]), int(g["k2"]) + 1)] if g["k1"]
              else _list(g["k"]) if g["k"] else [None])
        ps = (list(DIEM_ORDER[DIEM_ORDER.index(g["d1"]):DIEM_ORDER.index(g["d2"]) + 1]) if g["d1"]
              else _list(g["d"]) if g["d"] else [None])
        for i, n in enumerate(ns):
            if i == 0 or g["cac"]:
                out += [(sh, n, k, p) for k in ks for p in ps]
            else:
                out.append((sh, n, None, None))
    return out


def main() -> int:
    vb = {json.loads(x)["so_hieu"]: json.loads(x) for x in (OUT / "huong_dan_van_ban.jsonl").read_text(encoding="utf-8").splitlines()}
    chunks = [json.loads(x) for x in (OUT / "chunks_phien_ban.jsonl").read_text(encoding="utf-8").splitlines()]
    versions = defaultdict(list)          # dieu_id -> [(valid_from, valid_to, phien_ban_id)] của bộ luật gốc
    for x in (OUT / "dieu_phien_ban.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(x)
        if r["so_hieu"] in ("91/2015/QH13", "92/2015/QH13", "100/2015/QH13", "101/2015/QH13") and not r["chua_tung_ap_dung"]:
            versions[r["dieu_id"]].append((r["valid_from"], r["valid_to"], r["phien_ban_id"], r["trang_thai"]))
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
    bo_qua = Counter()
    for c in chunks:
        if c["nhom"] != "huong_dan":
            continue
        v = vb[c["so_hieu"]]
        links = []
        # 1) dẫn chiếu nêu rõ trong chunk; 2) Điều nêu trong trích yếu văn bản ("Hướng dẫn áp dụng Điều 65
        #    của Bộ luật Hình sự") – mọi Điều của văn bản đó đều hướng dẫn Điều này
        for nguon, text in (("dan_chieu", c["noi_dung"]), ("trich_yeu", v["trich_yeu"])):
            for sh, n, k, p in dict.fromkeys(dan_chieu(text)):
                if any(l["dieu_id"] == f"{sh}#D{n}" and l["khoan"] in (k, None) for l in links):
                    continue
                l = lien_ket(sh, n, k, p, c["valid_from"], c["valid_to"], nguon)
                if l:
                    links.append(l)
                elif nguon == "dan_chieu":
                    bo_qua[f"{sh}#D{n}"] += 1
        c["huong_dan_cho"] = links
        tk["chunk_huong_dan"] += 1
        tk["chunk_co_lien_ket"] += bool(links)
        for l in links:
            tk[l["trang_thai"]] += 1

    # chiều ngược: gắn vào chunk bộ luật gốc
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
                if hop_khoan and giao and not any(x["chunk_id"] == h["chunk_id"] for x in c["huong_dan_boi"]):
                    c["huong_dan_boi"].append({"chunk_id": h["chunk_id"], "phien_ban_id": h["phien_ban_id"],
                                               "trang_thai": "viet_cho_ban_cu" if c["valid_from"] > h["valid_from"] else "khop"})
    tk["chunk_goc_duoc_huong_dan"] = sum(bool(c.get("huong_dan_boi")) for c in chunks if c["nhom"] == "goc")

    # Hai kho riêng: chỉ chunk Điều luật được đưa vào tìm kiếm; chunk hướng dẫn chỉ tra theo mã
    # khi một Điều luật trỏ tới (huong_dan_boi).
    for name, nhom in (("corpus_luat.jsonl", "goc"), ("corpus_huong_dan.jsonl", "huong_dan")):
        with (OUT / name).open("w", encoding="utf-8", newline="\n") as f:
            for c in chunks:
                if c["nhom"] == nhom:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
    (OUT / "corpus.jsonl").unlink(missing_ok=True)
    (OUT / "thong_ke_lien_ket.json").write_text(json.dumps({"thong_ke": tk, "dan_chieu_khong_co_dieu": bo_qua},
                                                         ensure_ascii=False, indent=2), encoding="utf-8")
    print(dict(tk))
    if bo_qua:
        print("Dẫn chiếu tới Điều không có trong dữ liệu:", dict(bo_qua.most_common(10)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
