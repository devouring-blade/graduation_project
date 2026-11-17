"""Clean – Phần 1: dựng corpus ban đầu từ 4 bộ luật gốc (chưa ghép sửa đổi).

Chạy (từ thư mục dự án):
    venv\\Scripts\\python.exe src\\clean\\build_goc.py

Đầu ra trong data/processed/:
    van_ban.jsonl   mỗi dòng một văn bản
    dieu.jsonl      mỗi dòng một phiên bản Điều (cây Khoản/Điểm)
    chunks.jsonl    chunk để embed / truy xuất
    canh_bao.jsonl  lỗi nguồn và chỗ code phải đoán, cần người duyệt
    thong_ke.json   số liệu tổng hợp + kết quả kiểm tra
Thoát với mã 1 nếu có kiểm tra bắt buộc không đạt.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bo_sung  # noqa: E402
from cau_truc import parse_van_ban, render_dieu_body  # noqa: E402
from chunking import NGUONG_DIEU, NGUONG_KHOAN, chunk_dieu, sha  # noqa: E402
from html_text import read_lines  # noqa: E402

CODE_VERSION = "goc-1.2"
# Cảnh báo mà code đã tự sửa chắc chắn (không cần người duyệt)
TU_DONG_SUA = {"diem_dinh_dong", "khoan_thieu_dau_cham", "cuoi_van_ban_chung_dong"}
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "processed"
CONFIG = ROOT / "config" / "van_ban_goc.json"

RE_NGAY = r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})"
RE_HIEU_LUC = re.compile(r"có hiệu lực(?: thi hành)?(?: kể)? từ " + RE_NGAY, re.I)
RE_THONG_QUA = re.compile(r"thông qua " + RE_NGAY, re.I)
RE_HA_NOI = re.compile(r"Hà Nội,\s*" + RE_NGAY, re.I)


def _iso(m) -> str:
    d, mth, y = (int(x) for x in m.groups())
    return f"{y:04d}-{mth:02d}-{d:02d}"


def _find_date(rx, texts) -> str | None:
    for t in texts:
        if t.startswith(("“", '"')):
            continue
        m = rx.search(t)
        if m:
            return _iso(m)
    return None


def load_manifest() -> list[dict]:
    rows = [json.loads(x) for x in (DATA / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if r["nhom"] == "goc"]


def write_jsonl(path: Path, rows) -> int:
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def kiem_tra_mot_phien_ban(rows: list[dict], key: str) -> list[str]:
    """Bất biến: tại mọi ngày, mỗi key chỉ có đúng một phiên bản hiệu lực."""
    loi = []
    by = defaultdict(list)
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
    bs_cfg = bo_sung.load(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    van_ban, dieu_rows, chunk_rows, canh_bao = [], [], [], []
    loi: list[str] = []          # lỗi kiểm tra bắt buộc
    thong_ke = {"code_version": CODE_VERSION, "chay_luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "nguong_dieu": NGUONG_DIEU, "nguong_khoan": NGUONG_KHOAN, "van_ban": {}}

    for m in load_manifest():
        so_hieu = m["so_hieu"]
        c = cfg[so_hieu]
        path = DATA / m["file"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != m["sha256"]:
            loi.append(f"{so_hieu}: sha256 không khớp manifest")

        parsed = parse_van_ban(read_lines(path))
        D = parsed["dieu"]
        for w in parsed["canh_bao"]:
            canh_bao.append({"so_hieu": so_hieu, **w,
                             "trang_thai": "tu_dong_sua" if w["loai"] in TU_DONG_SUA else "mo"})
        bo_sung.ap_dung(ROOT, bs_cfg, so_hieu, D, canh_bao, loi)

        # --- ngày tháng
        cuoi_dieu = [render_dieu_body(d) for d in D[-3:]]
        hl_vb = _find_date(RE_HIEU_LUC, "\n".join(cuoi_dieu).split("\n"))
        ban_hanh = _find_date(RE_THONG_QUA, parsed["cuoi_van_ban"]) or _find_date(RE_HA_NOI, parsed["dau_van_ban"])
        hl = c.get("ngay_hieu_luc") or hl_vb
        if not hl:
            loi.append(f"{so_hieu}: không tìm được ngày hiệu lực")
        if c.get("ngay_hieu_luc") and c["ngay_hieu_luc"] != hl_vb:
            canh_bao.append({"so_hieu": so_hieu, "loai": "ngay_hieu_luc_ghi_de", "dieu": None,
                             "chi_tiet": f"văn bản ghi {hl_vb}, dùng {hl} theo config: {c.get('can_cu_hieu_luc')}",
                             "trang_thai": "mo" if c.get("can_kiem_tra") else "da_xac_minh",
                             "xu_ly": {"nguon": c.get("nguon_hieu_luc")}})

        vb = {
            "so_hieu": so_hieu, "ten": c["ten"], "ten_ngan": c["ten_ngan"], "nam": c["nam"],
            "loai": c["loai"], "nhom": m["nhom"], "linh_vuc": c["linh_vuc"], "co_quan": c["co_quan"],
            "ngay_ban_hanh": ban_hanh, "ngay_hieu_luc": hl, "ngay_hieu_luc_ghi_trong_vb": hl_vb,
            "can_cu_hieu_luc": c.get("can_cu_hieu_luc"), "so_dieu": len(D),
            "file": m["file"], "sha256": m["sha256"], "url": m.get("url"),
        }
        van_ban.append(vb)

        # --- kiểm tra số Điều
        so = [int(re.match(r"\d+", d["so_dieu"]).group()) for d in D]
        if len(D) != c["so_dieu_mong_doi"]:
            loi.append(f"{so_hieu}: {len(D)} Điều, mong đợi {c['so_dieu_mong_doi']}")
        if so != list(range(1, len(so) + 1)):
            loi.append(f"{so_hieu}: số Điều không liên tục 1..N")

        n_chunk = Counter()
        for d in D:
            dieu_id = f"{so_hieu}#D{d['so_dieu']}"
            body = render_dieu_body(d)
            rec = {
                "dieu_id": dieu_id,
                "phien_ban_id": f"{dieu_id}@{hl}",
                "so_hieu": so_hieu,
                "so_dieu": d["so_dieu"], "thu_tu": d["thu_tu"], "tieu_de": d["tieu_de"],
                "vi_tri": d["vi_tri"],
                "doan_dan": d["doan_dan"], "diem": d["diem"], "khoan": d["khoan"],
                "trang_thai": "hieu_luc",
                "valid_from": hl, "valid_to": None,
                "nguon_thay_doi": [],
                "bo_sung_tay": d.get("bo_sung_tay", []),
                "sha256": sha(f"Điều {d['so_dieu']}. {d['tieu_de']}\n{body}"),
            }
            dieu_rows.append(rec)
            if not body.strip():
                loi.append(f"{dieu_id}: Điều rỗng")

            chunks = chunk_dieu(vb, rec)
            # Kiểm tra phủ: mọi dòng nội dung của Điều phải nằm trong ít nhất một chunk
            all_text = "\n".join(ch["text"] for ch in chunks)
            for line in body.split("\n"):
                if line.strip() and line not in all_text:
                    loi.append(f"{dieu_id}: dòng bị mất khi cắt chunk: {line[:60]}")
            for ch in chunks:
                n_chunk[ch["cap"]] += 1
                chunk_rows.append({
                    "chunk_id": ch["chunk_id"],
                    "phien_ban_id": f"{ch['chunk_id']}@{hl}",
                    "dieu_id": dieu_id,
                    "so_hieu": so_hieu,
                    "nhom": m["nhom"], "loai_van_ban": c["loai"], "linh_vuc": c["linh_vuc"],
                    "cap": ch["cap"],
                    "trich_dan": ch["trich_dan"],
                    "text": ch["text"],
                    "noi_dung": ch["noi_dung"],
                    "so_tu": ch["so_tu"],
                    "valid_from": hl, "valid_to": None,
                    "sha256": sha(ch["text"]),
                    "huong_dan_boi": [], "huong_dan_cho": [],
                })

        thong_ke["van_ban"][so_hieu] = {
            "ten": c["ten"], "so_dieu": len(D),
            "so_khoan": sum(len(d["khoan"]) for d in D),
            "so_diem": sum(len(k["diem"]) for d in D for k in d["khoan"]) + sum(len(d["diem"]) for d in D),
            "so_chunk": sum(n_chunk.values()), "chunk_theo_cap": dict(n_chunk),
            "ngay_hieu_luc": hl, "ngay_ban_hanh": ban_hanh,
        }

    # --- kiểm tra toàn cục
    ids = Counter(r["phien_ban_id"] for r in chunk_rows)
    loi += [f"trùng phien_ban_id chunk: {k}" for k, v in ids.items() if v > 1]
    loi += [f"chunk rỗng: {r['chunk_id']}" for r in chunk_rows if not r["noi_dung"].strip()]
    loi += kiem_tra_mot_phien_ban(chunk_rows, "chunk_id")
    loi += kiem_tra_mot_phien_ban(dieu_rows, "dieu_id")

    sizes = sorted(r["so_tu"] for r in chunk_rows)
    thong_ke["chunk"] = {
        "tong": len(chunk_rows),
        "so_tu_min": sizes[0], "so_tu_trung_vi": sizes[len(sizes) // 2],
        "so_tu_p95": sizes[int(len(sizes) * 0.95)], "so_tu_max": sizes[-1],
        "vuot_600_tu": [r["chunk_id"] for r in chunk_rows if r["so_tu"] > 600],
    }
    thong_ke["canh_bao_theo_loai"] = dict(Counter(w["loai"] for w in canh_bao))
    thong_ke["canh_bao_theo_trang_thai"] = dict(Counter(w["trang_thai"] for w in canh_bao))
    thong_ke["canh_bao_con_mo"] = [f"{w['so_hieu']} {w['dieu'] or ''} {w['loai']}: {w['chi_tiet']}"
                                   for w in canh_bao if w["trang_thai"] == "mo"]
    thong_ke["kiem_tra"] = {"dat": not loi, "loi": loi}

    write_jsonl(OUT / "van_ban.jsonl", van_ban)
    write_jsonl(OUT / "dieu.jsonl", dieu_rows)
    write_jsonl(OUT / "chunks.jsonl", chunk_rows)
    write_jsonl(OUT / "canh_bao.jsonl", canh_bao)
    (OUT / "thong_ke.json").write_text(json.dumps(thong_ke, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- in tóm tắt
    print(f"{'Văn bản':<16}{'Điều':>6}{'Khoản':>7}{'Điểm':>7}{'Chunk':>7}  hiệu lực")
    for sh, t in thong_ke["van_ban"].items():
        print(f"{sh:<16}{t['so_dieu']:>6}{t['so_khoan']:>7}{t['so_diem']:>7}{t['so_chunk']:>7}  {t['ngay_hieu_luc']}")
    ck = thong_ke["chunk"]
    print(f"\nChunk: {ck['tong']} | số từ min/trung vị/p95/max = "
          f"{ck['so_tu_min']}/{ck['so_tu_trung_vi']}/{ck['so_tu_p95']}/{ck['so_tu_max']} | >600 từ: {len(ck['vuot_600_tu'])}")
    print(f"Cảnh báo: {len(canh_bao)} theo trạng thái {thong_ke['canh_bao_theo_trang_thai']}")
    for x in thong_ke["canh_bao_con_mo"]:
        print("  CÒN MỞ:", x)
    if loi:
        print(f"\nKIỂM TRA KHÔNG ĐẠT ({len(loi)} lỗi):")
        for x in loi[:30]:
            print("  -", x)
        return 1
    print("\nKiểm tra: ĐẠT (số Điều, liên tục, phủ nội dung, không trùng id, một phiên bản/ngày)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
