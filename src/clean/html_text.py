"""Đọc file HTML của vbpl.vn thành danh sách dòng chữ sạch.

Quy tắc (BAO_CAO_DU_LIEU.md mục 7):
- Chỉ lấy khối lá (p, div, td, li, h1-h6...) để không lặp chữ.
- <br> là xuống dòng thật.
- KHÔNG gộp theo data-merged: thuộc tính này đôi khi đánh dấu cả dòng nội dung
  (vd. Điều 682 BLDS). Việc nối tên Chương/Phần do bước tách cấu trúc làm.
- Chuẩn hóa Unicode NFC, gom khoảng trắng.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

BLOCK_TAGS = {"p", "div", "td", "th", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "table", "tr", "tbody", "thead", "ul", "ol", "body", "blockquote"}

_WS = re.compile(r"[ \t    ​﻿]+")


@dataclass
class Line:
    text: str
    bold: bool = False      # toàn bộ chữ của dòng nằm trong <strong>/<b>
    italic: bool = False
    center: bool = False
    cls: str = ""           # class prov-* nếu có (chỉ để tham khảo, không dựa vào)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = _WS.sub(" ", s)
    return s.strip()


def _has_block_child(tag: Tag) -> bool:
    return any(isinstance(c, Tag) and c.name in BLOCK_TAGS for c in tag.descendants)


def _segments(tag: Tag) -> list[list[tuple[str, bool, bool]]]:
    """Chia nội dung khối lá thành các đoạn theo <br>; mỗi đoạn là list (chữ, đậm, nghiêng)."""
    segs: list[list[tuple[str, bool, bool]]] = [[]]

    def walk(node, bold: bool, ital: bool):
        for c in node.children:
            if isinstance(c, NavigableString):
                if c.__class__.__name__ in ("Comment",):
                    continue
                segs[-1].append((str(c), bold, ital))
            elif isinstance(c, Tag):
                if c.name == "br":
                    segs.append([])
                    continue
                b = bold or c.name in ("strong", "b")
                i = ital or c.name in ("em", "i")
                walk(c, b, i)

    walk(tag, False, False)
    return segs


def _is_center(tag: Tag) -> bool:
    if (tag.get("align") or "").lower() == "center":
        return True
    return "text-align: center" in (tag.get("style") or "").replace("text-align:center", "text-align: center")


def read_lines(path: str | Path) -> list[Line]:
    html = Path(path).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    out: list[Line] = []
    for tag in body.find_all(True):
        if tag.name not in BLOCK_TAGS or tag.name in ("table", "tr", "tbody", "thead", "ul", "ol", "body"):
            continue
        if _has_block_child(tag):
            continue
        cls = " ".join(c for c in (tag.get("class") or []) if c.startswith("prov-"))
        center = _is_center(tag)
        for seg in _segments(tag):
            text = norm("".join(t for t, _, _ in seg))
            if not text:
                continue
            visible = [(t, b, i) for t, b, i in seg if norm(t)]
            bold = bool(visible) and all(b for _, b, _ in visible)
            ital = bool(visible) and all(i for _, _, i in visible)
            out.append(Line(text, bold, ital, center, cls))
    return out


if __name__ == "__main__":
    import sys
    for ln in read_lines(sys.argv[1]):
        flags = ("B" if ln.bold else "-") + ("I" if ln.italic else "-") + ("C" if ln.center else "-")
        print(f"{flags} {ln.text}")
