import html
import re
from datetime import date, timedelta
from pathlib import Path

from hijridate import Gregorian
from weasyprint import HTML

from kurrasa.services.company import load_facts, load_template

FONTS = Path(__file__).resolve().parents[3] / "assets" / "fonts"
METHODS_AR = {"direct purchase": "شراء مباشر", "limited competition": "منافسة محدودة", "general competition": "منافسة عامة"}
COVER_FIELDS = ("اسم المنافسة:", "رقم الكراسة:", "تاريخ طرح الكراسة:", "الجهة المالكة:", "كراسة الشروط والمواصفات")


def hijri(day: date) -> str:
    h = Gregorian(day.year, day.month, day.day).to_hijri()
    return f"{h.year}/{h.month:02d}/{h.day:02d}"


def both_calendars(day: date) -> str:
    return f'<span dir="ltr">{day:%d/%m/%Y}</span> · <span dir="ltr">{hijri(day)}</span> هـ'


def clause_headings() -> set[str]:
    """The template's own numbered clause titles, so numbered lists the agent writes aren't mistaken for them."""
    return {line.strip() for line in load_template().splitlines() if re.match(r"^\d+\.\s", line.strip())}


def body_html(tender: str) -> str:
    """The filled booklet text as HTML: sections, clauses, paragraphs, lists and tables."""
    headings, out, items, rows = clause_headings(), [], [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()
        if rows:
            head, *rest = rows
            out.append("<table class='grid'><tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{c or '&#160;'}</td>" for c in r) + "</tr>" for r in rest)
                       + "</table>")
            rows.clear()

    started = False
    for raw in tender.splitlines():
        line = raw.strip().replace("**", "")
        if set(line) == {"="}:
            started = True
            continue
        if not started or not line:
            if started:
                flush()
            continue
        text = html.escape(line)
        if line.startswith("|"):
            cells = [html.escape(c.strip()) for c in line.strip("|").split("|")]
            if not all(set(c) <= {"-", ":", " "} for c in cells):
                rows.append(cells)
            continue
        if re.match(r"^[-•*]\s+", line):
            items.append(html.escape(re.sub(r"^[-•*]\s+", "", line)))
            continue
        flush()
        if line.startswith("القسم"):
            out.append(f"<h2>{text}</h2>")
        elif line in headings or re.match(r"^ملحق \(\d+\)", line):
            out.append(f"<h3>{text}</h3>")
        else:
            out.append(f"<p>{text}</p>")
    flush()
    return "\n".join(out)


