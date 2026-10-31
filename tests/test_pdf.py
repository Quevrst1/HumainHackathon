import json
from datetime import date

from weasyprint import HTML

from kurrasa.pipeline.run import save_package
from kurrasa.services.company import AGENT_BLANKS, fill_template, load_facts, load_template
from kurrasa.services.pdf import build_tender_html, hijri, tender_pdf


def package(scope="- توريد نظام CRM لعدد 120 مستخدماً\n- الربط مع Odoo 16"):
    sections = {b: f"نص {b}" for b in AGENT_BLANKS}
    sections.update(TITLE="توريد نظام إدارة علاقات العملاء", SCOPE=scope)
    tender = fill_template(load_template(), sections, date(2026, 10, 29), "SAHAB-001", load_facts())
    return {"tender": tender, "sections": sections, "tender_no": "SAHAB-001", "publish": "2026-10-29",
            "route": {"method": "limited competition", "approver": "General Manager"}, "transcript": [], "issues": []}


def test_hijri_matches_etimad():
    # the Etimad tender page shared by the team shows 29/10/2026 as 1448/05/18
    assert hijri(date(2026, 10, 29)) == "1448/05/18"


def test_html_has_etimad_style_summary():
    html = build_tender_html(package())
    assert "SAHAB-001" in html and "منافسة محدودة" in html
    assert "29/10/2026" in html and "1448/05/18" in html          # publication date, both calendars
    assert "08/11/2026" in html                                      # questions deadline: +10 days
    assert "General Manager" not in html                             # the approver is internal


def test_html_keeps_the_booklet_structure():
    html = build_tender_html(package())
    assert html.count("<h2") >= 10                                   # one heading per القسم
    assert "<li>الربط مع Odoo 16</li>" in html                      # agent bullets become a list
    assert "<table" in html                                          # the questions form is a real table


def test_tender_pdf_is_a_multi_page_pdf():
    assert tender_pdf(package()).startswith(b"%PDF")
    assert len(HTML(string=build_tender_html(package())).render().pages) >= 3


def test_save_package_writes_pdf_next_to_txt(tmp_path):
    save_package(tmp_path, package())
    assert (tmp_path / "tender.txt").exists() and (tmp_path / "tender.pdf").read_bytes().startswith(b"%PDF")
    assert "tender" not in json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
