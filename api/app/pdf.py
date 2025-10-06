from __future__ import annotations

from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import os
from pathlib import Path


def _register_jp_font() -> str:
    """Register a Japanese-capable font and return its name.
    Priority: Noto Sans CJK JP if present, otherwise built-in HeiseiKakuGo-W5.
    """
    # Common locations for Noto Sans CJK
    candidates = [
        Path(__file__).parents[2] / "fonts" / "NotoSansCJKjp-Regular.otf",
        Path(__file__).parents[2] / "fonts" / "NotoSansJP-Regular.otf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf"),
        Path("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"),
    ]
    for p in candidates:
        try:
            if p.exists():
                pdfmetrics.registerFont(TTFont("JP", str(p)))
                return "JP"
        except Exception:
            pass
    # Fallback CID font bundled with ReportLab
    try:
        name = "HeiseiKakuGo-W5"
        pdfmetrics.registerFont(UnicodeCIDFont(name))
        return name
    except Exception:
        # As a final fallback, use Helvetica (may not render JP)
        return "Helvetica"


def assignments_to_pdf(
    assignments: List[Dict[str, Any]],
    nurses: Optional[List[Dict[str, Any]]] = None,
    days: Optional[List[str]] = None,
    summary: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=24,
        bottomMargin=18,
    )
    styles = getSampleStyleSheet()
    font_name = _register_jp_font()
    # Clone styles to apply Japanese font
    title_style = styles["Title"].clone("TitleJP")
    title_style.fontName = font_name
    title_style.leading = 18
    normal_style = styles["Normal"].clone("NormalJP")
    normal_style.fontName = font_name

    elements = []
    elements.append(Paragraph("看護師シフト 自動割当 結果", title_style))
    elements.append(Spacer(1, 12))

    shift_symbols = {"DAY": "日", "LATE": "遅", "NIGHT": "夜", "OFF": "休"}

    day_list: List[str]
    if days:
        day_list = list(days)
    else:
        day_list = sorted({str(a.get("date")) for a in assignments})

    nurse_rows: List[Dict[str, Any]]
    if nurses:
        nurse_rows = sorted(
            nurses,
            key=lambda x: (str(x.get("team")), int(str(x.get("id"))))
            if str(x.get("id")).isdigit() else str(x.get("id"))
        )
    else:
        uniq_ids = sorted({str(a.get("nurse_id")) for a in assignments}, key=lambda x: int(x))
        nurse_rows = [{"id": nid, "name": nid, "team": ""} for nid in uniq_ids]

    assign_lookup: Dict[tuple[str, str], str] = {}
    for a in assignments:
        nid = str(a.get("nurse_id"))
        date = str(a.get("date"))
        assign_lookup[(nid, date)] = str(a.get("shift"))

    header = ["Ns/Date"] + [d[-2:] for d in day_list]
    matrix: List[List[str]] = [header]
    for nurse in nurse_rows:
        nid = str(nurse.get("id"))
        label = f"{nurse.get('name', nid)} ({nid})"
        row = [label]
        for day in day_list:
            raw = assign_lookup.get((nid, day), "")
            row.append(shift_symbols.get(raw, raw or ""))
        matrix.append(row)

    roster_table = Table(matrix, repeatRows=1)
    roster_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
    ]))

    elements.append(roster_table)
    elements.append(Spacer(1, 12))

    if summary and summary.get("per_nurse"):
        h2 = styles["Heading2"].clone("H2JP")
        h2.fontName = font_name
        elements.append(Paragraph("個人別サマリ", h2))
        summary_header = ["Ns", "日勤", "遅番", "夜勤", "公休", "土日祝数", "勤務日数"]
        summary_rows = [summary_header]
        for info in summary["per_nurse"]:
            summary_rows.append([
                f"{info.get('name', info['nurse_id'])} ({info['nurse_id']})",
                str(info["counts"].get("DAY", 0)),
                str(info["counts"].get("LATE", 0)),
                str(info["counts"].get("NIGHT", 0)),
                str(info["counts"].get("OFF", 0)),
                str(info.get("weekend_work", 0)),
                str(info.get("total_work_days", 0)),
            ])
        summary_table = Table(summary_rows, repeatRows=1)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e0f2f1")),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 12))

    if warnings:
        h2 = styles["Heading2"].clone("H2JP2")
        h2.fontName = font_name
        elements.append(Paragraph("警告", h2))
        for warn in warnings[:20]:
            elements.append(Paragraph(f"・{warn}", normal_style))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
