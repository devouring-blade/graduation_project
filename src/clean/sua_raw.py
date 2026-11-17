"""Sửa trực tiếp file HTML trong data/raw theo một bản đối chiếu, ghi lại từng chỗ sửa.

Dùng:  sua_raw(file, dong_moi, nguon)
  - file      : đường dẫn HTML trong data/raw
  - dong_moi  : danh sách dòng chữ đúng của TOÀN văn bản (đã duyệt)
  - nguon     : mô tả nguồn đối chiếu
Cách làm: căn hai danh sách dòng (difflib); dòng khác -> thay chữ trong đúng khối HTML chứa dòng đó
(giữ thẻ, thuộc tính, in đậm); dòng thiếu -> chèn khối mới cùng kiểu với khối đứng trước.
Dòng thừa trong raw (vd. phần "sao y bản chính") giữ nguyên.
Sau khi ghi, đọc lại file và kiểm tra ra đúng dòng mong muốn; cập nhật manifest (sha256 mới,
giữ sha256 cũ ở 'sha256_truoc_sua') và ghi nhật ký data/raw/SUA_TAY.jsonl.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

from html_text import BLOCK_TAGS, _has_block_child, read_lines

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"


def chuan(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    t = re.sub(r"[\s ]+", " ", t)
    return t.strip()


def _khoi(soup) -> list[tuple[Tag, int]]:
    """(khối lá, số đoạn <br>) theo đúng thứ tự read_lines() sinh dòng."""
    body = soup.body or soup
    out = []
    for tag in body.find_all(True):
        if tag.name not in BLOCK_TAGS or tag.name in ("table", "tr", "tbody", "thead", "ul", "ol", "body"):
            continue
        if _has_block_child(tag):
            continue
        segs = [[]]
        for d in tag.descendants:
            if isinstance(d, Tag) and d.name == "br":
                segs.append([])
            elif isinstance(d, NavigableString) and d.__class__.__name__ != "Comment":
                segs[-1].append(str(d))
        for i, s in enumerate(segs):
            if chuan("".join(s)):
                out.append((tag, i))
    return out


def _dat_chu(tag: Tag, seg: int, text: str, dam: bool, soup):
    """Thay chữ đoạn thứ seg (tính theo <br>) của khối tag."""
    parts = re.split(r"<br\s*/?>", tag.decode_contents())
    plain = [chuan(BeautifulSoup(p, "lxml").get_text()) for p in parts]
    nonempty = [i for i, p in enumerate(plain) if p]
    idx = nonempty[seg]
    new_html = f"<strong>{text}</strong>" if dam else text
    parts[idx] = new_html
    tag.clear()
    frag = BeautifulSoup("<x>" + "<br/>".join(parts) + "</x>", "lxml").x
    for c in list(frag.contents):
        tag.append(c)


def sua_raw(file: Path, dong_moi: list[str], nguon: str, ghi_chu: str = "") -> list[dict]:
    file = Path(file).resolve()
    html = file.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    lines = read_lines(file)
    khoi = _khoi(soup)
    assert len(khoi) == len(lines), f"lệch số dòng {len(khoi)} vs {len(lines)}"
    A = [chuan(l.text) for l in lines]
    B = [chuan(x) for x in dong_moi]
    nk = []
    sm = difflib.SequenceMatcher(a=A, b=B, autojunk=False)
    ops = sm.get_opcodes()
    # Chèn làm sau cùng, đi ngược để chỉ số không lệch
    for op, i1, i2, j1, j2 in ops:
        if op == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                i, j = i1 + k, j1 + k
                if i < i2 and j < j2:
                    tag, seg = khoi[i]
                    _dat_chu(tag, seg, B[j], lines[i].bold, soup)
                    nk.append({"thao_tac": "sua", "dong": i, "cu": A[i], "moi": B[j]})
                elif j < j2:          # bên mới dài hơn -> chèn sau dòng i2-1
                    nk.append({"thao_tac": "chen", "sau_dong": i2 - 1, "moi": B[j], "_tag": khoi[i2 - 1][0]})
                # bên cũ dài hơn: giữ nguyên dòng thừa
        elif op == "insert":
            for j in range(j1, j2):
                nk.append({"thao_tac": "chen", "sau_dong": i1 - 1, "moi": B[j], "_tag": khoi[i1 - 1][0]})
    # thực hiện chèn: các dòng chèn sau cùng một khối giữ thứ tự
    last_by_tag: dict[int, Tag] = {}
    for e in [e for e in nk if e["thao_tac"] == "chen"]:
        ref = e.pop("_tag")
        anchor = last_by_tag.get(id(ref), ref)
        new = soup.new_tag(ref.name, attrs=copy.copy(ref.attrs))
        new.string = e["moi"]
        anchor.insert_after(new)
        last_by_tag[id(ref)] = new
    out = str(soup)
    file.write_text(out, encoding="utf-8", newline="\n")
    # kiểm tra đọc lại
    got = [chuan(l.text) for l in read_lines(file)]
    exp = list(A)
    for op, i1, i2, j1, j2 in reversed(ops):
        if op == "replace":
            n_old, n_new = i2 - i1, j2 - j1
            exp[i1:i1 + min(n_old, n_new)] = B[j1:j1 + min(n_old, n_new)]
            if n_new > n_old:
                exp[i2:i2] = B[j1 + n_old:j2]
        elif op == "insert":
            exp[i1:i1] = B[j1:j2]
    assert got == exp, "đọc lại không khớp mong đợi"
    # manifest + nhật ký
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    rel = file.relative_to(ROOT / "data").as_posix()
    mpath = RAW / "manifest.jsonl"
    rows = [json.loads(x) for x in mpath.read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in rows:
        if r["file"] == rel:
            r.setdefault("sha256_truoc_sua", r["sha256"])
            r["sha256"], r["bytes"] = sha, file.stat().st_size
            r["sua_tay"] = sorted(set(r.get("sua_tay", [])) | {nguon})
    mpath.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    with (RAW / "SUA_TAY.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        for e in nk:
            f.write(json.dumps({"ngay": date.today().isoformat(), "file": rel, "nguon": nguon,
                                "ghi_chu": ghi_chu, **e}, ensure_ascii=False) + "\n")
    return nk
