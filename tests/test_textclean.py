"""clean_pdf_text must drop page furniture and keep every word of prose."""

from __future__ import annotations

from studio.textclean import clean_pdf_text


def _book(pages: int = 20) -> str:
    """Synthetic pdftotext output: running head + page number on every page,
    plus prose that includes a legitimately-repeated short line."""
    out = []
    for p in range(1, pages + 1):
        out.append("\f" if p > 1 else "")
        out.append(str(p))                      # standalone page number
        out.append("")
        out.append("В ПОИСКАХ ЧУДЕСНОГО")       # running head, every page
        out.append("")
        if p == 1:
            out.append("Глава 1")
        out.append(f"Абзац номер {p} про учение и путь.")
        if p % 3 == 0:
            out.append("это.")                  # repeats, but well under pages/2 → PROSE
        out.append("•")                         # decorative separator
        out.append(f"Слово {p} перено-")        # unique per page: prose, not furniture
        out.append(f"сится дальше на стр {p}.")
    return "\n".join(out)


def test_furniture_removed_prose_kept():
    t = clean_pdf_text(_book())
    assert "В ПОИСКАХ ЧУДЕСНОГО" not in t       # running head gone
    assert "\f" not in t
    assert "•" not in t
    assert "\n7\n" not in t and not t.startswith("1\n")   # page numbers gone
    assert "Глава 1" in t                        # heading kept
    assert t.count("это.") == 6                  # repeated PROSE kept every time
    assert "Слово 5 переносится дальше" in t     # hyphen line-break rejoined
    assert "Абзац номер 20" in t                 # nothing truncated


def test_low_repeat_short_lines_survive():
    # a short line repeating well under pages/2 is prose, not furniture
    pages = ["страница\nтекст"] * 12
    pages[2] += "\nк нам."
    pages[7] += "\nк нам."
    t = "\f".join(pages)
    assert "к нам." in clean_pdf_text(t)


def test_no_formfeeds_still_safe():
    t = clean_pdf_text("Просто текст.\nБез страниц.\n")
    assert "Просто текст." in t and "Без страниц." in t
