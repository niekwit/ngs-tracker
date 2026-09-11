"""PDF report generation for a single workflow run."""

import io
import json
import textwrap
from xml.sax.saxutils import escape

from pathlib import Path

from pypdf import PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import get_backup_locations, get_logo_path, resolve_stored_path

_LOGO_MAX_WIDTH = 6 * cm
_LOGO_MAX_HEIGHT = 2.2 * cm

_styles = getSampleStyleSheet()
_H1 = ParagraphStyle("ReportH1", parent=_styles["Title"], fontSize=18, spaceAfter=4)
_H2 = ParagraphStyle(
    "ReportH2",
    parent=_styles["Heading2"],
    fontSize=12,
    spaceBefore=14,
    spaceAfter=6,
    textColor=colors.HexColor("#212529"),
)
_BODY = _styles["BodyText"]
_MUTED = ParagraphStyle("Muted", parent=_BODY, textColor=colors.HexColor("#6c757d"))
_MONO = ParagraphStyle("Mono", parent=_BODY, fontName="Courier", fontSize=8.5, leading=11)

_TABLE_HEADER_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
)


def _p(text, style=_BODY):
    return Paragraph(escape(str(text)) if text else "", style)


def _link_p(url, style=_BODY):
    safe_url = escape(url)
    return Paragraph(f'<link href="{safe_url}" color="blue">{safe_url}</link>', style)


def _logo_flowable():
    path = get_logo_path()
    if not path or not Path(path).exists():
        return None
    try:
        reader = ImageReader(path)
        iw, ih = reader.getSize()
        scale = min(_LOGO_MAX_WIDTH / iw, _LOGO_MAX_HEIGHT / ih, 1.0)
        img = Image(path, width=iw * scale, height=ih * scale)
        img.hAlign = "CENTER"
        return img
    except Exception:
        return None


def _flatten_config(d: dict, indent: int = 0) -> list[str]:
    """Flatten a (possibly nested) config dict into indented "key: value" lines."""
    lines = []
    prefix = "  " * indent
    for key, val in d.items():
        if isinstance(val, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_flatten_config(val, indent + 1))
        elif isinstance(val, (list, tuple)):
            joined = ", ".join(str(v) for v in val) if val else "[]"
            lines.append(f"{prefix}{key}: {joined}")
        elif val is None:
            lines.append(f"{prefix}{key}: null")
        elif val == "":
            lines.append(f'{prefix}{key}: ""')
        else:
            lines.append(f"{prefix}{key}: {val}")
    return lines


