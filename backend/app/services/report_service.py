import os
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, PageBreak, HRFlowable
)

from app.config import settings

def generate_modification_pdf_report(
    modification_data: Dict[str, Any],
    property_data: Dict[str, Any],
    output_filename: Optional[str] = None
) -> str:
    """
    Generate an auditable, professional PDF case verification report using ReportLab.
    """
    alert_id = modification_data.get("modification_alert_id", "MOD-REPORT")
    if not output_filename:
        output_filename = f"Report_{alert_id}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"

    pdf_path = settings.REPORTS_DIR / output_filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    brand_title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A")
    )

    brand_subtitle_style = ParagraphStyle(
        "BrandSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B")
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )

    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B")
    )

    elements = []

    # 1. Header Banner
    header_data = [
        [
            Paragraph("<b>PROPERTYWATCH AI</b><br/><font size=8 color='#0284C7'>PROPERTY INTELLIGENCE & VERIFICATION RECORD</font>", brand_title_style),
            Paragraph(f"<b>CASE DOSSIER</b><br/>Alert ID: <b>{alert_id}</b><br/>Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ParagraphStyle("HdrRight", parent=brand_subtitle_style, alignment=2))
        ]
    ]
    header_table = Table(header_data, colWidths=[320, 220])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=12))

    # 2. Status Banner
    status = modification_data.get("status", "New")
    status_bg = "#E0F2FE" if status == "Verified" else ("#FEF3C7" if "Review" in status or "Evidence" in status else "#F1F5F9")
    status_text_color = "#0369A1" if status == "Verified" else ("#B45309" if "Review" in status or "Evidence" in status else "#475569")
    
    status_banner = [
        [
            Paragraph(f"CASE STATUS: <b>{status.upper()}</b>", ParagraphStyle("Stat1", parent=body_style, fontSize=11, textColor=colors.HexColor(status_text_color))),
            Paragraph(f"Suspected Modification: <b>{modification_data.get('suspected_category', 'General Modification')}</b>", ParagraphStyle("Stat2", parent=body_style, fontSize=10)),
            Paragraph(f"Change Score: <b>{modification_data.get('change_score', 0.0)}%</b>", ParagraphStyle("Stat3", parent=body_style, fontSize=10, alignment=2))
        ]
    ]
    status_table = Table(status_banner, colWidths=[180, 220, 140])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(status_bg)),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.HexColor(status_text_color)),
    ]))
    elements.append(status_table)
    elements.append(Spacer(1, 14))

    # 3. Property Information & Policy Reference
    elements.append(Paragraph("1. Property Profile & Registration Details", section_heading))
    prop_info_data = [
        [
            Paragraph(f"<b>Property Ref:</b> {property_data.get('property_reference', 'N/A')}", body_style),
            Paragraph(f"<b>Owner Name:</b> {property_data.get('owner_name', 'N/A')}", body_style)
        ],
        [
            Paragraph(f"<b>Address:</b> {property_data.get('address', 'N/A')}", body_style),
            Paragraph(f"<b>Contact:</b> {property_data.get('owner_contact', 'N/A')}", body_style)
        ],
        [
            Paragraph(f"<b>Coordinates:</b> {property_data.get('latitude', 0.0):.5f}, {property_data.get('longitude', 0.0):.5f}", body_style),
            Paragraph(f"<b>Property Type:</b> {property_data.get('property_type', 'Residential')}", body_style)
        ],
        [
            Paragraph(f"<b>Stories / Floors:</b> {property_data.get('number_of_floors', 1)}", body_style),
            Paragraph(f"<b>Built-up Area:</b> {property_data.get('built_up_area', 'N/A')} sq ft", body_style)
        ],
        [
            Paragraph(f"<b>Reference Policy No:</b> {property_data.get('reference_policy_number', 'N/A')} <i>(recordkeeping only)</i>", body_style),
            Paragraph(f"<b>Monitoring Status:</b> {'Active Monitoring' if property_data.get('monitoring_enabled') else 'Paused'}", body_style)
        ]
    ]
    prop_table = Table(prop_info_data, colWidths=[270, 270])
    prop_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(prop_table)
    elements.append(Spacer(1, 14))

    # 4. Computer Vision Image Comparison & Findings
    elements.append(Paragraph("2. Computer Vision Change Detection & Visual Analysis", section_heading))
    cv_data = [
        [
            Paragraph(f"<b>Detection Date:</b> {str(modification_data.get('detected_at', ''))[:19]}", body_style),
            Paragraph(f"<b>Algorithm:</b> OpenCV ORB + CLAHE + Differential SSIM", body_style)
        ],
        [
            Paragraph(f"<b>Salient Alteration Score:</b> {modification_data.get('change_score', 0.0)}%", body_style),
            Paragraph(f"<b>Primary Signal:</b> {modification_data.get('suspected_category', 'Physical Structure Variance')}", body_style)
        ]
    ]
    cv_table = Table(cv_data, colWidths=[270, 270])
    cv_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
    ]))
    elements.append(cv_table)
    elements.append(Spacer(1, 6))

    analysis = modification_data.get("analysis")
    if analysis and analysis.get("explanation"):
        elements.append(Paragraph(f"<b>AI CV Signal Explanation:</b> {analysis['explanation']}", body_style))
        elements.append(Spacer(1, 4))

    # Image attachments in PDF if available
    analysis = modification_data.get("analysis") or {}
    heatmap_rel = analysis.get("heatmap_image_path")
    diff_rel = analysis.get("diff_image_path")

    # If local image files exist on disk, render them side-by-side
    img_cells = []
    if heatmap_rel:
        heatmap_file = settings.BASE_DIR / heatmap_rel.lstrip("/")
        if heatmap_file.exists():
            img_cells.append([Paragraph("<b>Change Differential Heatmap</b>", body_style), RLImage(str(heatmap_file), width=2.4*inch, height=2.4*inch)])
    if diff_rel:
        diff_file = settings.BASE_DIR / diff_rel.lstrip("/")
        if diff_file.exists():
            img_cells.append([Paragraph("<b>Contours & Bounding Boxes</b>", body_style), RLImage(str(diff_file), width=2.4*inch, height=2.4*inch)])

    if img_cells:
        img_table = Table([[cell[0] for cell in img_cells], [cell[1] for cell in img_cells]], colWidths=[260, 260])
        img_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(img_table)
        elements.append(Spacer(1, 10))

    # 5. Supporting Evidence & AI Authenticity
    elements.append(Paragraph("3. Supporting Evidence Inventory & Authenticity Analysis", section_heading))
    evidence_items = modification_data.get("evidence_items", [])
    if not evidence_items:
        elements.append(Paragraph("<i>No external evidence items submitted for this case yet.</i>", body_style))
    else:
        ev_headers = ["Category", "Filename", "SHA-256 Hash", "Authenticity Evaluation"]
        ev_rows = [[Paragraph(f"<b>{h}</b>", body_style) for h in ev_headers]]
        for ev in evidence_items:
            auth_status = "Not analyzed"
            analyses = ev.get("authenticity_analyses", [])
            if analyses:
                first_auth = analyses[0]
                auth_status = f"{first_auth.get('result', 'Inconclusive')} (Score: {first_auth.get('score', 'N/A')})"
            ev_rows.append([
                Paragraph(ev.get("category", "Photo"), body_style),
                Paragraph(ev.get("original_filename", "File"), body_style),
                Paragraph(f"<font size=6>{ev.get('file_hash', 'N/A')[:16]}...</font>", body_style),
                Paragraph(auth_status, body_style)
            ])
        ev_table = Table(ev_rows, colWidths=[90, 140, 110, 200])
        ev_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(ev_table)

    elements.append(Spacer(1, 14))

    # 6. Human Review Decision & Audit Trail
    elements.append(Paragraph("4. Human Verification Decision & Audit Record", section_heading))
    reviews = modification_data.get("reviews", [])
    if reviews:
        latest_rev = reviews[-1]
        rev_box = [
            [
                Paragraph(f"<b>Reviewer Decision:</b> {latest_rev.get('decision')}", body_style),
                Paragraph(f"<b>Decision Date:</b> {str(latest_rev.get('created_at', ''))[:19]}", body_style)
            ],
            [
                Paragraph(f"<b>Reviewer Rationale:</b> {latest_rev.get('reason')}", body_style),
                Paragraph(f"<b>Internal Notes:</b> {latest_rev.get('notes') or 'None'}", body_style)
            ]
        ]
        rev_table = Table(rev_box, colWidths=[270, 270])
        rev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0FDF4" if latest_rev.get('decision') == 'Verified' else "#FFFBEB")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#86EFAC" if latest_rev.get('decision') == 'Verified' else "#FDE68A")),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(rev_table)
    else:
        elements.append(Paragraph("<i>Case is awaiting formal reviewer determination.</i>", body_style))

    elements.append(Spacer(1, 16))

    # 7. Regulatory & Technical Disclaimers
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceAfter=6))
    elements.append(Paragraph(
        "<b>SYSTEM NOTICE & AUDIT BOUNDARIES:</b> PropertyWatch AI identifies potential physical modifications using "
        "optical satellite differencing and supporting evidence. AI-generated findings are preliminary signals only. "
        "This dossier represents an independent property record and does not constitute an insurance claim approval, "
        "rejection, underwriting assessment, or policy adjustment.",
        disclaimer_style
    ))

    # Build document
    doc.build(elements)
    return str(pdf_path)


