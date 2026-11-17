"""Clean – Phần 1: dựng corpus từ 4 bộ luật gốc (chưa ghép sửa đổi).

Chạy: venv\\Scripts\\python.exe src\\clean\\build_goc.py

Đầu ra trong data/processed/:
    van_ban.jsonl   mỗi dòng một văn bản
    dieu.jsonl      mỗi dòng một Điều (cây Khoản/Điểm)
    chunks.jsonl    chunk để embed / truy xuất
    thong_ke.json   số liệu tổng hợp
Thoát với mã 1 nếu kiểm tra không đạt.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cau_truc import parse_van_ban, render_dieu_body  # noqa: E402
from chunking import chunk_dieu, sha  # noqa: E402
from html_text import read_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "processed"
CONFIG = ROOT / "config" / "van_ban_goc.json"

RE_NGAY = r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})"
RE_HIEU_LUC = re.compile(r"có hiệu lực(?: thi hành)?(?: kể)? từ " + RE_NGAY, re.I)
RE_THONG_QUA = re.compile(r"thông qua " + RE_NGAY, re.I)
RE_HA_NOI = re.compile(r"Hà Nội,\s*" + RE_NGAY, re.I)


def _find_date(rx, texts) -> str | None:
    for t in texts:
        m = rx.search(t)
        if m:
            d, mo, y = (int(x) for x in m.groups())
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def kiem_tra_mot_phien_ban(rows: list[dict], key: str) -> list[str]:
    """Tại mọi ngày, mỗi key chỉ có đúng một phiên bản hiệu lực."""
    loi, by = [], defaultdict(list)
    for r in rows:
        by[r[key]].append((r["valid_from"], r["valid_to"] or "9999-12-31"))
    for k, iv in by.items():
        iv.sort()
        for (a1, b1), (a2, _) in zip(iv, iv[1:]):
            if a2 < b1:
                loi.append(f"{k}: [{a1},{b1}) chồng [{a2},…)")
    return loi


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    manifest = [json.loads(x) for x in (DATA / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    OUT.mkdir(parents=True, exist_ok=True)
    van_ban, dieu_rows, chunk_rows, loi = [], [], [], []
    thong_ke = {"van_ban": {}}

    for m in [r for r in manifest if r["nhom"] == "goc"]:
        so_hieu, c = m["so_hieu"], cfg[m["so_hieu"]]
        path = DATA / m["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != m["sha256"]:
            loi.append(f"{so_hieu}: sha256 không khớp manifest")
        parsed = parse_van_ban(read_lines(path))
        D = parsed["dieu"]

        hl_vb = _find_date(RE_HIEU_LUC, "\n".join(render_dieu_body(d) for d in D[-3:]).split("\n"))
        ban_hanh = _find_date(RE_THONG_QUA, parsed["cuoi_van_ban"]) or _find_date(RE_HA_NOI, parsed["dau_van_ban"])
        hl = c.get("ngay_hieu_luc") or hl_vb
        vb = {"so_hieu": so_hieu, "ten": c["ten"], "ten_ngan": c["ten_ngan"], "nam": c["nam"],
              "loai": c["loai"], "nhom": m["nhom"], "linh_vuc": c["linh_vuc"], "co_quan": c["co_quan"],
              "ngay_ban_hanh": ban_hanh, "ngay_hieu_luc": hl, "ngay_hieu_luc_ghi_trong_vb": hl_vb,
              "can_cu_hieu_luc": c.get("can_cu_hieu_luc"), "so_dieu": len(D),
              "file": m["file"], "sha256": m["sha256"], "url": m.get("url")}
        van_ban.append(vb)

        so = [int(re.match(r"\d+", d["so_dieu"]).group()) for d in D]
        if so != list(range(1, c["so_dieu_mong_doi"] + 1)):
            loi.append(f"{so_hieu}: {len(D)} Điều, mong đợi 1..{c['so_dieu_mong_doi']} liên tục")

        n_chunk = Counter()
        for d in D:
            dieu_id = f"{so_hieu}#D{d['so_dieu']}"
            body = render_dieu_body(d)
            rec = {"dieu_id": dieu_id, "phien_ban_id": f"{dieu_id}@{hl}", "so_hieu": so_hieu,
                   "so_dieu": d["so_dieu"], "thu_tu": d["thu_tu"], "tieu_de": d["tieu_de"], "vi_tri": d["vi_tri"],
                   "doan_dan": d["doan_dan"], "diem": d["diem"], "khoan": d["khoan"],
                   "trang_thai": "hieu_luc", "valid_from": hl, "valid_to": None, "nguon_thay_doi": [],
                   "sha256": sha(f"Điều {d['so_dieu']}. {d['tieu_de']}\n{body}")}
            dieu_rows.append(rec)
            chunks = chunk_dieu(vb, rec)
            all_text = "\n".join(ch["text"] for ch in chunks)
            for line in body.split("\n"):           # mọi dòng của Điều phải nằm trong chunk
                if line.strip() and line not in all_text:
                    loi.append(f"{dieu_id}: dòng bị mất khi cắt chunk: {line[:60]}")
            for ch in chunks:
                n_chunk[ch["cap"]] += 1
                chunk_rows.append({
                    "chunk_id": ch["chunk_id"], "phien_ban_id": f"{ch['chunk_id']}@{hl}", "dieu_id": dieu_id,
                    "so_hieu": so_hieu, "nhom": m["nhom"], "loai_van_ban": c["loai"], "linh_vuc": c["linh_vuc"],
                    "cap": ch["cap"], "trich_dan": ch["trich_dan"], "text": ch["text"], "noi_dung": ch["noi_dung"],
                    "so_tu": ch["so_tu"], "valid_from": hl, "valid_to": None, "sha256": sha(ch["text"]),
                    "huong_dan_boi": [], "huong_dan_cho": []})
        thong_ke["van_ban"][so_hieu] = {
            "so_dieu": len(D), "so_khoan": sum(len(d["khoan"]) for d in D),
            "so_diem": sum(len(k["diem"]) for d in D for k in d["khoan"]) + sum(len(d["diem"]) for d in D),
            "so_chunk": sum(n_chunk.values()), "ngay_hieu_luc": hl}

    loi += [f"trùng phien_ban_id: {k}" for k, v in Counter(r["phien_ban_id"] for r in chunk_rows).items() if v > 1]
    loi += kiem_tra_mot_phien_ban(chunk_rows, "chunk_id") + kiem_tra_mot_phien_ban(dieu_rows, "dieu_id")
    thong_ke["so_chunk"] = len(chunk_rows)
    thong_ke["kiem_tra"] = {"dat": not loi, "loi": loi}

    write_jsonl(OUT / "van_ban.jsonl", van_ban)
    write_jsonl(OUT / "dieu.jsonl", dieu_rows)
    write_jsonl(OUT / "chunks.jsonl", chunk_rows)
    (OUT / "thong_ke.json").write_text(json.dumps(thong_ke, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'Văn bản':<16}{'Điều':>6}{'Khoản':>7}{'Điểm':>7}{'Chunk':>7}  hiệu lực")
    for sh, t in thong_ke["van_ban"].items():
        print(f"{sh:<16}{t['so_dieu']:>6}{t['so_khoan']:>7}{t['so_diem']:>7}{t['so_chunk']:>7}  {t['ngay_hieu_luc']}")
    if loi:
        print(f"KIỂM TRA KHÔNG ĐẠT ({len(loi)}):", *loi[:20], sep="\n  ")
        return 1
    print("Kiểm tra: ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
