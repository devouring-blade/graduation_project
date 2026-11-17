"""Bước 1: tách 4 bộ luật gốc thành cây Điều/Khoản/Điểm (bản ban hành, chưa ghép sửa đổi).

Đầu ra data/processed/trung_gian/: goc_van_ban.jsonl, goc_dieu.jsonl
Kiểm tra: mã băm file khớp manifest; số Điều liên tục 1..N đúng như config.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cau_truc import parse_van_ban, render_dieu_body  # noqa: E402
from chunking import sha  # noqa: E402
from html_text import read_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
TG = DATA / "processed" / "trung_gian"
CONFIG = ROOT / "config" / "van_ban_goc.json"

RE_NGAY = r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})"
RE_HIEU_LUC = re.compile(r"có hiệu lực(?: thi hành)?(?: kể)? từ " + RE_NGAY, re.I)
RE_THONG_QUA = re.compile(r"thông qua " + RE_NGAY, re.I)
RE_HA_NOI = re.compile(r"Hà Nội,\s*" + RE_NGAY, re.I)


def find_date(rx, texts) -> str | None:
    for t in texts:
        m = rx.search(t)
        if m:
            d, mo, y = (int(x) for x in m.groups())
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def dieu_record(so_hieu: str, d: dict, valid_from: str) -> dict:
    did = f"{so_hieu}#D{d['so_dieu']}"
    return {"dieu_id": did, "phien_ban_id": f"{did}@{valid_from}", "so_hieu": so_hieu,
            "so_dieu": d["so_dieu"], "thu_tu": d["thu_tu"], "tieu_de": d["tieu_de"], "vi_tri": d["vi_tri"],
            "doan_dan": d["doan_dan"], "diem": d["diem"], "khoan": d["khoan"],
            "trang_thai": "hieu_luc", "valid_from": valid_from, "valid_to": None, "nguon_thay_doi": [],
            "sha256": sha(f"Điều {d['so_dieu']}. {d['tieu_de']}\n{render_dieu_body(d)}")}


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    van_ban, dieu_rows, loi = [], [], []
    for m in [r for r in read_jsonl(DATA / "raw" / "manifest.jsonl") if r["nhom"] == "goc"]:
        so_hieu, c = m["so_hieu"], cfg[m["so_hieu"]]
        path = DATA / m["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != m["sha256"]:
            loi.append(f"{so_hieu}: sha256 không khớp manifest")
        parsed = parse_van_ban(read_lines(path))
        D = parsed["dieu"]
        so = [int(re.match(r"\d+", d["so_dieu"]).group()) for d in D]
        if so != list(range(1, c["so_dieu_mong_doi"] + 1)):
            loi.append(f"{so_hieu}: {len(D)} Điều, mong đợi 1..{c['so_dieu_mong_doi']} liên tục")
        hl_vb = find_date(RE_HIEU_LUC, "\n".join(render_dieu_body(d) for d in D[-3:]).split("\n"))
        hl = c.get("ngay_hieu_luc") or hl_vb
        van_ban.append({
            "so_hieu": so_hieu, "nhom": "goc", "loai": c["loai"], "ten": c["ten"], "ten_ngan": c["ten_ngan"],
            "nam": c["nam"], "linh_vuc": c["linh_vuc"], "co_quan": c["co_quan"],
            "ngay_ban_hanh": find_date(RE_THONG_QUA, parsed["cuoi_van_ban"]) or find_date(RE_HA_NOI, parsed["dau_van_ban"]),
            "ngay_hieu_luc": hl, "ngay_hieu_luc_ghi_trong_vb": hl_vb, "can_cu_hieu_luc": c.get("can_cu_hieu_luc"),
            "so_dieu": len(D), "file": m["file"], "sha256": m["sha256"], "url": m.get("url")})
        dieu_rows += [dieu_record(so_hieu, d, hl) for d in D]
        print(f"  {so_hieu:<15}{len(D):>5} Điều   hiệu lực {hl}")
    if loi:
        print("KIỂM TRA KHÔNG ĐẠT:", *loi, sep="\n  ")
        return 1
    write_jsonl(TG / "goc_van_ban.jsonl", van_ban)
    write_jsonl(TG / "goc_dieu.jsonl", dieu_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
