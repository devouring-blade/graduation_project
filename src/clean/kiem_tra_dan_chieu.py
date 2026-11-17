"""Kiểm tra dẫn chiếu chéo trong 4 bộ luật gốc.

Ý tưởng: luật tự nhắc tới chính nó rất nhiều ("điểm d khoản 2 Điều 175 của Bộ luật này",
"khoản 3 Điều này", "các điểm từ điểm a đến điểm n khoản này"). Nếu dữ liệu bị mất Khoản/Điểm
cuối của một Điều thì thứ tự vẫn liền nên kiểm tra thứ tự không bắt được – nhưng câu dẫn chiếu
tới chỗ bị mất sẽ trỏ vào chỗ không tồn tại.

Chỉ kiểm dẫn chiếu NỘI BỘ chắc chắn: kết thúc bằng "Điều này", "khoản này", hoặc theo sau là
"của Bộ luật này". Dẫn chiếu trần ("tại Điều 26", không ghi văn bản) được kiểm riêng, mức tin
thấp hơn (có thể trỏ sang văn bản khác). Dẫn chiếu sang văn bản khác thì bỏ qua.

Chạy sau build_goc.py:
    venv\\Scripts\\python.exe src\\clean\\kiem_tra_dan_chieu.py
Đầu ra: data/processed/dan_chieu.jsonl (mọi dẫn chiếu) và in danh sách không khớp.
Script KHÔNG sửa dữ liệu.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed"
DIEM_ORDER = "abcdđeghiklmnopqrstuvxy"

D = r"[a-zđ]"
N = r"\d+[a-zđ]?"
SEP = r"(?:\s*,\s*|\s*,?\s*(?:và|hoặc)\s+)"
# Danh sách có thể lặp từ khóa: "b và điểm c", "1 hoặc khoản 2", "40 và Điều 41"
LD = rf"{D}(?:{SEP}(?:điểm\s+)?{D}(?!\w))*"
LK = rf"\d+(?:{SEP}(?:khoản\s+)?\d+(?!\w))*"
LN = rf"{N}(?:{SEP}(?:Điều\s+)?{N}(?!\w))*"
# Ranh giới sau chữ cái điểm: "a" không được là đầu một từ ("điểm a khoản" ok, "điểm anh" không)
RE_REF = re.compile(
    r"(?<!\w)(?=(?:các\s+)?(?:điểm|khoản|Điều|điều)\s)"
    rf"(?:(?:các\s+)?điểm\s+(?:từ\s+điểm\s+(?P<d1>{D})\s+đến\s+điểm\s+(?P<d2>{D})|(?P<d>{LD}))(?!\w)\s*,?\s*)?"
    rf"(?:(?:của\s+)?(?:các\s+)?khoản\s+(?:từ\s+khoản\s+(?P<k1>\d+)\s+đến\s+khoản\s+(?P<k2>\d+)|(?P<k>{LK}|này))(?!\w)\s*,?\s*)?"
    rf"(?:(?:của\s+)?(?P<cac>các\s+)?(?:Điều|điều)\s+(?:từ\s+Điều\s+(?P<n1>\d+)\s+đến\s+Điều\s+(?P<n2>\d+)|(?P<n>{LN}|này))(?!\w))?"
    r"(?P<tail>\s+(?:của|tại)\s+[^,;.:()]{0,80})?"
)
RE_TAIL_NOI_BO = re.compile(r"^\s+(?:của|tại)\s+Bộ\s+luật\s+này", re.I)
RE_TAIL_NGOAI = re.compile(r"^\s+(?:của|tại)\s+(?:Bộ\s+luật|Luật|Nghị\s+quyết|Nghị\s+định|Pháp\s+lệnh|Hiến\s+pháp|Thông\s+tư|"
                           r"điều\s+ước|Công\s+ước|văn\s+bản|luật)", re.I)


def _list(s: str) -> list[str]:
    parts = re.split(r"\s*,\s*|\s*,?\s*(?:và|hoặc)\s+", s.strip())
    return [re.sub(r"^(?:điểm|khoản|Điều)\s+", "", x) for x in parts if x]


def _range_d(a: str, b: str) -> list[str]:
    i, j = DIEM_ORDER.index(a), DIEM_ORDER.index(b)
    return list(DIEM_ORDER[i:j + 1])


def units(d: dict):
    """(khoan, diem, text) cho mọi đơn vị chữ của một Điều."""
    if d["doan_dan"]:
        yield None, None, d["doan_dan"]
    for p in d["diem"]:
        yield None, p["ky_hieu"], p["noi_dung"]
    for k in d["khoan"]:
        yield k["so"], None, k["noi_dung"]
        for p in k["diem"]:
            yield k["so"], p["ky_hieu"], p["noi_dung"]
        if k["doan_sau"]:
            yield k["so"], None, k["doan_sau"]


def main() -> int:
    dieu = defaultdict(dict)                  # so_hieu -> so_dieu -> record
    for line in (OUT / "dieu.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        dieu[r["so_hieu"]][r["so_dieu"]] = r

    def ton_tai(sh, n, k, p):
        """Trả về None nếu tồn tại, ngược lại chuỗi mô tả phần không tồn tại."""
        a = dieu[sh].get(n)
        if a is None:
            return f"không có Điều {n}"
        if k is None:
            if p is None:
                return None
            if any(x["ky_hieu"] == p for x in a["diem"]):
                return None
            return f"Điều {n} không có điểm {p} (ngoài khoản)"
        kk = next((x for x in a["khoan"] if x["so"] == int(k)), None)
        if kk is None:
            return f"Điều {n} không có khoản {k} (có {len(a['khoan'])} khoản)"
        if p is None or any(x["ky_hieu"] == p for x in kk["diem"]):
            return None
        co = "".join(x["ky_hieu"] for x in kk["diem"]) or "không có điểm"
        return f"khoản {k} Điều {n} không có điểm {p} (có: {co})"

    rows, stats = [], Counter()
    for sh, by in dieu.items():
        for so, a in by.items():
            for k_ctx, d_ctx, text in units(a):
                if text.lstrip().startswith(("“", '"')):
                    continue
                for m in RE_REF.finditer(text):
                    g = m.groupdict()
                    if not (g["n"] or g["n1"] or g["k"] == "này"):
                        continue                    # không có neo Điều -> không xác định được
                    tail = g["tail"] or ""
                    if g["n"] == "này" or g["k"] == "này":
                        loai = "noi_bo"
                    elif RE_TAIL_NOI_BO.match(tail):
                        loai = "noi_bo"
                    elif RE_TAIL_NGOAI.match(tail):
                        stats["ngoai"] += 1
                        continue
                    else:
                        loai = "tran"
                    # Danh sách Điều
                    if g["n"] == "này" or (g["n"] is None and g["k"] == "này"):
                        ns = [so]
                    elif g["n1"]:
                        ns = [str(x) for x in range(int(g["n1"]), int(g["n2"]) + 1)]
                    else:
                        ns = _list(g["n"])
                    # Danh sách Khoản
                    if g["k"] == "này":
                        if k_ctx is None:
                            stats["khoan_nay_ngoai_khoan"] += 1
                            continue
                        ks = [str(k_ctx)]
                    elif g["k1"]:
                        ks = [str(x) for x in range(int(g["k1"]), int(g["k2"]) + 1)]
                    elif g["k"]:
                        ks = _list(g["k"])
                    else:
                        ks = [None]
                    # Danh sách Điểm
                    if g["d1"]:
                        ps = _range_d(g["d1"], g["d2"])
                    elif g["d"]:
                        ps = _list(g["d"])
                    else:
                        ps = [None]
                    # "khoản 2 Điều 155 và Điều 157": khoản/điểm chỉ thuộc Điều đầu, các Điều sau là cả Điều.
                    # "khoản 1 các điều 134, 135": khoản áp cho từng Điều.
                    targets = []
                    for i, n in enumerate(ns):
                        if i == 0 or g["cac"]:
                            targets += [(n, k, p) for k in ks for p in ps]
                        else:
                            targets.append((n, None, None))
                    for n, k, p in targets:
                        err = ton_tai(sh, n, k, p)
                        stats[f"{loai}_{'ok' if err is None else 'loi'}"] += 1
                        rows.append({
                            "so_hieu": sh, "tu": f"Điều {so}" + (f" khoản {k_ctx}" if k_ctx else "")
                                                 + (f" điểm {d_ctx}" if d_ctx else ""),
                            "cau": m.group(0).strip(), "loai": loai,
                            "toi": {"dieu": n, "khoan": k, "diem": p},
                            "khop": err is None, "loi": err,
                        })

    with (OUT / "dan_chieu.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Chỗ không khớp đã được người duyệt giải thích (config/bo_sung_tay.json)
    cfg_path = ROOT / "config" / "bo_sung_tay.json"
    giai_thich = json.loads(cfg_path.read_text(encoding="utf-8")).get("dan_chieu_da_giai_thich", []) if cfg_path.exists() else []
    for r in rows:
        for g in giai_thich:
            if not r["khop"] and r["so_hieu"] == g["so_hieu"] and r["tu"] == g["tu"] and r["cau"] == g["cau"]:
                r["giai_thich"] = g["ket_luan"]

    print("Thống kê:", dict(stats))
    gt = [r for r in rows if r.get("giai_thich")]
    print(f"Đã giải thích: {len(gt)}")
    for r in gt:
        print(f"  [{r['so_hieu']}] {r['tu']}: \"{r['cau']}\" – {r['giai_thich'][:90]}…")
    for loai in ("noi_bo", "tran"):
        bad = [r for r in rows if r["loai"] == loai and not r["khop"] and not r.get("giai_thich")]
        print(f"\n=== {loai}: {len(bad)} không khớp")
        for r in bad:
            print(f"  [{r['so_hieu']}] {r['tu']}: \"{r['cau'][:90]}\" -> {r['loi']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
