import json

from kurrasa.pipeline.run import save_package
from kurrasa.services.pdf import tender_pdf

SAMPLE = "كراسة الشروط والمواصفات\n\nاسم المنافسة: توريد نظام CRM لعدد 120 مستخدماً\n" + "بند تجريبي للتأكد من تعدد الصفحات.\n" * 120


def test_tender_pdf_makes_a_multi_page_pdf():
    data = tender_pdf(SAMPLE)
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page\n") >= 2


def test_save_package_writes_pdf_next_to_txt(tmp_path):
    package = {"tender": SAMPLE, "transcript": [], "route": None, "issues": [], "stopped_reason": "finished"}
    save_package(tmp_path, package)
    assert (tmp_path / "tender.txt").exists() and (tmp_path / "tender.pdf").read_bytes().startswith(b"%PDF")
    assert "tender" not in json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
