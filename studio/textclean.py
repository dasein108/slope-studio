"""PDF-extraction cleanup — keep pure prose + headings, drop page furniture.

pdftotext output carries per-page artifacts that would end up in narration:
form feeds, standalone page numbers, the running head/footer repeated on every
page, decorative separators, and hyphenated line breaks. `clean_pdf_text` strips
exactly those and nothing else.

The dangerous case is the running head: it must be detected by frequency, but
ordinary short prose lines also repeat (a paragraph-final "это." appears 200+
times in a long book). The discriminator is the PAGE COUNT: a running head
appears on ~every page, so only lines repeating >= half the number of form-feed
pages are treated as furniture.
"""

from __future__ import annotations

import re
from collections import Counter

_PAGE_NUM = re.compile(r"^\d{1,4}$")
_DECOR = re.compile(r"^[•·*∙◦\-–—_=\.\s]+$")
_HYPHEN_BREAK = re.compile(r"([а-яёa-zА-ЯЁA-Z])-\n\s*")


def clean_pdf_text(text: str) -> str:
    pages = max(1, text.count("\f"))
    lines = text.split("\n")
    counts = Counter(ln.strip() for ln in lines if 0 < len(ln.strip()) < 80)
    # furniture repeats about once per page; prose lines repeat far less than
    # half the page count (measured: a common paragraph-final word ~0.4×pages)
    running = {s for s, c in counts.items() if c >= max(4, pages // 2)}

    out: list[str] = []
    for ln in lines:
        s = ln.replace("\f", "").strip()
        if not s:
            out.append("")
            continue
        if _PAGE_NUM.match(s) or _DECOR.match(s) or s in running:
            continue
        out.append(ln.replace("\f", ""))

    t = "\n".join(out)
    t = _HYPHEN_BREAK.sub(r"\1", t)      # re-join words split across lines
    t = re.sub(r"\n{3,}", "\n\n", t)     # collapse blank-line runs
    return t.strip() + "\n"