def _build_cover_pdf(run, mapping_rate_cutoff: float, workflow_url: str | None) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        title=f"{run.workflow_name} — Run {run.id} Report",
    )
    story = []

    # Logo
    logo = _logo_flowable()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 10))

    # Header
    story.append(_p(f"{run.workflow_name} — Workflow Run Report", _H1))
    subtitle_bits = [f"Run ID: {run.id}", run.run_date.strftime("%Y-%m-%d %H:%M")]
    if run.workflow_tag:
        subtitle_bits.append(f"Tag: {run.workflow_tag}")
    story.append(_p("  ·  ".join(subtitle_bits), _MUTED))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#dee2e6"), spaceBefore=8, spaceAfter=4))

    # Summary table: run ID, date, project, status, tags, runtime, workflow URL
    tag_list = run.tag_list
    _key_style = ParagraphStyle("k", parent=_BODY, fontName="Helvetica-Bold")
    summary_rows = [
        ["Run ID", _p(run.id)],
        ["Date of run", _p(run.run_date.strftime("%Y-%m-%d %H:%M"))],
        ["Project", _p(run.project.name)],
        ["Status", _p(run.status_label)],
        ["Tags", _p(", ".join(tag_list) if tag_list else "—")],
    ]
    if run.runtime_display:
        summary_rows.append(["Runtime", _p(run.runtime_display)])
    if workflow_url:
        summary_rows.append(["Workflow", _link_p(workflow_url)])
    if run.created_by:
        summary_rows.append(["Created by", _p(run.created_by)])
    if run.description:
        summary_rows.append(["Description", _p(run.description)])
    summary_table = Table(
        [[_p(k, _key_style), v] for k, v in summary_rows],
        colWidths=[4 * cm, 12.7 * cm],
    )
    summary_table.setStyle(_TABLE_HEADER_STYLE)
    story.append(summary_table)

    # Backup status
    story.append(_p("Backup Status", _H2))
    backed_up = {b["location"]: b["path"] for b in run.backups_list}
    backup_locations = get_backup_locations()
    loc_names = [loc["name"] for loc in backup_locations]
    backup_rows = [["Location", "Backed up", "Path"]]
    for loc in backup_locations:
        name = loc["name"]
        if name in backed_up:
            backup_rows.append([name, "Yes", backed_up[name] or "—"])
        else:
            backup_rows.append([name, "No", ""])
    for b in run.backups_list:
        if b["location"] not in loc_names:
            backup_rows.append([f"{b['location']} (removed)", "Yes", b.get("path") or "—"])
    if run.shared_storage_path:
        backup_rows.append(["Shared storage", "—", run.shared_storage_path])
    backup_table = Table(
        [[_p(c) for c in row] for row in backup_rows],
        colWidths=[5 * cm, 2.7 * cm, 9 * cm],
    )
    backup_table.setStyle(_TABLE_HEADER_STYLE)
    story.append(backup_table)

    # Notes
    story.append(_p("Notes", _H2))
    if run.notes:
        for line in run.notes.splitlines():
            story.append(_p(line) if line.strip() else Spacer(1, 6))
    else:
        story.append(_p("No notes recorded.", _MUTED))

    # Samples
    story.append(_p("Samples", _H2))
    if run.run_samples:
        sample_rows = [["Sample"]] + [[rs.sample.name] for rs in run.run_samples]
        sample_table = Table([[_p(c) for c in row] for row in sample_rows], colWidths=[16.7 * cm])
        sample_table.setStyle(_TABLE_HEADER_STYLE)
        story.append(sample_table)
    else:
        story.append(_p("No samples linked to this run.", _MUTED))

    # Configuration
    config_files = [
        f for f in run.attached_files if f.file_type == "config" and f.config_dict
    ]
    if config_files:
        story.append(_p("Configuration", _H2))
        for cf in config_files:
            story.append(_p(cf.original_filename, ParagraphStyle("cfname", parent=_BODY, fontName="Helvetica-Bold")))
            lines = _flatten_config(cf.config_dict)
            wrapped = []
            for line in lines:
                indent = " " * (len(line) - len(line.lstrip(" ")))
                wrapped.extend(
                    textwrap.wrap(
                        line,
                        width=95,
                        subsequent_indent=indent + "  ",
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                    or [line]
                )
            story.append(Preformatted("\n".join(wrapped), _MONO))
            story.append(Spacer(1, 8))

    # Mapping rates
    mr_files = [
        f for f in run.attached_files if f.file_type == "mapping_rates" and f.parsed_config
    ]
    if mr_files:
        story.append(_p("Mapping Rates", _H2))
        for mf in mr_files:
            mr = json.loads(mf.parsed_config)
            story.append(
                _p(
                    f"{mf.original_filename} — cutoff: {mapping_rate_cutoff}%",
                    ParagraphStyle("mrname", parent=_BODY, fontName="Helvetica-Bold"),
                )
            )
            rows = [["Sample", "Mapping rate (%)", "Status"]]
            for sample, rate in zip(mr.get("samples", []), mr.get("rates", [])):
                passed = rate >= mapping_rate_cutoff
                rows.append([sample, f"{rate:.2f}", "OK" if passed else "BELOW CUTOFF"])
            mr_table = Table([[_p(c) for c in row] for row in rows], colWidths=[8 * cm, 4.7 * cm, 4 * cm])
            style_cmds = list(_TABLE_HEADER_STYLE.getCommands())
            for i, (_, rate) in enumerate(
                zip(mr.get("samples", []), mr.get("rates", [])), start=1
            ):
                if rate < mapping_rate_cutoff:
                    style_cmds.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#dc3545")))
            mr_table.setStyle(TableStyle(style_cmds))
            story.append(mr_table)
            story.append(Spacer(1, 8))

    doc.build(story)
    buf.seek(0)
    return buf


def build_run_report_pdf(
    run, mapping_rate_cutoff: float, workflow_url: str | None = None
) -> io.BytesIO:
    """Build a full PDF report for a workflow run: cover pages + all attached PDFs."""
    cover_buf = _build_cover_pdf(run, mapping_rate_cutoff, workflow_url)

    writer = PdfWriter()
    writer.append(cover_buf)

    pdf_files = [f for f in run.attached_files if f.is_pdf]
    for f in pdf_files:
        stored = resolve_stored_path(f.stored_path)
        if not stored.exists():
            continue
        try:
            writer.append(str(stored), outline_item=f.original_filename)
        except Exception:
            continue

    out = io.BytesIO()
    writer.write(out)
    writer.close()
    out.seek(0)
    return out
