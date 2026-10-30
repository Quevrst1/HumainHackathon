from datetime import date

import pytest

from kurrasa.services.company import AGENT_BLANKS, fill_template, load_facts, load_template, purchase_route


def test_purchase_route_boundaries():
    f = load_facts()
    assert purchase_route(100_000, f) == {"method": "direct purchase", "approver": "Purchasing Committee"}
    assert purchase_route(100_001, f)["approver"] == "General Manager"
    assert purchase_route(300_000, f)["method"] == "direct purchase"
    assert purchase_route(300_001, f)["method"] == "limited competition"
    assert purchase_route(1_000_000, f)["method"] == "limited competition"
    assert purchase_route(1_000_001, f)["method"] == "general competition"


def test_purchase_route_rejects_zero():
    with pytest.raises(ValueError):
        purchase_route(0, load_facts())


def test_template_header_stripped_and_blanks_present():
    t = load_template()
    assert "{{!" not in t
    for b in AGENT_BLANKS + ["TENDER_NO", "PUBLISH_DATE", "KEY_DATES"]:
        assert "{{" + b + "}}" in t


def test_fill_template_fills_everything():
    sections = {b: f"نص {b}" for b in AGENT_BLANKS}
    out = fill_template(load_template(), sections, date(2026, 11, 1), "SAHAB-001", load_facts())
    assert "{{" not in out and "SAHAB-001" in out and "2026-11-11" in out


def test_fill_template_reports_missing():
    with pytest.raises(ValueError, match="SCOPE"):
        fill_template(load_template(), {"TITLE": "x"}, date(2026, 11, 1), "N", load_facts())
