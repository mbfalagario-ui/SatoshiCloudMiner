#!/usr/bin/env python3
"""Foolproof iOS Clone Prompts Playbook — v2.

Fixes from v1:
  * Every Table cell content is now wrapped in a Paragraph so text WORD-WRAPS
    inside its column instead of physically overflowing into the next one.
  * Column widths re-balanced for the wider content cells.
  * Page padding increased on tables so adjacent cells never touch.

Additions in v2:
  * Section 6 — full sub-playbook for cloning the app for Litecoin + Dogecoin.
  * Section 7 (renumbered) — TL;DR / Reality-checks (same as v1).
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

OUT_PATH = Path("/app/store/playbook/Foolproof_iOS_Clone_Prompts_Playbook.pdf")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
INK = HexColor("#0B0E14")
NEON = HexColor("#5AF4AC")
NEON_DIM = HexColor("#1d3a2d")
PAPER = HexColor("#FFFFFF")
SOFT = HexColor("#F4F6F8")
MUTED = HexColor("#5b6470")
ACCENT = HexColor("#0BA86F")
BOX_BG = HexColor("#101720")
BOX_BG_LIGHT = HexColor("#F7FBF9")
BOX_BORDER = HexColor("#1d3a2d")
PILL_BG = HexColor("#143226")
RED = HexColor("#E5484D")
AMBER = HexColor("#E08503")
LTC_COL = HexColor("#345D9D")          # litecoin silver-blue
DOGE_COL = HexColor("#C2A633")         # dogecoin gold

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
styles = getSampleStyleSheet()
title_xl = ParagraphStyle("title_xl", parent=styles["Title"], fontName="Helvetica-Bold",
                          fontSize=34, leading=40, textColor=PAPER, alignment=TA_LEFT,
                          spaceAfter=10)
h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=22, leading=28, textColor=INK, spaceBefore=8, spaceAfter=10)
h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=15, leading=20, textColor=ACCENT, spaceBefore=18, spaceAfter=6)
h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                    fontSize=11, leading=14, textColor=INK, spaceBefore=6, spaceAfter=4)
body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=10.5, leading=15, textColor=INK, alignment=TA_LEFT,
                      spaceAfter=6)
muted = ParagraphStyle("muted", parent=body, textColor=MUTED, fontSize=9.5, leading=13)
# Used for ALL table body cells so text word-wraps inside its column.
tbl_cell = ParagraphStyle("tbl_cell", parent=styles["Normal"], fontName="Helvetica",
                          fontSize=8.8, leading=12, textColor=INK, alignment=TA_LEFT,
                          spaceAfter=0, spaceBefore=0)
tbl_cell_mono = ParagraphStyle("tbl_cell_mono", parent=tbl_cell, fontName="Courier",
                               fontSize=8.4, leading=11.5)
tbl_head = ParagraphStyle("tbl_head", parent=styles["Normal"], fontName="Helvetica-Bold",
                          fontSize=9.2, leading=11.5, textColor=NEON, alignment=TA_LEFT,
                          spaceAfter=0)
tbl_num = ParagraphStyle("tbl_num", parent=tbl_cell, fontName="Helvetica-Bold",
                         fontSize=10, textColor=ACCENT, alignment=TA_CENTER)


# ---------------------------------------------------------------------------
# Page templates
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = LETTER
MARGIN = 0.6 * inch


def _draw_cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=0)
    canvas.setFillColor(NEON)
    canvas.rect(0, PAGE_H - 8, PAGE_W, 8, fill=True, stroke=0)
    canvas.setFillColor(PILL_BG)
    canvas.roundRect(MARGIN, PAGE_H - 1.2 * inch, 3.2 * inch, 0.34 * inch,
                     0.17 * inch, fill=True, stroke=0)
    canvas.setFillColor(NEON)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(MARGIN + 0.18 * inch, PAGE_H - 1.07 * inch,
                      "● SATOSHI CLOUD MINER · POSTMORTEM · v2")
    canvas.setFillColor(NEON_DIM)
    canvas.rect(0, 0, PAGE_W, 6, fill=True, stroke=0)
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(NEON)
    canvas.drawString(MARGIN, 0.42 * inch,
                      "Foolproof iOS Clone Prompts · Playbook v2.0 · 2026")
    canvas.drawRightString(PAGE_W - MARGIN, 0.42 * inch,
                           "Now includes Litecoin + Dogecoin variant")
    canvas.restoreState()


def _draw_content_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, PAGE_H - 0.45 * inch, PAGE_W, 0.45 * inch, fill=True, stroke=0)
    canvas.setFillColor(NEON)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(MARGIN, PAGE_H - 0.30 * inch,
                      "FOOLPROOF iOS CLONE PROMPTS PLAYBOOK · v2")
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.30 * inch,
                           f"Page {doc.page}")
    canvas.setFillColor(NEON)
    canvas.rect(0, 0.32 * inch, PAGE_W, 2, fill=True, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(MARGIN, 0.16 * inch,
                      "Copy each prompt verbatim into a fresh Emergent chat to skip the rebuild loops.")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def section_pill(label: str):
    pill = Table([[Paragraph(
        f'<font color="{NEON.hexval()}"><b>{label}</b></font>',
        ParagraphStyle("pill", parent=styles["Normal"], fontName="Helvetica-Bold",
                       fontSize=9, leading=12, textColor=NEON),
    )]], colWidths=[2.6 * inch])
    pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PILL_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, NEON_DIM),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return pill


def callout(text: str, color=AMBER, label: str = "WHY"):
    para = Paragraph(
        f'<font color="{color.hexval()}"><b>{label}:</b></font> '
        f'<font color="{INK.hexval()}">{text}</font>',
        ParagraphStyle("co", parent=body, fontSize=9.5, leading=13,
                       leftIndent=12, rightIndent=12),
    )
    t = Table([[para]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFF8E6")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def prompt_box(prompt_no: str, title: str, text_lines: list[str], dark: bool = True):
    bg = BOX_BG if dark else BOX_BG_LIGHT
    fg_label = NEON if dark else ACCENT
    fg_text = PAPER if dark else INK
    chrome = NEON_DIM if dark else BOX_BORDER

    header = Paragraph(
        f'<font color="{fg_label.hexval()}"><b>► PROMPT {prompt_no}</b></font>'
        f'&nbsp;&nbsp;<font color="{fg_text.hexval()}"><b>{title}</b></font>',
        ParagraphStyle("phdr", parent=styles["Normal"], fontName="Helvetica-Bold",
                       fontSize=10, leading=13, textColor=fg_text),
    )
    body_html = "<br/>".join(text_lines)
    body_para = Paragraph(
        f'<font color="{fg_text.hexval()}">{body_html}</font>',
        ParagraphStyle("ptxt", parent=styles["Normal"], fontName="Courier",
                       fontSize=8.6, leading=12.5, textColor=fg_text),
    )
    inner = [[header], [Spacer(1, 5)], [body_para]]
    t = Table(inner, colWidths=[PAGE_W - 2 * MARGIN - 24])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    outer = Table([[t]], colWidths=[PAGE_W - 2 * MARGIN])
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 1, chrome),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return KeepTogether([outer, Spacer(1, 10)])


def _cell(text: str, mono: bool = False, num: bool = False):
    """Wrap raw text in a Paragraph so it word-wraps. This is THE v1->v2 fix."""
    style = tbl_num if num else (tbl_cell_mono if mono else tbl_cell)
    return Paragraph(text, style)


def _head(text: str):
    return Paragraph(text, tbl_head)


def styled_table(rows, col_widths, dark_header: bool = True, num_col: int | None = None,
                 mono_cols: list[int] | None = None):
    """Build a table with word-wrapped cells + clean chrome."""
    mono_cols = mono_cols or []
    # Wrap header row
    header_row = [_head(c) if not isinstance(c, Paragraph) else c for c in rows[0]]
    body_rows = []
    for row in rows[1:]:
        new_row = []
        for j, c in enumerate(row):
            if isinstance(c, Paragraph):
                new_row.append(c)
            else:
                is_num = (num_col is not None and j == num_col)
                is_mono = j in mono_cols
                new_row.append(_cell(str(c), mono=is_mono, num=is_num))
        body_rows.append(new_row)
    data = [header_row] + body_rows

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK if dark_header else ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("LINEAFTER", (0, 0), (-2, -1), 0.2, HexColor("#E7ECEF")),
    ]
    if num_col is not None:
        style.append(("ALIGN", (num_col, 1), (num_col, -1), "CENTER"))
    t.setStyle(TableStyle(style))
    return t


# ===========================================================================
# Build story
# ===========================================================================
story = []

# --- COVER PAGE -------------------------------------------------------------
story.append(Spacer(1, 1.5 * inch))
story.append(Paragraph(
    '<font color="#FFFFFF">Foolproof</font><br/>'
    '<font color="#5AF4AC">iOS Clone Prompts</font><br/>'
    '<font color="#FFFFFF">Playbook</font>',
    title_xl,
))
story.append(Spacer(1, 0.18 * inch))
story.append(Paragraph(
    'Copy/paste prompts that ship an Expo + FastAPI iOS app to '
    'TestFlight with zero rebuild loops. Includes a Litecoin + '
    'Dogecoin variant.',
    ParagraphStyle("cs1", parent=styles["Normal"], fontName="Helvetica",
                   fontSize=14, leading=20, textColor=HexColor("#C5D6CC")),
))
story.append(Spacer(1, 0.4 * inch))

who = [
    "● You are about to clone an iOS app and ship it to TestFlight.",
    "● You don't want a 20-build, 20-credit rebuild loop.",
    "● You want to read a few pages, copy, paste, walk away.",
    "● This playbook is built for exactly that.",
]
cover_pill = Table(
    [[Paragraph(
        f'<font color="#5AF4AC"><b>HOW TO USE</b></font><br/><br/>' +
        '<br/>'.join(f'<font color="#FFFFFF" size="11">{line}</font>' for line in who),
        ParagraphStyle("cv", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=11, leading=18, textColor=PAPER),
    )]],
    colWidths=[PAGE_W - 2 * MARGIN],
)
cover_pill.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#101720")),
    ("BOX", (0, 0), (-1, -1), 1.2, NEON),
    ("LEFTPADDING", (0, 0), (-1, -1), 18),
    ("RIGHTPADDING", (0, 0), (-1, -1), 18),
    ("TOPPADDING", (0, 0), (-1, -1), 16),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
]))
story.append(cover_pill)

story.append(Spacer(1, 0.35 * inch))
story.append(Paragraph(
    '<font color="#5AF4AC"><b>BASED ON</b></font>'
    '&nbsp;&nbsp;'
    '<font color="#FFFFFF" size="10">'
    'Builds #11 → #20 of Satoshi Cloud Miner. We made every mistake so you '
    'do not have to. The prompts here would have collapsed that journey '
    'into 1–2 EAS builds.'
    '</font>',
    ParagraphStyle("based", parent=styles["Normal"], fontName="Helvetica",
                   fontSize=10, leading=16, textColor=PAPER),
))
story.append(Spacer(1, 0.18 * inch))
story.append(Paragraph(
    '<font color="#5AF4AC"><b>WHAT IS NEW IN v2</b></font>'
    '&nbsp;&nbsp;'
    '<font color="#FFFFFF" size="10">'
    '(1) All tables re-rendered with word-wrap so no text overlaps another '
    'column. (2) New Section 6 — a complete sub-playbook for cloning the '
    'same architecture for Litecoin + Dogecoin (one app, both coins).'
    '</font>',
    ParagraphStyle("v2", parent=styles["Normal"], fontName="Helvetica",
                   fontSize=10, leading=16, textColor=PAPER),
))

# --- PAGE 2: HOW IT WORKS ---------------------------------------------------
story.append(NextPageTemplate("content"))
story.append(PageBreak())

story.append(section_pill("0 · QUICKSTART"))
story.append(Spacer(1, 6))
story.append(Paragraph("How to use this playbook", h1))
story.append(Paragraph(
    "This document contains <b>10 numbered prompts</b> + <b>1 master prompt</b> "
    "for the Bitcoin / Satoshi Cloud Miner case, plus a full <b>Litecoin + "
    "Dogecoin variant</b> in Section 6. If you follow them in order, you "
    "will skip every painful rebuild loop we hit (App Store Connect IAP "
    "mismatches, icon white-borders, simulated data, iPad screenshot "
    "rejections, tracking-permission rejections, etc.).",
    body,
))
story.append(Spacer(1, 6))
story.append(Paragraph("The three rules", h2))
rules_data = [
    [_cell("<b>1 · Send the Master Prompt first.</b>"),
     _cell("It declares every constraint upfront. Without it, the agent invents assumptions that cost you credits.")],
    [_cell("<b>2 · Send each follow-up prompt in order.</b>"),
     _cell("Each one assumes the previous step is done. Do not skip ahead — they are sequential.")],
    [_cell("<b>3 · Replace every &lt;…&gt; placeholder.</b>"),
     _cell("Wherever you see angle brackets, paste your real value. If you cannot fill one, ask the agent to source it for you in the same chat.")],
]
t = Table(rules_data, colWidths=[1.9 * inch, PAGE_W - 2 * MARGIN - 1.9 * inch])
t.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ("TOPPADDING", (0, 0), (-1, -1), 9),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ("BACKGROUND", (0, 0), (0, -1), SOFT),
    ("LINEABOVE", (0, 0), (-1, 0), 0.5, BOX_BORDER),
    ("LINEBELOW", (0, -1), (-1, -1), 0.5, BOX_BORDER),
    ("LINEBETWEEN", (0, 0), (-1, -1), 0.3, BOX_BORDER),
]))
story.append(t)
story.append(Spacer(1, 14))

story.append(Paragraph("Before you paste anything — collect these credentials", h2))
creds_rows = [
    ["Item", "Where to get it", "Placeholder you will replace"],
    ["Apple Team ID", "developer.apple.com → Membership", "&lt;TEAM_ID&gt;"],
    ["ASC App Manager API key (.p8)",
     "App Store Connect → Users &amp; Access → Integrations → App Store Connect API",
     "&lt;ASC_KEY_ID&gt; / &lt;ASC_ISSUER_ID&gt; / &lt;ASC_P8&gt;"],
    ["In-App Purchase Server API key (.p8)",
     "App Store Connect → Users &amp; Access → Integrations → In-App Purchase",
     "&lt;IAP_KEY_ID&gt; / &lt;IAP_P8&gt;"],
    ["Expo personal access token",
     "expo.dev → account settings → access tokens",
     "&lt;EXPO_TOKEN&gt;"],
    ["Existing ASC app record",
     "App Store Connect → Apps",
     "&lt;BUNDLE_ID&gt; / &lt;ASC_APP_ID&gt;"],
    ["LLM key",
     "Emergent universal LLM key (recommended), or your OpenAI / Anthropic / Gemini key",
     "&lt;LLM_KEY&gt;"],
    ["Payment / wallet keys",
     "Whatever vendor (Stripe, Blink, BTCPay, NowPayments, Twilio…)",
     "&lt;VENDOR_KEY&gt;"],
]
story.append(styled_table(
    creds_rows,
    col_widths=[1.7 * inch, 3.0 * inch, 2.5 * inch],
    mono_cols=[2],
))

# --- PAGE 3: MASTER PROMPT --------------------------------------------------
story.append(PageBreak())
story.append(section_pill("1 · THE MASTER PROMPT"))
story.append(Spacer(1, 6))
story.append(Paragraph("Send this one prompt FIRST. Always.", h1))
story.append(Paragraph(
    "This is the single most important message in the whole playbook. "
    "Send it as the very first message in a fresh chat. Every gotcha that "
    "burned credits on Satoshi Cloud Miner is preempted by a constraint in "
    "this prompt.",
    body,
))
story.append(callout(
    "Without this prompt, the agent will assume sensible defaults that do not "
    "match Apple's reality (iPad screenshots required, hardcoded BTC rate, "
    "AI-generated icon with white border, etc.).",
    color=AMBER, label="WHY",
))
story.append(Spacer(1, 6))

master_lines = [
    "<b>GOAL</b>",
    "Clone &lt;SOURCE APP NAME + URL OR SCREENSHOTS&gt; into a production-ready",
    "iOS app called &lt;MY APP NAME&gt; and ship it to TestFlight + the App",
    "Store. I will NOT review interim builds — deliver the final result.",
    "You decide every implementation detail; I only weigh in on product",
    "behavior or branding.",
    "&nbsp;",
    "<b>MY CREDENTIALS (use these, do not ask later)</b>",
    "&nbsp;&nbsp;Apple Team ID:        &lt;TEAM_ID&gt;",
    "&nbsp;&nbsp;ASC API key:          &lt;ASC_KEY_ID&gt; / &lt;ASC_ISSUER_ID&gt; (.p8 attached)",
    "&nbsp;&nbsp;IAP Server API key:   &lt;IAP_KEY_ID&gt; (.p8 attached)",
    "&nbsp;&nbsp;EXPO_TOKEN:           &lt;EXPO_TOKEN&gt;",
    "&nbsp;&nbsp;ASC app record:       bundle=&lt;BUNDLE_ID&gt; app_id=&lt;ASC_APP_ID&gt;",
    "&nbsp;&nbsp;LLM key:              Use the Emergent universal LLM key",
    "&nbsp;&nbsp;Payment/wallet keys:  &lt;VENDOR_KEYS_HERE&gt;",
    "&nbsp;",
    "<b>NON-NEGOTIABLE CONSTRAINTS — fail the build if any is violated</b>",
    "1. No simulated data. No hardcoded prices, fake rates, deterministic-",
    "&nbsp;&nbsp;&nbsp;random AI, or MOCK_* constants. If a real source is unavailable,",
    "&nbsp;&nbsp;&nbsp;surface 'unavailable' in the UI rather than fake it.",
    "2. App Store Connect is the SOURCE OF TRUTH for IAP product IDs.",
    "&nbsp;&nbsp;&nbsp;Enumerate ASC via API BEFORE writing any IAP code. Never invent",
    "&nbsp;&nbsp;&nbsp;a product_id in the backend that doesn't already exist in ASC.",
    "3. App icon: 1024x1024 PNG, RGB (no alpha), full-bleed dark background,",
    "&nbsp;&nbsp;&nbsp;no white border, no transparent corners. Programmatically sample",
    "&nbsp;&nbsp;&nbsp;edge pixels before committing.",
    "4. AI-generated assets must have correct magic bytes. If filename says",
    "&nbsp;&nbsp;&nbsp;.png, file MUST start with 89 50 4E 47.",
    "5. supportsTablet: false by default (otherwise Apple requires iPad",
    "&nbsp;&nbsp;&nbsp;screenshots).",
    "6. Do NOT declare iOS permissions you don't use. No",
    "&nbsp;&nbsp;&nbsp;NSUserTrackingUsageDescription unless an SDK actually requests",
    "&nbsp;&nbsp;&nbsp;tracking — otherwise Apple forces the App Privacy questionnaire.",
    "7. Quality gates before EVERY EAS build: npx expo-doctor (must be N/N),",
    "&nbsp;&nbsp;&nbsp;yarn tsc --noEmit, backend tests. Block the build on any failure.",
    "8. Use the App Store Connect API to upload everything — description,",
    "&nbsp;&nbsp;&nbsp;keywords, screenshots, preview video, IAP linkage, review",
    "&nbsp;&nbsp;&nbsp;submission. Do NOT write me a 'manual upload guide'.",
    "&nbsp;",
    "<b>DEFINITION OF DONE</b>",
    "- App Store Connect shows WAITING_FOR_REVIEW with all IAPs auto-bundled.",
    "- Backend regression tests pass.",
    "- A persistent auto_ship watcher is armed for v1.0.1 so I never need",
    "&nbsp;&nbsp;to manually ship a follow-up build.",
    "&nbsp;",
    "Confirm you understand every constraint before writing code. Push",
    "back on anything that needs Apple policy exceptions (gambling, crypto",
    "withdrawals, age-gated content). Then proceed end-to-end.",
]
story.append(prompt_box("00", "THE MASTER PROMPT", master_lines, dark=True))

# --- PAGE 4: GOTCHAS --------------------------------------------------------
story.append(PageBreak())
story.append(section_pill("2 · THE 7 GOTCHAS"))
story.append(Spacer(1, 6))
story.append(Paragraph("Failures we hit — and the one sentence that would have prevented each", h1))
story.append(Paragraph(
    "Add all seven lines to the bottom of the Master Prompt if you want "
    "belt-and-suspenders coverage.",
    muted,
))
story.append(Spacer(1, 8))
gotchas = [
    ["#", "What went wrong on Satoshi Cloud Miner", "Sentence to add to your prompt"],
    ["1",
     "starter_099 IAP existed in backend code but Apple never had it. Every TestFlight tap returned 'Purchase failed'.",
     "Before writing any IAP code, enumerate App Store Connect IAPs via the v2 API and use those product IDs as the source of truth."],
    ["2",
     "BTC_USD_RATE = 65000.0 was hardcoded as a 'simulated rate' and ran in production for weeks.",
     "Any price, FX, or rate must come from a live API with a fallback cascade. No magic numbers outside true constants like SATS_PER_BTC."],
    ["3",
     "AI Trading Agents were deterministic random — the UI said 'AI' but the data was random.choice().",
     "Anywhere the UI shows an 'AI' or 'live' value, it must be a real LLM/API call with cache and offline fallback. No fake AI."],
    ["4",
     "AI-generated icon was JPEG bytes saved as .png, which broke the EAS expo-doctor check.",
     "For every generated image, verify the file's magic bytes match the extension. Re-encode through PIL if mismatched."],
    ["5",
     "Icon had a 69-px white border baked in, which produced a visible white ring around the app on the home screen.",
     "Sample the four edges of any 1024×1024 icon. If pixels above (235,235,235) are found within 80 px of the edge, replace with the brand background."],
    ["6",
     "supportsTablet:true plus an unused NSUserTrackingUsageDescription caused submission rejection.",
     "Default supportsTablet:false. Never add a permission string unless I explicitly request the feature."],
    ["7",
     "Apple's 'first IAP must ship with first version' plus the screenshot lockout once a version enters WAITING_FOR_REVIEW caught us mid-flow.",
     "Use the reviewSubmissions API (not inAppPurchaseSubmissions). Upload all metadata and screenshots BEFORE attaching the version to the review submission."],
]
story.append(styled_table(
    gotchas,
    col_widths=[0.35 * inch, 3.05 * inch, 3.8 * inch],
    num_col=0,
))

# --- PAGES 5–7: THE 10 NUMBERED PROMPTS ------------------------------------
story.append(PageBreak())
story.append(section_pill("3 · THE 10 NUMBERED PROMPTS"))
story.append(Spacer(1, 6))
story.append(Paragraph("Send these in order, one per message", h1))
story.append(Paragraph(
    "Each prompt assumes the previous one finished cleanly. Wait for the "
    "agent to confirm success (a green log line, a screenshot, or an HTTP "
    "200 response) before sending the next one.",
    body,
))
story.append(Spacer(1, 6))

story.append(prompt_box("01", "Lock in the product spec", [
    "Here is my PRODUCT_SPEC.md (attached). Read every section and confirm",
    "you understand it. Specifically confirm:",
    "&nbsp;&nbsp;- the exact list of screens",
    "&nbsp;&nbsp;- every IAP tier with product_id, type, price",
    "&nbsp;&nbsp;- every external integration with key scopes",
    "&nbsp;&nbsp;- every iOS permission with the code path that uses it",
    "&nbsp;",
    "Push back on anything that requires an Apple App Store policy",
    "exception. Propose alternatives where needed. Reply with a TL;DR",
    "of the spec in your own words so I know we are aligned.",
], dark=False))

story.append(prompt_box("02", "Build the backend + Expo skeleton (no UI yet)", [
    "Build the FastAPI backend + Expo Router skeleton.",
    "&nbsp;&nbsp;- Auth: email+password + JWT, with /api/auth/{register,login,me}.",
    "&nbsp;&nbsp;- All data models from the spec, with MongoDB indexes.",
    "&nbsp;&nbsp;- Every API endpoint stubbed with real schema responses (200 OK).",
    "&nbsp;&nbsp;- expo-router wired with app/(tabs)/_layout.tsx, but tabs",
    "&nbsp;&nbsp;&nbsp;&nbsp;render placeholder Text only — no real UI yet.",
    "&nbsp;",
    "Then run the deep_testing_backend_v2 agent and paste the report.",
    "Do NOT proceed to UI until backend regression is green.",
], dark=True))

story.append(prompt_box("03", "Bootstrap App Store Connect (BEFORE any IAP code)", [
    "Using my ASC App Manager key, do this end-to-end via the ASC API:",
    "&nbsp;&nbsp;1. Verify the existing app record &lt;ASC_APP_ID&gt;.",
    "&nbsp;&nbsp;2. Create every IAP from PRODUCT_SPEC.md with the correct type",
    "&nbsp;&nbsp;&nbsp;&nbsp;(consumable / non-consumable / subscription), localized name,",
    "&nbsp;&nbsp;&nbsp;&nbsp;price tier, and review screenshot (use a 1290x2796 placeholder",
    "&nbsp;&nbsp;&nbsp;&nbsp;PNG if needed).",
    "&nbsp;&nbsp;3. Move each IAP to READY_TO_SUBMIT state.",
    "&nbsp;",
    "After running, print the FINAL list of product IDs that exist in ASC.",
    "These are the source of truth for the backend SHOP_PACKAGES table.",
    "If any spec IAP cannot be created via API (e.g. missing review screenshot),",
    "tell me explicitly so we remove it from the spec.",
], dark=False))

story.append(PageBreak())
story.append(prompt_box("04", "Wire integrations one at a time, prove each is live", [
    "For each integration in my spec, do this loop:",
    "&nbsp;&nbsp;1. Write the integration module (one file in backend/integrations/).",
    "&nbsp;&nbsp;2. Add a /api/diag/&lt;integration_name&gt; endpoint that performs ONE",
    "&nbsp;&nbsp;&nbsp;&nbsp;real round-trip to the vendor (e.g. fetch BTC rate, validate",
    "&nbsp;&nbsp;&nbsp;&nbsp;a test Apple receipt, send a $0.001 Lightning ping).",
    "&nbsp;&nbsp;3. Hit it and paste the JSON response in your reply.",
    "&nbsp;",
    "Do NOT move to the next integration until the diag endpoint returns",
    "a real, non-mocked response. No 'MOCKED' values anywhere.",
], dark=True))

story.append(prompt_box("05", "Build the UI from the spec", [
    "Build every screen from PRODUCT_SPEC.md.",
    "&nbsp;&nbsp;- After EVERY screen, run yarn tsc --noEmit and npx expo-doctor.",
    "&nbsp;&nbsp;- Capture a screenshot of the rendered screen from the web preview",
    "&nbsp;&nbsp;&nbsp;&nbsp;(http://localhost:3000) at iPhone 14 Pro dimensions and paste it.",
    "&nbsp;&nbsp;- Use real data from the integrations wired in Prompt 04 — no",
    "&nbsp;&nbsp;&nbsp;&nbsp;placeholder text, no Lorem Ipsum, no MOCK_*.",
    "&nbsp;",
    "If any check fails, stop and fix that screen before moving on.",
    "Do not pile up TODOs.",
], dark=False))

story.append(prompt_box("06", "Generate marketing assets — with pixel-level verification", [
    "Generate all App Store marketing assets in ONE batch:",
    "&nbsp;&nbsp;- App icon: 1024x1024 PNG, RGB only (no alpha), brand-colored",
    "&nbsp;&nbsp;&nbsp;&nbsp;full-bleed background, glyph centered, NO white border.",
    "&nbsp;&nbsp;- 12 screenshots: 1290x2796 (iPhone 6.7), 1242x2688 (6.5), 1242x2208 (5.5).",
    "&nbsp;&nbsp;- 1 App Preview video: 1080x1920 H.264, 15-30s, STEREO or SILENT",
    "&nbsp;&nbsp;&nbsp;&nbsp;audio only (no mono — Apple's encoder rejects MOV_RESAVE_STEREO).",
    "&nbsp;",
    "Then run a verification pass that PROVES:",
    "&nbsp;&nbsp;- icon edge pixels (sample 10 corners within 20 px of edge) are NOT white",
    "&nbsp;&nbsp;- every PNG starts with bytes 89 50 4E 47",
    "&nbsp;&nbsp;- video probe (ffprobe) shows acodec=aac stereo OR no audio stream",
    "&nbsp;",
    "Paste the pixel-sample report. Re-encode if anything fails.",
], dark=True))

story.append(prompt_box("07", "Harden app.json for Apple submission", [
    "Update /app/frontend/app.json with these EXACT settings before any",
    "EAS build:",
    "&nbsp;&nbsp;- ios.supportsTablet: false",
    "&nbsp;&nbsp;- ios.config.usesNonExemptEncryption: false",
    "&nbsp;&nbsp;- ios.infoPlist.ITSAppUsesNonExemptEncryption: false",
    "&nbsp;&nbsp;- Remove every permission string (NSCameraUsageDescription,",
    "&nbsp;&nbsp;&nbsp;&nbsp;NSUserTrackingUsageDescription, etc.) UNLESS my spec lists a",
    "&nbsp;&nbsp;&nbsp;&nbsp;feature that actually requires it.",
    "&nbsp;&nbsp;- version: 1.0.0    buildNumber: 1",
    "&nbsp;",
    "Then run npx expo-doctor — must show N/N checks passed.",
], dark=False))

story.append(PageBreak())
story.append(prompt_box("08", "Ship to App Store Connect end-to-end (one shot)", [
    "Now run the full ship sequence WITHOUT pausing for input:",
    "&nbsp;&nbsp;1. npx eas build --platform ios --profile production --non-interactive",
    "&nbsp;&nbsp;&nbsp;&nbsp;Wait for it to finish.",
    "&nbsp;&nbsp;2. npx eas submit --platform ios --non-interactive (uses my ASC key).",
    "&nbsp;&nbsp;3. Poll the ASC builds API until the build state is VALID.",
    "&nbsp;&nbsp;4. Attach the build to App Store Version 1.0 via the ASC API.",
    "&nbsp;&nbsp;5. Upload description / keywords / supportURL / marketingURL /",
    "&nbsp;&nbsp;&nbsp;&nbsp;promotionalText via the appStoreVersionLocalizations PATCH.",
    "&nbsp;&nbsp;6. Upload the 12 screenshots + the App Preview video.",
    "&nbsp;&nbsp;7. Create a reviewSubmission, attach the version as a",
    "&nbsp;&nbsp;&nbsp;&nbsp;reviewSubmissionItem (IAPs auto-bundle), PATCH submitted:true.",
    "&nbsp;",
    "Print the final reviewSubmission state. If anything fails, surface",
    "Apple's exact error message — do NOT retry blindly.",
], dark=True))

story.append(prompt_box("09", "Arm the auto_ship watcher for v1.0.1+", [
    "Create /app/backend/services/auto_ship.py with these properties:",
    "&nbsp;&nbsp;- Runs every 30 min via APScheduler inside the FastAPI worker.",
    "&nbsp;&nbsp;- Polls the ASC API for version 1.0's appStoreState.",
    "&nbsp;&nbsp;- When the state becomes READY_FOR_SALE or PENDING_APPLE_RELEASE,",
    "&nbsp;&nbsp;&nbsp;&nbsp;it auto-ships the next version: bump app.json, run eas build,",
    "&nbsp;&nbsp;&nbsp;&nbsp;eas submit, attach to version 1.0.1, upload fresh screenshots,",
    "&nbsp;&nbsp;&nbsp;&nbsp;submit reviewSubmission.",
    "&nbsp;&nbsp;- Idempotent: stores state in /app/store/.auto_ship_state.json so",
    "&nbsp;&nbsp;&nbsp;&nbsp;it never double-ships.",
    "&nbsp;",
    "Confirm the watcher's first tick logged successfully and paste the log",
    "line that proves it.",
], dark=False))

story.append(prompt_box("10", "Final smoke test + hand-off", [
    "Run a final regression pass:",
    "&nbsp;&nbsp;- deep_testing_backend_v2 (all critical endpoints).",
    "&nbsp;&nbsp;- Take a fresh web preview screenshot of every tab.",
    "&nbsp;&nbsp;- curl GET /api/system/btc_rate (or your live-data endpoint) and",
    "&nbsp;&nbsp;&nbsp;&nbsp;paste the JSON to prove no simulated data is left.",
    "&nbsp;&nbsp;- Show the ASC final state: version, build, IAP states,",
    "&nbsp;&nbsp;&nbsp;&nbsp;reviewSubmission.",
    "&nbsp;",
    "Then write a /app/HANDOFF.md that documents:",
    "&nbsp;&nbsp;- every credential the app uses + where it lives",
    "&nbsp;&nbsp;- every cron job + its schedule",
    "&nbsp;&nbsp;- how to invoke the auto_ship watcher manually if needed",
    "I want to be able to hand this to ANY future engineer in one file.",
], dark=True))

# --- PAGE 8: TWO LINES THAT SAVE 70% --------------------------------------
story.append(PageBreak())
story.append(section_pill("4 · IF YOU ONLY READ TWO LINES"))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "The two sentences that would have saved 70% of the credits on Satoshi Cloud Miner", h1
))
story.append(Paragraph(
    "If you can only send two sentences before letting the agent work, "
    "these are the two.",
    body,
))
story.append(Spacer(1, 10))

q_data = [
    [Paragraph(
        '<font color="#5AF4AC" size="11"><b>SENTENCE 1</b></font><br/><br/>'
        '<font color="#FFFFFF" size="11"><i>'
        '"Before writing a single line of IAP code, enumerate my App Store '
        'Connect product IDs via API and tell me the canonical list. I will '
        'only use those — no new SKUs invented in the backend."'
        '</i></font>',
        ParagraphStyle("ql", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=11, leading=16, textColor=PAPER),
    )],
    [Spacer(1, 14)],
    [Paragraph(
        '<font color="#5AF4AC" size="11"><b>SENTENCE 2</b></font><br/><br/>'
        '<font color="#FFFFFF" size="11"><i>'
        '"Any \'AI\', \'rate\', \'price\', or \'live data\' field in the UI '
        'MUST be backed by a real provider with a fallback cascade. Show me '
        'one curl response per data source proving the wire is live before '
        'connecting it to the UI."'
        '</i></font>',
        ParagraphStyle("ql2", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=11, leading=16, textColor=PAPER),
    )],
]
qt = Table(q_data, colWidths=[PAGE_W - 2 * MARGIN])
qt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), INK),
    ("BOX", (0, 0), (-1, -1), 1.5, NEON),
    ("LEFTPADDING", (0, 0), (-1, -1), 24),
    ("RIGHTPADDING", (0, 0), (-1, -1), 24),
    ("TOPPADDING", (0, 0), (-1, -1), 18),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
]))
story.append(qt)

story.append(Spacer(1, 18))
story.append(Paragraph("The fool-proof header — paste it as the first 8 lines of any iOS-clone prompt", h2))
header_lines = [
    "ROLE: ship-the-app engineer, not interim-demo engineer.",
    "DEFINITION OF DONE: WAITING_FOR_REVIEW in App Store Connect.",
    "CREDS: &lt;paste all keys here, do not ask me later&gt;",
    "HARD CONSTRAINTS:",
    "&nbsp;&nbsp;- Zero simulated data.",
    "&nbsp;&nbsp;- App Store Connect is the source of truth for product IDs.",
    "&nbsp;&nbsp;- Full-bleed RGB icon, no alpha, no white border, pixel-verified.",
    "&nbsp;&nbsp;- supportsTablet:false unless explicitly requested.",
    "&nbsp;&nbsp;- No unused iOS permission strings.",
    "&nbsp;&nbsp;- expo-doctor + tsc must pass before any EAS build.",
    "&nbsp;&nbsp;- Use the ASC API for every upload; no manual upload guides.",
    "EXIT CRITERIA: auto_ship watcher armed for the next version.",
]
story.append(prompt_box("HEADER", "FOOL-PROOF HEADER", header_lines, dark=True))

# --- PAGE 9+: TL;DR -------------------------------------------------------
story.append(PageBreak())
story.append(section_pill("5 · TL;DR — THE ONE LESSON"))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Verify the platform's reality BEFORE writing the code that depends on it",
    h1,
))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "Both of the most expensive bugs on Satoshi Cloud Miner — the "
    "<b>starter_099 'Purchase failed'</b> in TestFlight and the "
    "<b>white-border app icon</b> — came from the same mistake: writing "
    "code based on what we <i>assumed</i> the platform or asset-generator "
    "had produced, instead of programmatically inspecting what was actually "
    "there.",
    body,
))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "If every future iOS clone starts with a 5-minute "
    "<i>'enumerate the platform reality'</i> step (list ASC's actual IAPs, "
    "sample the icon's actual edge pixels, probe the actual video's audio "
    "track), you ship in 1–2 EAS builds. Not 20.",
    body,
))
story.append(Spacer(1, 18))

story.append(Paragraph("The four reality-checks every iOS clone needs on Day 1", h2))
checks = [
    ["#", "Reality check", "How to do it (one line)"],
    ["1",
     "What product IDs exist in App Store Connect?",
     "GET /v1/apps/&lt;id&gt;/inAppPurchasesV2 — list and pin those as your SKU table."],
    ["2",
     "What does the 1024x1024 icon actually look like at the edges?",
     "PIL: sample 10 random pixels within 30 px of each edge. Assert non-white."],
    ["3",
     "What is the live BTC / FX / whatever rate right now?",
     "curl the provider. Cache. Add two fallback providers. No constants in code."],
    ["4",
     "What audio track does my preview video really have?",
     "ffprobe -v error -show_streams app-preview.mp4 | grep audio — assert stereo or none."],
]
story.append(styled_table(
    checks,
    col_widths=[0.35 * inch, 2.85 * inch, 4.0 * inch],
    num_col=0,
    mono_cols=[2],
))

# ===========================================================================
# SECTION 6 — LITECOIN + DOGECOIN VARIANT
# ===========================================================================
story.append(PageBreak())
story.append(section_pill("6 · LITECOIN + DOGECOIN VARIANT"))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Cloning the architecture for Litecoin and Dogecoin (one app, both coins)",
    h1,
))
story.append(Paragraph(
    "This is a complete sub-playbook for building a brand-new iOS app — "
    "let's call it <b>&lt;MY_APP_NAME&gt;</b> — that uses the same "
    "architecture as Satoshi Cloud Miner, but supports Litecoin (LTC) and "
    "Dogecoin (DOGE) instead of Bitcoin. One app, both coins, with a coin "
    "selector in the wallet UI.",
    body,
))
story.append(callout(
    "This sub-playbook re-uses every constraint from Section 1's Master "
    "Prompt. Send <b>that</b> first (with the LTC+DOGE variant on the next "
    "page substituted for &lt;GOAL&gt;). Then send Prompts L01–L10 from "
    "Section 6 in order.",
    color=AMBER, label="HOW",
))
story.append(Spacer(1, 12))

# --- 6a. What's different from SCM --
story.append(Paragraph("What is different from Satoshi Cloud Miner", h2))
diff_rows = [
    ["Area", "Satoshi Cloud Miner (BTC)", "&lt;MY_APP_NAME&gt; (LTC + DOGE)"],
    ["Coins supported",
     "One — Bitcoin only.",
     "Two — Litecoin AND Dogecoin in a single app, with a coin-picker in the wallet UI."],
    ["Withdrawal method",
     "Lightning Network via Blink Wallet (Bitcoin Layer-2).",
     "On-chain payouts via NowPayments REST API (preferred) — supports both LTC and DOGE with one account. Alternatives noted below."],
    ["Live price feed",
     "1 ticker (BTC/USD) from CoinGecko → Coinbase → Kraken.",
     "2 tickers (LTC/USD + DOGE/USD) using the same 3-provider cascade pattern. Both cached, 5-min refresh."],
    ["AI Trading Agents",
     "6 agents commenting on BTC mining + Lightning conditions.",
     "Same 6 agents, but each daily commentary must reference whichever coin the user is currently viewing (selector-aware)."],
    ["IAP price tiers",
     "10 SKUs: welcome_199 → colossus_19999 + adfree_399 (USD).",
     "Identical USD price ladder — Apple still charges in USD. Plan yields are quoted in LTC AND DOGE per plan, the user picks."],
    ["Apple receipt validation",
     "App Store Server API with In-App Purchase .p8 key.",
     "Identical. No change."],
    ["Branding",
     "Dark theme + neon green.",
     "Dark theme + dual accent: Litecoin silver-blue (#345D9D) + Dogecoin gold (#C2A633). App icon shows both glyphs over a dark background."],
]
story.append(styled_table(
    diff_rows,
    col_widths=[1.3 * inch, 2.7 * inch, 3.2 * inch],
))

# --- 6b. Extra credentials needed --
story.append(Spacer(1, 14))
story.append(Paragraph("Extra credentials YOU need to collect for the LTC + DOGE variant", h2))
extra_creds = [
    ["Item", "Where to get it", "Placeholder you will replace"],
    ["NowPayments API key",
     "nowpayments.io → Dashboard → Settings → API keys",
     "&lt;NOWPAY_API_KEY&gt;"],
    ["NowPayments IPN secret",
     "nowpayments.io → Settings → IPN (for payout webhook verification)",
     "&lt;NOWPAY_IPN_SECRET&gt;"],
    ["Custodial LTC payout address (optional)",
     "Generate in any LTC wallet you control (Litecoin Core, Exodus, etc.)",
     "&lt;LTC_PAYOUT_ADDR&gt;"],
    ["Custodial DOGE payout address (optional)",
     "Generate in any DOGE wallet you control (Dogecoin Core, Exodus, etc.)",
     "&lt;DOGE_PAYOUT_ADDR&gt;"],
    ["New ASC app record",
     "App Store Connect → Apps → New iOS App. Pick a NEW bundle ID — do not reuse Satoshi Cloud Miner's.",
     "&lt;BUNDLE_ID&gt; / &lt;ASC_APP_ID&gt;"],
]
story.append(styled_table(
    extra_creds,
    col_widths=[1.9 * inch, 3.0 * inch, 2.3 * inch],
    mono_cols=[2],
))
story.append(Spacer(1, 10))
story.append(callout(
    "If you do NOT have a NowPayments account, you have two alternatives. "
    "(A) <b>BlockCypher</b> + your own LTC/DOGE node — more control, more "
    "ops overhead. (B) <b>CoinGate</b> — same shape as NowPayments. The "
    "prompts below assume NowPayments; the agent will adapt if you swap.",
    color=AMBER, label="ALTERNATIVE",
))

# --- 6c. The LTC+DOGE Master Prompt --
story.append(PageBreak())
story.append(section_pill("6 · LITECOIN + DOGECOIN VARIANT"))
story.append(Spacer(1, 6))
story.append(Paragraph("The Master Prompt (LTC + DOGE edition)", h2))
story.append(Paragraph(
    "Send this as the very first message in a fresh chat. It re-uses every "
    "non-negotiable constraint from the Section 1 Master Prompt, plus the "
    "two-coin specifics.",
    body,
))
story.append(Spacer(1, 6))

ltc_master = [
    "<b>GOAL</b>",
    "Clone the Satoshi Cloud Miner architecture into a brand-new iOS app",
    "called &lt;MY_APP_NAME&gt; that supports BOTH Litecoin (LTC) and",
    "Dogecoin (DOGE). One app, both coins, single APK/IPA, coin selector",
    "in the Wallet tab. Ship to TestFlight + the App Store end-to-end.",
    "&nbsp;",
    "<b>MY CREDENTIALS (use these, do not ask later)</b>",
    "&nbsp;&nbsp;Apple Team ID:        &lt;TEAM_ID&gt;",
    "&nbsp;&nbsp;ASC API key:          &lt;ASC_KEY_ID&gt; / &lt;ASC_ISSUER_ID&gt; (.p8 attached)",
    "&nbsp;&nbsp;IAP Server API key:   &lt;IAP_KEY_ID&gt; (.p8 attached)",
    "&nbsp;&nbsp;EXPO_TOKEN:           &lt;EXPO_TOKEN&gt;",
    "&nbsp;&nbsp;ASC app record:       bundle=&lt;BUNDLE_ID&gt; app_id=&lt;ASC_APP_ID&gt;",
    "&nbsp;&nbsp;LLM key:              Use the Emergent universal LLM key",
    "&nbsp;&nbsp;NowPayments:          api_key=&lt;NOWPAY_API_KEY&gt;",
    "&nbsp;&nbsp;&nbsp;&nbsp;                  ipn_secret=&lt;NOWPAY_IPN_SECRET&gt;",
    "&nbsp;&nbsp;&nbsp;&nbsp;                  ltc_addr=&lt;LTC_PAYOUT_ADDR&gt;",
    "&nbsp;&nbsp;&nbsp;&nbsp;                  doge_addr=&lt;DOGE_PAYOUT_ADDR&gt;",
    "&nbsp;",
    "<b>COIN-SPECIFIC CONSTRAINTS (in addition to Section 1's 8 rules)</b>",
    "A. Live price feeds: TWO tickers — LTC/USD and DOGE/USD. Use the same",
    "&nbsp;&nbsp;&nbsp;3-provider cascade as SCM (CoinGecko -> Coinbase -> Kraken).",
    "&nbsp;&nbsp;&nbsp;Refresh every 5 min. Expose at /api/system/rates returning",
    "&nbsp;&nbsp;&nbsp;{ltc_usd, doge_usd, source, fetched_at}.",
    "B. Withdrawal: use NowPayments REST API for ALL payouts. No mock",
    "&nbsp;&nbsp;&nbsp;payouts. /api/diag/nowpayments must show one real successful",
    "&nbsp;&nbsp;&nbsp;test-mode quote round-trip before any UI is built.",
    "C. Wallet UI: a top-of-screen segmented control (LTC | DOGE) decides",
    "&nbsp;&nbsp;&nbsp;which balance is shown, which yield is displayed on mining",
    "&nbsp;&nbsp;&nbsp;plan cards, and which address the user enters at withdrawal time.",
    "D. IAP product IDs: identical ladder to SCM — welcome_199, rookie_299,",
    "&nbsp;&nbsp;&nbsp;pro_499, elite_999, ultra_1999, mega_4999, giga_9999, titan_14999,",
    "&nbsp;&nbsp;&nbsp;colossus_19999, adfree_399. Each plan's daily yield is stored",
    "&nbsp;&nbsp;&nbsp;in the DB in USD; the UI converts to LTC or DOGE using the live",
    "&nbsp;&nbsp;&nbsp;rate from constraint A.",
    "E. AI Trading Agents: same 6 agents (Arbiter, Helios, Orbital, Quasar,",
    "&nbsp;&nbsp;&nbsp;Voltage, Sentinel). Daily commentary must reference whichever",
    "&nbsp;&nbsp;&nbsp;coin the user is currently viewing — pass coin=LTC|DOGE into",
    "&nbsp;&nbsp;&nbsp;the LLM prompt at /api/ai/agents?coin=...",
    "F. Branding: dark theme (#0B0E14) with DUAL accent — Litecoin",
    "&nbsp;&nbsp;&nbsp;silver-blue (#345D9D) and Dogecoin gold (#C2A633). App icon",
    "&nbsp;&nbsp;&nbsp;must show BOTH glyphs over the dark background, full-bleed,",
    "&nbsp;&nbsp;&nbsp;pixel-verified per Section 1 constraint #3.",
    "&nbsp;",
    "Everything else (Apple receipt validation, auto_ship watcher, ASC",
    "metadata flow, expo-doctor gates) is identical to Section 1. Apply",
    "all of those constraints. Confirm understanding before writing code.",
]
story.append(prompt_box("L00", "MASTER PROMPT — LITECOIN + DOGECOIN", ltc_master, dark=True))

# --- 6d. The 10 numbered LTC+DOGE prompts -----------------------------------
story.append(PageBreak())
story.append(section_pill("6 · LITECOIN + DOGECOIN VARIANT"))
story.append(Spacer(1, 6))
story.append(Paragraph("The 10 numbered prompts (LTC + DOGE edition)", h2))
story.append(Paragraph(
    "Send these in order, one per message. They mirror Section 3's 10 "
    "prompts but with the multi-coin specifics baked in.",
    body,
))
story.append(Spacer(1, 6))

story.append(prompt_box("L01", "Lock in the LTC + DOGE product spec", [
    "Here is my PRODUCT_SPEC.md for &lt;MY_APP_NAME&gt;. Read every section and",
    "confirm you understand it. Specifically confirm:",
    "&nbsp;&nbsp;- the 5 screens (Dashboard, Plans, Wallet, AI Agents, Profile)",
    "&nbsp;&nbsp;- the LTC|DOGE segmented control on the Wallet tab",
    "&nbsp;&nbsp;- the 10 IAP tiers (identical SKU ladder to SCM)",
    "&nbsp;&nbsp;- NowPayments as the withdrawal vendor with the keys above",
    "&nbsp;&nbsp;- the dual-rate ticker (LTC/USD + DOGE/USD)",
    "&nbsp;",
    "Then push back if Apple has any policy concerns with multi-coin",
    "payouts. Reply with a TL;DR of the spec in your own words.",
], dark=False))

story.append(prompt_box("L02", "Build the backend + Expo skeleton (no UI yet)", [
    "Build the FastAPI backend + Expo Router skeleton.",
    "&nbsp;&nbsp;- Auth: same as SCM (email+password JWT).",
    "&nbsp;&nbsp;- DB models: user.balance_ltc_sats, user.balance_doge_atomic,",
    "&nbsp;&nbsp;&nbsp;&nbsp;user.preferred_coin (LTC|DOGE), Machine, Transaction.",
    "&nbsp;&nbsp;- Stubbed endpoints (200 OK with real schema):",
    "&nbsp;&nbsp;&nbsp;&nbsp;/api/auth/*, /api/dashboard, /api/packages,",
    "&nbsp;&nbsp;&nbsp;&nbsp;/api/wallet?coin=LTC|DOGE, /api/withdraw,",
    "&nbsp;&nbsp;&nbsp;&nbsp;/api/system/rates, /api/ai/agents?coin=...",
    "&nbsp;&nbsp;- expo-router wired, placeholder Text on each tab.",
    "&nbsp;",
    "Then run deep_testing_backend_v2 and paste the report. Do NOT proceed",
    "to UI until backend regression is green.",
], dark=True))

story.append(prompt_box("L03", "Bootstrap App Store Connect (BEFORE any IAP code)", [
    "Using my ASC App Manager key, do this end-to-end via the ASC API:",
    "&nbsp;&nbsp;1. Verify the new app record &lt;ASC_APP_ID&gt; (different from SCM).",
    "&nbsp;&nbsp;2. Create the 10 IAPs from the spec with USD pricing:",
    "&nbsp;&nbsp;&nbsp;&nbsp;welcome_199, rookie_299, pro_499, elite_999, ultra_1999,",
    "&nbsp;&nbsp;&nbsp;&nbsp;mega_4999, giga_9999, titan_14999, colossus_19999, adfree_399.",
    "&nbsp;&nbsp;3. Each consumable needs a 1290x2796 review-screenshot placeholder",
    "&nbsp;&nbsp;&nbsp;&nbsp;(dark BG + the SKU name in neon).",
    "&nbsp;&nbsp;4. Move every IAP to READY_TO_SUBMIT.",
    "&nbsp;",
    "Then print the final list of product IDs that exist in ASC. These are",
    "the source of truth for SHOP_PACKAGES — no extra SKUs in the backend.",
], dark=False))

story.append(PageBreak())
story.append(prompt_box("L04", "Wire the 3 live integrations — prove each is live", [
    "Wire these integrations in order and prove each one is live before",
    "moving to the next:",
    "&nbsp;",
    "&nbsp;&nbsp;1. integrations/rates.py — LTC/USD + DOGE/USD via CoinGecko",
    "&nbsp;&nbsp;&nbsp;&nbsp;-&gt; Coinbase -&gt; Kraken fallback cascade. Add",
    "&nbsp;&nbsp;&nbsp;&nbsp;/api/diag/rates → paste the response. Confirm both rates",
    "&nbsp;&nbsp;&nbsp;&nbsp;are within sanity bounds (LTC 20-1000, DOGE 0.01-2).",
    "&nbsp;&nbsp;2. integrations/nowpayments.py — REST client with key auth.",
    "&nbsp;&nbsp;&nbsp;&nbsp;Add /api/diag/nowpayments → fetch /v1/status and",
    "&nbsp;&nbsp;&nbsp;&nbsp;/v1/min-amount?currency_from=usd&amp;currency_to=ltc. Paste",
    "&nbsp;&nbsp;&nbsp;&nbsp;the response. Then do a sandbox $1 LTC payout test to",
    "&nbsp;&nbsp;&nbsp;&nbsp;&lt;LTC_PAYOUT_ADDR&gt; and paste the payout_id.",
    "&nbsp;&nbsp;3. integrations/apple.py — same as SCM, App Store Server API",
    "&nbsp;&nbsp;&nbsp;&nbsp;receipt validation. Add /api/diag/apple → use Apple's",
    "&nbsp;&nbsp;&nbsp;&nbsp;sandbox shared-secret test transaction.",
    "&nbsp;",
    "No mocks. Each diag endpoint must return a real vendor response.",
], dark=True))

story.append(prompt_box("L05", "Build the UI — coin selector everywhere", [
    "Build every screen with the coin selector baked in.",
    "&nbsp;&nbsp;- Wallet tab: a segmented control at the top (LTC | DOGE).",
    "&nbsp;&nbsp;&nbsp;&nbsp;Selection persists in Zustand + AsyncStorage.",
    "&nbsp;&nbsp;- Plans tab: each card shows the daily yield converted to",
    "&nbsp;&nbsp;&nbsp;&nbsp;both LTC AND DOGE (small line under the USD price).",
    "&nbsp;&nbsp;- AI Agents tab: pass the current coin to /api/ai/agents",
    "&nbsp;&nbsp;&nbsp;&nbsp;so commentary references whichever coin is selected.",
    "&nbsp;&nbsp;- Dashboard tab: hero shows BOTH balances simultaneously.",
    "&nbsp;",
    "Run yarn tsc --noEmit and npx expo-doctor after every screen. Take a",
    "screenshot of each completed tab from the web preview and paste it.",
    "Use real data from the diag endpoints — no Lorem Ipsum, no MOCK_*.",
], dark=False))

story.append(prompt_box("L06", "Marketing assets — DUAL-coin icon + verification", [
    "Generate all App Store marketing assets in ONE batch:",
    "&nbsp;",
    "&nbsp;&nbsp;- App icon (1024x1024, RGB, no alpha): dark background",
    "&nbsp;&nbsp;&nbsp;&nbsp;(#0B0E14) with the LTC glyph (silver-blue #345D9D) AND",
    "&nbsp;&nbsp;&nbsp;&nbsp;the DOGE glyph (gold #C2A633) side by side, full-bleed,",
    "&nbsp;&nbsp;&nbsp;&nbsp;no white border.",
    "&nbsp;&nbsp;- 12 screenshots: 1290x2796 (6.7), 1242x2688 (6.5),",
    "&nbsp;&nbsp;&nbsp;&nbsp;1242x2208 (5.5). At least 4 must show the LTC | DOGE",
    "&nbsp;&nbsp;&nbsp;&nbsp;selector clearly.",
    "&nbsp;&nbsp;- App Preview video: 1080x1920 H.264, 15-30s, STEREO or",
    "&nbsp;&nbsp;&nbsp;&nbsp;SILENT audio only (Apple rejects mono).",
    "&nbsp;",
    "Run the verification pass from Section 3 Prompt 06 — sample icon edges,",
    "PNG magic bytes, ffprobe video. Paste the report. Re-encode if any",
    "check fails.",
], dark=True))

story.append(prompt_box("L07", "Harden app.json for Apple submission", [
    "Update /app/frontend/app.json:",
    "&nbsp;&nbsp;- name: \"&lt;MY_APP_NAME&gt;\"   slug: \"&lt;my-app-slug&gt;\"",
    "&nbsp;&nbsp;- ios.bundleIdentifier: &lt;BUNDLE_ID&gt;",
    "&nbsp;&nbsp;- ios.supportsTablet: false",
    "&nbsp;&nbsp;- ios.config.usesNonExemptEncryption: false",
    "&nbsp;&nbsp;- ios.infoPlist.ITSAppUsesNonExemptEncryption: false",
    "&nbsp;&nbsp;- Remove every permission string unless the spec demands it",
    "&nbsp;&nbsp;- version: 1.0.0    buildNumber: 1",
    "&nbsp;",
    "Then npx expo-doctor → must be N/N pass.",
], dark=False))

story.append(PageBreak())
story.append(prompt_box("L08", "Ship to App Store Connect end-to-end (one shot)", [
    "Run the full ship sequence WITHOUT pausing for input:",
    "&nbsp;&nbsp;1. npx eas build --platform ios --profile production --non-interactive",
    "&nbsp;&nbsp;2. npx eas submit --platform ios --non-interactive",
    "&nbsp;&nbsp;3. Poll ASC builds API until processingState=VALID.",
    "&nbsp;&nbsp;4. Attach the build to App Store Version 1.0 via ASC API.",
    "&nbsp;&nbsp;5. PATCH appStoreVersionLocalizations with description, keywords,",
    "&nbsp;&nbsp;&nbsp;&nbsp;supportUrl, marketingUrl, promotionalText, primaryCategory.",
    "&nbsp;&nbsp;6. Upload all 12 screenshots + App Preview video.",
    "&nbsp;&nbsp;7. Create reviewSubmission, attach the version as a",
    "&nbsp;&nbsp;&nbsp;&nbsp;reviewSubmissionItem (IAPs auto-bundle), PATCH submitted:true.",
    "&nbsp;",
    "Print the final reviewSubmission state. If anything fails, surface",
    "Apple's exact error code — do NOT retry blindly.",
], dark=True))

story.append(prompt_box("L09", "Arm the auto_ship watcher for v1.0.1+", [
    "Create /app/backend/services/auto_ship.py for &lt;MY_APP_NAME&gt;:",
    "&nbsp;&nbsp;- 30-min APScheduler cron inside the FastAPI worker.",
    "&nbsp;&nbsp;- Polls ASC for version 1.0's appStoreState.",
    "&nbsp;&nbsp;- On READY_FOR_SALE or PENDING_APPLE_RELEASE: bump app.json,",
    "&nbsp;&nbsp;&nbsp;&nbsp;run eas build + eas submit, attach build to v1.0.1,",
    "&nbsp;&nbsp;&nbsp;&nbsp;upload fresh screenshots, submit reviewSubmission.",
    "&nbsp;&nbsp;- Idempotent: state in /app/store/.auto_ship_state.json so it",
    "&nbsp;&nbsp;&nbsp;&nbsp;never double-ships.",
    "&nbsp;",
    "Confirm the watcher's first tick logged successfully and paste the",
    "log line. Same pattern as SCM — re-use that module's code.",
], dark=False))

story.append(prompt_box("L10", "Final smoke test + hand-off (LTC + DOGE)", [
    "Run a final regression pass:",
    "&nbsp;&nbsp;- deep_testing_backend_v2 on all critical endpoints.",
    "&nbsp;&nbsp;- Take a web preview screenshot of EACH tab in BOTH coins",
    "&nbsp;&nbsp;&nbsp;&nbsp;(toggle LTC, screenshot; toggle DOGE, screenshot).",
    "&nbsp;&nbsp;- curl GET /api/system/rates and paste JSON proving live LTC",
    "&nbsp;&nbsp;&nbsp;&nbsp;and DOGE rates from CoinGecko/Coinbase/Kraken.",
    "&nbsp;&nbsp;- Show the final ASC state: version, build, IAP states,",
    "&nbsp;&nbsp;&nbsp;&nbsp;reviewSubmission.",
    "&nbsp;",
    "Then write /app/HANDOFF.md documenting:",
    "&nbsp;&nbsp;- every credential (ASC, EXPO, NowPayments, LLM)",
    "&nbsp;&nbsp;- every cron job + its schedule",
    "&nbsp;&nbsp;- how to swap NowPayments for an alternative (BlockCypher",
    "&nbsp;&nbsp;&nbsp;&nbsp;or CoinGate) without touching UI code.",
], dark=True))

# --- Final closing -----------------------------
story.append(Spacer(1, 14))
story.append(Paragraph(
    "<font color='#5AF4AC'><b>— end of playbook v2 —</b></font>",
    ParagraphStyle("end", parent=body, alignment=TA_CENTER, fontSize=11),
))


# ===========================================================================
# Render
# ===========================================================================
doc = BaseDocTemplate(
    str(OUT_PATH),
    pagesize=LETTER,
    leftMargin=MARGIN,
    rightMargin=MARGIN,
    topMargin=0.65 * inch,
    bottomMargin=0.55 * inch,
    title="Foolproof iOS Clone Prompts Playbook v2",
    author="Satoshi Cloud Miner Build Postmortem + LTC/DOGE variant",
    subject="Prompt playbook to ship iOS apps without rebuild loops",
)
frame_cover = Frame(
    MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN,
    leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    id="cover_frame",
)
frame_content = Frame(
    MARGIN, MARGIN + 0.10 * inch,
    PAGE_W - 2 * MARGIN,
    PAGE_H - 2 * MARGIN - 0.20 * inch,
    leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    id="content_frame",
)
doc.addPageTemplates([
    PageTemplate(id="cover", frames=[frame_cover], onPage=_draw_cover_page),
    PageTemplate(id="content", frames=[frame_content], onPage=_draw_content_page),
])
doc.build(story)

print(f"PDF generated: {OUT_PATH}  ({OUT_PATH.stat().st_size:,} bytes)")
