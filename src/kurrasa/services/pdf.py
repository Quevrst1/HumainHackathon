from pathlib import Path

from fpdf import FPDF

FONTS = Path(__file__).resolve().parents[3] / "assets" / "fonts"


def tender_pdf(text: str) -> bytes:
    """Render the Arabic tender text as an A4 PDF (right-to-left, shaped with HarfBuzz)."""
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_font("Amiri", "", FONTS / "Amiri-Regular.ttf")
    pdf.add_font("Amiri", "B", FONTS / "Amiri-Bold.ttf")
    pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab", language="ar")
    pdf.add_page()

    for line in text.splitlines():
        stripped = line.strip()
        if set(stripped) == {"="}:          # the template's section separators
            continue
        heading = stripped.startswith("القسم") or stripped == "كراسة الشروط والمواصفات"
        pdf.set_font("Amiri", "B" if heading else "", 15 if heading else 12)
        if heading:
            pdf.ln(3)
        pdf.multi_cell(0, 8, stripped or " ", align="R", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
