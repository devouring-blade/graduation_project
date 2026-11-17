"""Clean – Phần 3, bước 1: tách Điều và cắt chunk các văn bản hướng dẫn (data/raw/huong_dan).

Chạy sau build_goc.py:  venv\\Scripts\\python.exe src\\clean\\build_huong_dan.py

Thông tin văn bản đọc từ chính văn bản: loại, trích yếu, ngày ban hành, ngày hiệu lực,
bộ luật được hướng dẫn (nhắc trong trích yếu, nếu không có thì trong phần "Căn cứ").
Văn bản nào không đọc được ngày hiệu lực -> ghi trong config/van_ban_huong_dan.json (do người điền).

Đầu ra data/processed/: huong_dan_van_ban.jsonl, huong_dan_dieu.jsonl
(chunk của văn bản hướng dẫn do ap_lenh.py sinh, cùng với phiên bản theo thời gian).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_goc import write_jsonl  # noqa: E402
from cau_truc import parse_van_ban, render_dieu_body  # noqa: E402
from chunking import sha  # noqa: E402
from html_text import read_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "processed"
CONFIG = ROOT / "config" / "van_ban_huong_dan.json"

NGAY = r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})"
CHU_THE = r"(?:Nghị quyết|Thông tư liên tịch|Thông tư|Nghị định|Luật) này"
RE_HL_NGAY = re.compile(CHU_THE + r"[^.]{0,220}?có hiệu lực(?: thi hành)?(?: kể)? từ " + NGAY)
RE_HL_KY = re.compile(CHU_THE + r"[^.]{0,220}?có hiệu lực(?: thi hành)?(?: kể)? từ ngày ký")
RE_BAN_HANH = re.compile(r"(?:Hà Nội|thông qua),?\s*" + NGAY)
LOAI = [("THÔNG TƯ LIÊN TỊCH", "thong_tu_lien_tich", "Thông tư liên tịch"), ("THÔNG TƯ", "thong_tu", "Thông tư"),
        ("NGHỊ QUYẾT", "nghi_quyet", "Nghị quyết"), ("NGHỊ ĐỊNH", "nghi_dinh", "Nghị định")]
BO_LUAT = [(re.compile(r"Bộ luật\s+tố tụng hình sự|101/2015/QH13", re.I), "101/2015/QH13", "hinh_su"),
           (re.compile(r"Bộ luật\s+tố tụng dân sự|92/2015/QH13", re.I), "92/2015/QH13", "dan_su"),
           (re.compile(r"Bộ luật\s+hình sự|100/2015/QH13", re.I), "100/2015/QH13", "hinh_su"),
           (re.compile(r"Bộ luật\s+dân sự|91/2015/QH13", re.I), "91/2015/QH13", "dan_su")]


def _iso(m) -> str:
    d, mo, y = (int(x) for x in m.groups()[-3:])
    return f"{y:04d}-{mo:02d}-{d:02d}"


def bo_luat_nhac(text: str) -> list[str]:
    """Các bộ luật gốc được nhắc trong đoạn chữ (theo thứ tự xuất hiện)."""
    hit = []
    for rx, sh, _ in BO_LUAT:
        m = rx.search(text)
        if m:
            hit.append((m.start(), sh))
    return [sh for _, sh in sorted(hit)]


def thong_tin(so_hieu: str, lines, parsed) -> dict:
    texts = [ln.text for ln in lines]
    dau = parsed["dau_van_ban"]
    # loại + trích yếu: dòng loại văn bản (in hoa, căn giữa) rồi các dòng kế tiếp tới "Căn cứ"/cơ quan ban hành
    loai, ten_loai, trich_yeu = None, None, []
    for i, t in enumerate(dau):
        hit = next(((k, n) for up, k, n in LOAI if t.strip().upper() == up), None)
        if hit:
            loai, ten_loai = hit
            for u in dau[i + 1:]:
                if re.match(r"^(Căn cứ|Theo đề nghị|QUYẾT NGHỊ|HỘI ĐỒNG THẨM PHÁN|QUỐC HỘI|ỦY BAN|CHÍNH PHỦ|[_\-–—=]{3,})", u):
                    break
                trich_yeu.append(u)
            break
    trich_yeu = re.sub(r"\s+", " ", " ".join(trich_yeu)).strip()
    if trich_yeu.isupper():
        trich_yeu = trich_yeu[:1] + trich_yeu[1:].lower()
    can_cu = " ".join(t for t in dau if t.startswith("Căn cứ"))
    # Bộ luật được hướng dẫn: nêu trong trích yếu; nếu không thì trong "Căn cứ"; nếu không thì
    # các bộ luật được nhắc trong thân văn bản (theo số lần nhắc, nhiều trước)
    bl = bo_luat_nhac(trich_yeu) or bo_luat_nhac(can_cu)
    if not bl:
        than = " ".join(render_dieu_body(d) for d in parsed["dieu"])
        dem = {sh: len(rx.findall(than)) for rx, sh, _ in BO_LUAT}
        bl = [sh for sh, n in sorted(dem.items(), key=lambda x: -x[1]) if n]
    # ngày
    toan_van = [render_dieu_body(d) for d in parsed["dieu"]] + parsed["cuoi_van_ban"]
    ban_hanh = next((_iso(m) for t in dau + parsed["cuoi_van_ban"] for m in [RE_BAN_HANH.search(t)] if m), None)
    hl, hl_cach = None, None
    for t in toan_van:
        m = RE_HL_NGAY.search(t)
        if m:
            hl, hl_cach = _iso(m), "ghi trong văn bản"
            break
        if RE_HL_KY.search(t):
            hl, hl_cach = ban_hanh, "từ ngày ký"
            break
    return {"so_hieu": so_hieu, "loai": loai, "ten_loai": ten_loai, "trich_yeu": trich_yeu,
            "ngay_ban_hanh": ban_hanh, "ngay_hieu_luc": hl, "cach_xac_dinh_hieu_luc": hl_cach,
            "huong_dan_bo_luat": bl}


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    manifest = [json.loads(x) for x in (DATA / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    vbs, dieu_rows, chua_ro = [], [], []
    for m in [r for r in manifest if r["nhom"] == "huong_dan"]:
        lines = read_lines(DATA / m["file"])
        parsed = parse_van_ban(lines)
        info = thong_tin(m["so_hieu"], lines, parsed)
        info.update({k: v for k, v in cfg.get(m["so_hieu"], {}).items() if not k.startswith("_")})
        ten_ngan = f"{info['ten_loai'] or 'Văn bản'} {m['so_hieu']}"
        vb = {**info, "nhom": "huong_dan", "ten": f"{ten_ngan} – {info['trich_yeu']}".rstrip(" –"),
              "ten_trich_dan": ten_ngan, "nam": "",
              "linh_vuc": next((lv for _, sh, lv in BO_LUAT if sh in info["huong_dan_bo_luat"]), None),
              "so_dieu": len(parsed["dieu"]), "file": m["file"], "sha256": m["sha256"], "url": m.get("url")}
        vbs.append(vb)
        if not vb["ngay_hieu_luc"] or not vb["huong_dan_bo_luat"] or not parsed["dieu"]:
            chua_ro.append(vb)
            continue
        for d in parsed["dieu"]:
            did = f"{m['so_hieu']}#D{d['so_dieu']}"
            body = render_dieu_body(d)
            dieu_rows.append({"dieu_id": did, "phien_ban_id": f"{did}@{vb['ngay_hieu_luc']}", "so_hieu": m["so_hieu"],
                              "so_dieu": d["so_dieu"], "thu_tu": d["thu_tu"], "tieu_de": d["tieu_de"],
                              "vi_tri": d["vi_tri"], "doan_dan": d["doan_dan"], "diem": d["diem"], "khoan": d["khoan"],
                              "trang_thai": "hieu_luc", "valid_from": vb["ngay_hieu_luc"], "valid_to": None,
                              "nguon_thay_doi": [], "sha256": sha(f"Điều {d['so_dieu']}. {d['tieu_de']}\n{body}")})
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "huong_dan_van_ban.jsonl", vbs)
    write_jsonl(OUT / "huong_dan_dieu.jsonl", dieu_rows)
    print(f"{len(vbs)} văn bản hướng dẫn, {len(dieu_rows)} Điều")
    for v in vbs:
        print(f"  {v['so_hieu']:<44} {v['ngay_hieu_luc'] or '?':<11} {','.join(v['huong_dan_bo_luat']) or '?':<28} "
              f"{v['so_dieu']:>3} Điều | {v['trich_yeu'][:60]}")
    if chua_ro:
        print("\nCHƯA ĐƯA VÀO (thiếu ngày hiệu lực / bộ luật / Điều) – điền vào config/van_ban_huong_dan.json:")
        for v in chua_ro:
            print(f"  {v['so_hieu']}: hiệu lực={v['ngay_hieu_luc']}, bộ luật={v['huong_dan_bo_luat']}, Điều={v['so_dieu']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