def generate_claim_pdf_report(
    claim_dict: Dict[str, Any],
    property_dict: Dict[str, Any],
    policy_dict: Optional[Dict[str, Any]] = None,
    output_filename: Optional[str] = None
) -> str:
    """
    Generate an official, professional PDF claim report incorporating:
    - Claim details and incident description
    - Policy coverage limits, deductibles, endorsements, and exclusions
    - Observed damage indicators and AI damage suggestions (LEVIR-CD)
    - Supporting evidence inventory with SHA-256 hashes
    - Policy-rule execution results
    - Provisional calculations, method, and assumptions
    - Reviewer recommendation and authorized determination block.
    """
    claim_ref = claim_dict.get("claim_reference", "CLM-REPORT")
    if not output_filename:
        output_filename = f"Claim_Report_{claim_ref}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"

    pdf_path = settings.REPORTS_DIR / output_filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    brand_title_style = ParagraphStyle(
        "BrandTitle", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#0F172A")
    )
    brand_sub_style = ParagraphStyle(
        "BrandSub", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor("#64748B")
    )
    section_heading = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=colors.HexColor("#1E293B"), spaceAfter=5
    )
    body_style = ParagraphStyle(
        "ReportBody", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8.5, leading=12, textColor=colors.HexColor("#334155")
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Italic"],
        fontName="Helvetica-Oblique", fontSize=7.5, leading=10, textColor=colors.HexColor("#64748B")
    )

    elements = []

    # 1. Header Banner
    hdr_table = Table([
        [
            Paragraph("<b>PROPERTYWATCH AI</b><br/><font size=8 color='#0284C7'>INSURANCE CLAIM EVALUATION & VERIFICATION DOSSIER</font>", brand_title_style),
            Paragraph(f"<b>CLAIM DOSSIER</b><br/>Ref: <b>{claim_ref}</b><br/>Status: <b>{claim_dict.get('status', 'Submitted')}</b><br/>Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ParagraphStyle("HdrRight", parent=brand_sub_style, alignment=2))
        ]
    ], colWidths=[330, 210])
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(hdr_table)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=12))

    # 2. Claim & Property Summary Table
    pol = policy_dict or {}
    cov = pol.get("coverage_limits", {})
    ded = pol.get("deductibles", {})
    summary_data = [
        [
            Paragraph("<b>Property Reference:</b>", body_style),
            Paragraph(property_dict.get("property_reference", "N/A"), body_style),
            Paragraph("<b>Claim Reference:</b>", body_style),
            Paragraph(claim_ref, body_style)
        ],
        [
            Paragraph("<b>Owner / Insured:</b>", body_style),
            Paragraph(claim_dict.get("owner_name") or property_dict.get("owner_name", "N/A"), body_style),
            Paragraph("<b>Incident Date:</b>", body_style),
            Paragraph(str(claim_dict.get("incident_date", ""))[:10], body_style)
        ],
        [
            Paragraph("<b>Address:</b>", body_style),
            Paragraph(property_dict.get("address", "N/A"), body_style),
            Paragraph("<b>Reported Peril / Cause:</b>", body_style),
            Paragraph(claim_dict.get("reported_cause", "N/A"), body_style)
        ],
        [
            Paragraph("<b>Policy Number:</b>", body_style),
            Paragraph(pol.get("policy_number", property_dict.get("reference_policy_number", "N/A")), body_style),
            Paragraph("<b>Gross Claimed Loss:</b>", body_style),
            Paragraph(f"<b>${claim_dict.get('estimated_loss', 0.0):,.2f}</b>", body_style)
        ],
        [
            Paragraph("<b>Dwelling Limit (Cov A):</b>", body_style),
            Paragraph(f"${cov.get('dwelling', 0.0):,.2f}", body_style),
            Paragraph("<b>Applicable Deductible:</b>", body_style),
            Paragraph(f"${ded.get('standard', 0.0):,.2f} (Std) / ${ded.get('wind_hail', 0.0):,.2f} (W/H)", body_style)
        ]
    ]
    sum_table = Table(summary_data, colWidths=[120, 160, 120, 140])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(sum_table)
    elements.append(Spacer(1, 10))

    # 3. Incident Description
    elements.append(Paragraph("<b>Reported Loss Description:</b>", section_heading))
    elements.append(Paragraph(claim_dict.get("description", "No narrative provided."), body_style))
    elements.append(Spacer(1, 10))

    # 4. Damage Assessment & AI Suggestions
    dmg = claim_dict.get("damage_assessment") or {}
    elements.append(Paragraph("<b>Observed Damage Indicators & Separate AI Status:</b>", section_heading))
    obs_indicators = dmg.get("observed_damage_indicators", [])
    obs_text = ", ".join(obs_indicators) if obs_indicators else "Visual inspection pending."
    ai_sugg = dmg.get("ai_damage_suggestions") or {}
    ai_summary = ai_sugg.get("summary", "No AI damage model is configured; no AI predictions are available.")

    dmg_box = [
        [
            Paragraph(f"<b>Observed Indicators:</b> {obs_text}", body_style),
            Paragraph(f"<b>AI Model:</b> {dmg.get('ai_model_name') or 'Not configured'}", body_style)
        ],
        [
            Paragraph(f"<b>AI Damage Assessment:</b> {ai_summary}", body_style),
            Paragraph(f"<b>Model Confidence:</b> {dmg.get('ai_confidence') or 'N/A'}", body_style)
        ],
        [
            Paragraph(f"<b>Missing Evidence Flags:</b> {', '.join(dmg.get('missing_evidence_flags', [])) or 'None'}", body_style),
            Paragraph(f"<b>Policy Terms Flags:</b> {', '.join(dmg.get('unresolved_policy_terms_flags', [])) or 'None'}", body_style)
        ]
    ]
    dmg_table = Table(dmg_box, colWidths=[330, 210])
    dmg_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(dmg_table)
    elements.append(Spacer(1, 10))

    # 5. Policy Rules Execution Table
    rules = claim_dict.get("rule_executions", [])
    if rules:
        elements.append(Paragraph("<b>Insurance Policy Rules Execution Summary:</b>", section_heading))
        r_rows = [["Rule Code", "Category", "Result", "Explanation"]]
        for r in rules[:6]: # Display first 6 rules
            res_val = r.get("result", "")
            r_rows.append([
                Paragraph(f"<b>{r.get('rule_code')}</b>", body_style),
                Paragraph(r.get("rule_name", "")[:28], body_style),
                Paragraph(f"<b>{res_val}</b>", body_style),
                Paragraph(r.get("explanation", "")[:120], body_style)
            ])
        r_table = Table(r_rows, colWidths=[95, 110, 85, 250])
        r_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(r_table)
        elements.append(Spacer(1, 10))

    # 6. Provisional Calculations
    calcs = claim_dict.get("calculations", [])
    if calcs:
        c_item = calcs[-1]
        elements.append(Paragraph("<b>Provisional Settlement Calculation:</b>", section_heading))
        calc_rows = [
            [
                Paragraph("<b>Gross Claimed Loss:</b>", body_style),
                Paragraph(f"${c_item.get('gross_claimed_loss', 0.0):,.2f}", body_style),
                Paragraph("<b>Non-Covered / Excluded Items:</b>", body_style),
                Paragraph(f"-${c_item.get('non_covered_excluded_amount', 0.0):,.2f}", body_style)
            ],
            [
                Paragraph("<b>Coverage Limit Applied:</b>", body_style),
                Paragraph(f"${c_item.get('applicable_coverage_limit', 0.0):,.2f}", body_style),
                Paragraph(f"<b>Deductible Applied ({c_item.get('deductible_type_applied', 'Std')}):</b>", body_style),
                Paragraph(f"-${c_item.get('applicable_deductible', 0.0):,.2f}", body_style)
            ],
            [
                Paragraph("<b>Net Provisional Calculation:</b>", ParagraphStyle("NetHdr", parent=body_style, fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#0369A1"))),
                Paragraph(f"<b>${c_item.get('provisional_net_payout', 0.0):,.2f}</b>", ParagraphStyle("NetAmt", parent=body_style, fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#0369A1"))),
                Paragraph("<b>Calculation Method:</b>", body_style),
                Paragraph(c_item.get("calculation_method", "Standard formula"), body_style)
            ]
        ]
        calc_table = Table(calc_rows, colWidths=[130, 140, 140, 130])
        calc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BAE6FD")),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(calc_table)
        elements.append(Spacer(1, 10))

    # 7. Reviewer Recommendation & Authorized Decision
    recs = claim_dict.get("recommendations", [])
    decs = claim_dict.get("decisions", [])
    elements.append(Paragraph("<b>Reviewer Recommendation & Final Determination:</b>", section_heading))

    rec_item = recs[-1] if recs else {}
    dec_item = decs[-1] if decs else {}

    sign_rows = [
        [
            Paragraph(f"<b>Reviewer Recommendation:</b> {rec_item.get('recommendation_type', 'Pending Examination')}", body_style),
            Paragraph(f"<b>Authorized Decision:</b> {dec_item.get('decision', 'Pending Authoritative Decision')}", body_style)
        ],
        [
            Paragraph(f"<b>Reasoning:</b> {rec_item.get('reasoning', 'Awaiting review')}", body_style),
            Paragraph(f"<b>Determination Rationale:</b> {dec_item.get('rationale', 'Awaiting decision-maker sign-off')}", body_style)
        ],
        [
            Paragraph(f"<b>Recommended Amount:</b> ${rec_item.get('recommended_amount', 0.0):,.2f}" if rec_item.get('recommended_amount') else "Recommended: As Calculated", body_style),
            Paragraph(f"<b>Authorized Payout:</b> ${dec_item.get('authorized_amount', 0.0):,.2f}" if dec_item.get('authorized_amount') else "Authorized: None / Pending", body_style)
        ]
    ]
    sign_table = Table(sign_rows, colWidths=[270, 270])
    sign_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(sign_table)
    elements.append(Spacer(1, 12))

    # 8. Regulatory Notice
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceAfter=5))
    elements.append(Paragraph(
        "<b>SYSTEM NOTICE & AUDIT BOUNDARIES:</b> PropertyWatch AI assists human reviewers by compiling satellite "
        "observations, computer vision differencing, cryptographically hashed evidence, and policy condition evaluations. "
        "AI models NEVER make automated claim settlement determinations. All claim recommendations and decisions are "
        "conducted and committed by authorized human insurance professionals.",
        disclaimer_style
    ))

    doc.build(elements)
    return str(pdf_path)
