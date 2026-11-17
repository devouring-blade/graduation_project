"""Áp bổ sung tay (config/bo_sung_tay.json) lên cây Điều đã tách.

Nguyên tắc:
- Không sửa data/raw. Chữ bổ sung lấy thẳng từ file bằng chứng (data/bo_sung_tay/*.txt),
  tách bằng cùng bộ tách cấu trúc, nên không có bước chép tay chữ vào config.
- Chèn Điểm chỉ khi vị trí đó đang trống; nếu nguồn vbpl đã có Điểm đó (vd. vbpl tải lại đã sửa)
  thì báo lỗi để người kiểm tra lại, không ghi đè.
- Mỗi Điểm chèn vào mang trường "nguon_bo_sung" = id mục bổ sung.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from cau_truc import DIEM_ORDER, parse_van_ban
from html_text import Line, norm


@lru_cache(maxsize=None)
def _doc_bang_chung(path: str) -> dict:
    """File bằng chứng dạng chữ: phần đầu là ghi chú, nội dung sau dòng '=========='."""
    text = Path(path).read_text(encoding="utf-8")
    if "==========" in text:
        text = text.split("==========", 1)[1]
    lines = []
    for t in text.splitlines():
        t = norm(t)
        if t:
            lines.append(Line(t, bold=t.startswith("Điều ")))
    return {d["so_dieu"]: d for d in parse_van_ban(lines)["dieu"]}


def _khoan(dieu: dict, so: int) -> dict:
    for k in dieu["khoan"]:
        if k["so"] == so:
            return k
    raise KeyError(f"Điều {dieu['so_dieu']} không có khoản {so}")


def _thieu_diem(k: dict) -> list[str]:
    have = [d["ky_hieu"] for d in k["diem"]]
    if not have:
        return []
    last = DIEM_ORDER.index(have[-1])
    return [c for c in DIEM_ORDER[: last + 1] if c not in have]


def load(root: Path) -> dict:
    p = root / "config" / "bo_sung_tay.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ap_dung(root: Path, cfg: dict, so_hieu: str, dieu_list: list[dict], canh_bao: list[dict], loi: list[str]):
    by_so = {d["so_dieu"]: d for d in dieu_list}

    for m in cfg.get("bo_sung_diem", []):
        if m["so_hieu"] != so_hieu:
            continue
        dieu = by_so[m["dieu"]]
        k = _khoan(dieu, m["khoan"])
        src = _khoan(_doc_bang_chung(str(root / m["lay_tu"]))[m["dieu"]], m["khoan"])
        src_diem = {d["ky_hieu"]: d for d in src["diem"]}
        have = {d["ky_hieu"] for d in k["diem"]}
        for c in m["diem"]:
            if c in have:
                loi.append(f"{m['id']}: Điều {m['dieu']} khoản {m['khoan']} đã có điểm {c} – bổ sung tay đã cũ, cần xem lại")
                continue
            if c not in src_diem:
                loi.append(f"{m['id']}: file bằng chứng không có điểm {c}")
                continue
            k["diem"].append({"ky_hieu": c, "noi_dung": src_diem[c]["noi_dung"], "nguon_bo_sung": m["id"]})
        k["diem"].sort(key=lambda d: DIEM_ORDER.index(d["ky_hieu"]))
        # Các Điểm vbpl đã có phải trùng từng chữ với bằng chứng, nếu không thì nguồn không cùng bản
        for d in k["diem"]:
            if "nguon_bo_sung" not in d and d["ky_hieu"] in src_diem and src_diem[d["ky_hieu"]]["noi_dung"] != d["noi_dung"]:
                loi.append(f"{m['id']}: điểm {d['ky_hieu']} vbpl khác bằng chứng – nguồn có thể không cùng phiên bản")
        con = _thieu_diem(k)
        if con:
            loi.append(f"{m['id']}: sau bổ sung vẫn thiếu điểm {', '.join(con)}")
        dieu.setdefault("bo_sung_tay", []).append(m["id"])
        _dong_canh_bao(canh_bao, so_hieu, m["dieu"], "thieu_diem", m["khoan"], "da_bo_sung", m)

    for m in cfg.get("xac_nhan_khong_loi", []):
        if m["so_hieu"] != so_hieu:
            continue
        _dong_canh_bao(canh_bao, so_hieu, m["dieu"], m["loai"], m.get("khoan"), "xac_nhan_khong_loi", m)


def _dong_canh_bao(canh_bao, so_hieu, dieu, loai, khoan, trang_thai, m):
    found = False
    for w in canh_bao:
        if (w["so_hieu"] == so_hieu and w["dieu"] == f"Điều {dieu}" and w["loai"] == loai
                and (khoan is None or w["chi_tiet"].startswith(f"khoản {khoan}:"))):
            w["trang_thai"] = trang_thai
            w["xu_ly"] = {"id": m["id"], "nguon": m["nguon"], "lay_tu": m.get("lay_tu")}
            found = True
    if not found:
        canh_bao.append({"so_hieu": so_hieu, "loai": "bo_sung_tay_khong_khop", "dieu": f"Điều {dieu}",
                         "chi_tiet": f"mục {m['id']} không ứng với cảnh báo nào", "trang_thai": "mo"})