def build_tender_html(package: dict) -> str:
    facts = load_facts()
    period = facts["procurement_policy"]["clarification_period"]
    publish = date.fromisoformat(package.get("publish") or date.today().isoformat())
    questions = publish + timedelta(days=period["questions_deadline_days"])
    answers = questions + timedelta(days=period["answers_deadline_days"])
    title = html.escape(package.get("sections", {}).get("TITLE", "منافسة"))
    number = html.escape(package.get("tender_no") or "—")
    method = METHODS_AR.get((package.get("route") or {}).get("method"), "—")

    def rows(pairs):
        return "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in pairs)

    basics = rows([("اسم المنافسة", title), ("رقم الكراسة", f'<span dir="ltr">{number}</span>'),
                   ("الجهة المالكة", "شركة سحاب – الرياض"), ("نوع المنافسة", method),
                   ("طريقة تقديم العروض", "ملفان منفصلان للعرض الفني والعرض المالي"), ("لغة العرض", "العربية"),
                   ("العملة", "الريال السعودي")])
    dates = rows([("تاريخ طرح الكراسة", both_calendars(publish)),
                  ("آخر موعد لإرسال الاستفسارات", both_calendars(questions)),
                  ("آخر موعد للرد على الاستفسارات", both_calendars(answers)),
                  ("مشاركة الإجابات", "تُنشر جميع الاستفسارات وإجاباتها لجميع المتنافسين")])

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>
@font-face {{ font-family: Plex; src: url("{(FONTS / 'IBMPlexSansArabic-Regular.ttf').as_uri()}"); font-weight: 400; }}
@font-face {{ font-family: Plex; src: url("{(FONTS / 'IBMPlexSansArabic-SemiBold.ttf').as_uri()}"); font-weight: 600; }}
@font-face {{ font-family: Plex; src: url("{(FONTS / 'IBMPlexSansArabic-Bold.ttf').as_uri()}"); font-weight: 700; }}
@page {{ size: A4; margin: 24mm 18mm 22mm;
  @top-right {{ content: "شركة سحاب · إدارة المشتريات"; font: 600 8.5pt Plex; color: #0b6b50; }}
  @top-left {{ content: "كراسة الشروط والمواصفات · {number}"; font: 8.5pt Plex; color: #6b7280; }}
  @bottom-center {{ content: "صفحة " counter(page) " من " counter(pages); font: 8.5pt Plex; color: #6b7280; }} }}
@page :first {{ margin: 0; @top-right {{ content: none }} @top-left {{ content: none }} @bottom-center {{ content: none }} }}
body {{ font-family: Plex; font-size: 10.5pt; line-height: 1.75; color: #1f2a37; }}
.cover {{ height: 296mm; position: relative; overflow: hidden; break-after: page; }}
.band {{ background: #0b6b50; color: #fff; padding: 22mm 20mm 14mm; }}
.brand {{ font-size: 30pt; font-weight: 700; letter-spacing: 1px; }}
.brand small {{ font-size: 11pt; font-weight: 400; opacity: .85; display: block; }}
.cover-body {{ padding: 30mm 20mm; }}
.kicker {{ color: #0b6b50; font-weight: 600; font-size: 12pt; }}
.cover h1 {{ font-size: 28pt; line-height: 1.35; margin: 4mm 0 10mm; color: #0f1f33; }}
.cover-meta {{ border-top: 2px solid #12a37b; padding-top: 6mm; font-size: 11.5pt; }}
.cover-meta div {{ margin: 2mm 0; }} .cover-meta b {{ color: #0b6b50; }}
.cover-foot {{ position: absolute; bottom: 16mm; right: 20mm; left: 20mm; color: #6b7280; font-size: 9pt; }}
.panel {{ border: 1px solid #dfe5e8; border-radius: 6px; padding: 3mm; margin: 0 0 7mm; break-inside: avoid; }}
.panel-title {{ color: #0b6b50; font-weight: 600; margin: 0 1mm 2mm; }}
table.info {{ width: 100%; border-collapse: separate; border-spacing: 0 1.5mm; }}
table.info th {{ width: 36%; background: #eef1f3; font-weight: 600; text-align: right; padding: 2mm 3mm; border-radius: 4px; }}
table.info td {{ padding: 2mm 3mm; color: #0b6b50; border-bottom: 1px solid #eef1f3; }}
h2 {{ font-size: 14pt; color: #0f1f33; border-bottom: 2px solid #12a37b; padding-bottom: 1.5mm; margin: 9mm 0 3mm; break-after: avoid; }}
h3 {{ font-size: 11pt; font-weight: 600; color: #0b6b50; margin: 5mm 0 1mm; break-after: avoid; }}
p {{ margin: 0 0 2mm; text-align: justify; }}
ul {{ margin: 0 0 3mm; padding-right: 6mm; }} li {{ margin: 0 0 1mm; }}
table.grid {{ width: 100%; border-collapse: collapse; margin: 2mm 0 4mm; }}
table.grid th {{ background: #0b6b50; color: #fff; font-weight: 600; padding: 2mm; border: 1px solid #0b6b50; }}
table.grid td {{ border: 1px solid #cfd8dc; padding: 5mm 2mm; }}
</style></head><body>
<section class="cover">
  <div class="band"><div class="brand">سحاب<small>Sahab · إدارة المشتريات</small></div></div>
  <div class="cover-body">
    <div class="kicker">كراسة الشروط والمواصفات</div>
    <h1>{title}</h1>
    <div class="cover-meta">
      <div><b>رقم الكراسة:</b> <span dir="ltr">{number}</span></div>
      <div><b>نوع المنافسة:</b> {method}</div>
      <div><b>تاريخ الطرح:</b> {both_calendars(publish)}</div>
    </div>
  </div>
  <div class="cover-foot">شركة سحاب – الرياض · وثيقة سرية للمتنافسين المدعوين فقط</div>
</section>
<div class="panel"><div class="panel-title">المعلومات الأساسية</div><table class="info">{basics}</table></div>
<div class="panel"><div class="panel-title">العناوين والمواعيد المتعلقة بالمنافسة</div><table class="info">{dates}</table></div>
{body_html(package.get("tender") or "")}
</body></html>"""


def tender_pdf(package: dict) -> bytes:
    """The tender booklet as a formatted Arabic PDF (A4, cover page, both calendars, page X of Y)."""
    return HTML(string=build_tender_html(package)).write_pdf()
