"""Đọc file HTML thành danh sách dòng chữ.

- Chỉ lấy khối lá (p, div, td, li, h1-h6…) để không lặp chữ; <br> là xuống dòng thật.
- Chuẩn hóa Unicode NFC, gom khoảng trắng.
- Mỗi dòng ghi thêm: in đậm toàn dòng, căn giữa (dùng để nhận tiêu đề Điều, Chương, Mục).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

BLOCK_TAGS = {"p", "div", "td", "th", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "table", "tr", "tbody", "thead", "ul", "ol", "body", "blockquote"}
CONTAINER = {"table", "tr", "tbody", "thead", "ul", "ol", "body"}
_WS = re.compile(r"[ \t    ​﻿]+")


@dataclass
class Line:
    text: str
    bold: bool = False      # toàn bộ chữ của dòng nằm trong <strong>/<b>
    center: bool = False


def norm(s: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", s)).strip()


def _has_block_child(tag: Tag) -> bool:
    return any(isinstance(c, Tag) and c.name in BLOCK_TAGS for c in tag.descendants)


def _segments(tag: Tag) -> list[list[tuple[str, bool]]]:
    """Nội dung khối lá chia theo <br>; mỗi đoạn là list (chữ, in đậm)."""
    segs: list[list[tuple[str, bool]]] = [[]]

    def walk(node, bold: bool):
        for c in node.children:
            if isinstance(c, NavigableString):
                if c.__class__.__name__ != "Comment":
                    segs[-1].append((str(c), bold))
            elif isinstance(c, Tag):
                if c.name == "br":
                    segs.append([])
                else:
                    walk(c, bold or c.name in ("strong", "b"))

    walk(tag, False)
    return segs


def _is_center(tag: Tag) -> bool:
    if (tag.get("align") or "").lower() == "center":
        return True
    return "text-align: center" in (tag.get("style") or "").replace("text-align:center", "text-align: center")


def read_lines(path: str | Path) -> list[Line]:
    soup = BeautifulSoup(Path(path).read_text(encoding="utf-8"), "lxml")
    out: list[Line] = []
    for tag in (soup.body or soup).find_all(True):
        if tag.name not in BLOCK_TAGS or tag.name in CONTAINER or _has_block_child(tag):
            continue
        center = _is_center(tag)
        for seg in _segments(tag):
            text = norm("".join(t for t, _ in seg))
            if text:
                visible = [b for t, b in seg if norm(t)]
                out.append(Line(text, bool(visible) and all(visible), center))
    return out
