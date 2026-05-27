#!/usr/bin/env python3
"""Generate the Foolproof Prompts Playbook PDF.

Output: /app/store/playbook/Foolproof_iOS_Clone_Prompts_Playbook.pdf

The document is structured so anyone — even someone with zero context — can
literally copy/paste each prompt in order and ship an iOS app to TestFlight
without the rebuild loops we hit on Satoshi Cloud Miner.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
# Brand palette — Satoshi Cloud Miner: dark + neon green
# ---------------------------------------------------------------------------
INK = HexColor("#0B0E14")            # dark background
NEON = HexColor("#5AF4AC")           # neon green
NEON_DIM = HexColor("#1d3a2d")       # deep dim neon for chrome
PAPER = HexColor("#FFFFFF")
SOFT = HexColor("#F4F6F8")
MUTED = HexColor("#5b6470")
ACCENT = HexColor("#0BA86F")
BOX_BG = HexColor("#101720")
BOX_BG_LIGHT = HexColor("#F7FBF9")
BOX_BORDER = HexColor("#1d3a2d")
PILL_BG = HexColor("#143226")
PILL_FG = HexColor("#5AF4AC")
RED = HexColor("#E5484D")
AMBER = HexColor("#E08503")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
styles = getSampleStyleSheet()

title_xl = ParagraphStyle(
    "title_xl",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=34,
    leading=40,
    textColor=PAPER,
    alignment=TA_LEFT,
    spaceAfter=10,
)
title_sub = ParagraphStyle(
    "title_sub",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=14,
    leading=20,
    textColor=NEON,
    spaceAfter=6,
)
h1 = ParagraphStyle(
    "h1",
    parent=styles["Heading1"],
    fontName="Helvetica-Bold",
    fontSize=22,
    leading=28,
    textColor=INK,
    spaceBefore=8,
    spaceAfter=10,
)
h2 = ParagraphStyle(
    "h2",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=15,
    leading=20,
    textColor=ACCENT,
    spaceBefore=18,
    spaceAfter=6,
)
h3 = ParagraphStyle(
    "h3",
    parent=styles["Heading3"],
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    textColor=INK,
    spaceBefore=6,
    spaceAfter=4,
)
body = ParagraphStyle(
    "body",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=10.5,
    leading=15,
    textColor=INK,
    alignment=TA_LEFT,
    spaceAfter=6,
)
muted = ParagraphStyle(
    "muted",
    parent=body,
    textColor=MUTED,
    fontSize=9.5,
    leading=13,
)
li_style = ParagraphStyle(
    "li",
    parent=body,
    leftIndent=14,
    bulletIndent=4,
    spaceAfter=3,
)
prompt_label = ParagraphStyle(
    "prompt_label",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=9,
    leading=11,
    textColor=NEON,
    spaceAfter=0,
    spaceBefore=0,
)
prompt_text = ParagraphStyle(
    "prompt_text",
    parent=styles["Normal"],
    fontName="Courier",
    fontSize=9,
    leading=13,
    textColor=PAPER,
    spaceAfter=0,
    spaceBefore=0,
)
prompt_text_light = ParagraphStyle(
    "prompt_text_light",
    parent=prompt_text,
    textColor=INK,
)
code = ParagraphStyle(
    "code",
    parent=styles["Normal"],
    fontName="Courier-Bold",
    fontSize=9,
    leading=12,
    textColor=ACCENT,
)
table_head = ParagraphStyle(
    "table_head",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=9.5,
    leading=12,
    textColor=PAPER,
    alignment=TA_LEFT,
)
table_cell = ParagraphStyle(
    "table_cell",
    parent=body,
    fontSize=9,
    leading=12,
    spaceAfter=0,
)


# ---------------------------------------------------------------------------
# Page templates
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = LETTER
MARGIN = 0.6 * inch


def _draw_cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=0)

    # Top neon stripe
    canvas.setFillColor(NEON)
    canvas.rect(0, PAGE_H - 8, PAGE_W, 8, fill=True, stroke=0)

    # Brand pill
    canvas.setFillColor(PILL_BG)
    canvas.roundRect(MARGIN, PAGE_H - 1.2 * inch, 2.6 * inch, 0.34 * inch,
                     0.17 * inch, fill=True, stroke=0)
    canvas.setFillColor(NEON)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(MARGIN + 0.18 * inch, PAGE_H - 1.07 * inch,
                      "● SATOSHI CLOUD MINER · POSTMORTEM")

    # Bottom edition footer
    canvas.setFillColor(NEON_DIM)
    canvas.rect(0, 0, PAGE_W, 6, fill=True, stroke=0)
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(NEON)
    canvas.drawString(MARGIN, 0.42 * inch,
                      "Foolproof iOS Clone Prompts · Playbook v1.0 · 2026")
    canvas.drawRightString(PAGE_W - MARGIN, 0.42 * inch,
                           "Authored by your shipping engineer")
    canvas.restoreState()


def _draw_content_page(canvas, doc):
    canvas.saveState()
    # Header strip
    canvas.setFillColor(INK)
    canvas.rect(0, PAGE_H - 0.45 * inch, PAGE_W, 0.45 * inch, fill=True, stroke=0)
    canvas.setFillColor(NEON)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(MARGIN, PAGE_H - 0.30 * inch,
                      "FOOLPROOF iOS CLONE PROMPTS PLAYBOOK")
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.30 * inch,
                           f"Page {doc.page}")
    # Footer accent
    canvas.setFillColor(NEON)
    canvas.rect(0, 0.32 * inch, PAGE_W, 2, fill=True, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(MARGIN, 0.16 * inch,
                      "Copy each prompt verbatim into a fresh Emergent chat to skip the rebuild loops.")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Reusable helpers
# ---------------------------------------------------------------------------
def prompt_box(prompt_no: str, title: str, text_lines: list[str], dark: bool = True):
    """A boxed 'copy this' prompt block."""
    bg = BOX_BG if dark else BOX_BG_LIGHT
    fg_label = NEON if dark else ACCENT
    fg_text = PAPER if dark else INK
    chrome = NEON_DIM if dark else BOX_BORDER

    # Build inner content
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

    inner = [
        [header],
        [Spacer(1, 5)],
        [body_para],
    ]
    t = Table(inner, colWidths=[PAGE_W - 2 * MARGIN - 18])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # Wrap the inner table in a colored outer cell with padding
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


def section_pill(label: str):
    pill = Table([[Paragraph(
        f'<font color="{NEON.hexval()}"><b>{label}</b></font>',
        ParagraphStyle("pill", parent=styles["Normal"], fontName="Helvetica-Bold",
                       fontSize=9, leading=12, textColor=NEON),
    )]], colWidths=[2.0 * inch])
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
        f'<font color="{color.hexval()}"><b>{label}:</b></font> <font color="{INK.hexval()}">{text}</font>',
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


# ---------------------------------------------------------------------------
# Build story
# ---------------------------------------------------------------------------
story = []

# --- COVER PAGE -------------------------------------------------------------
story.append(Spacer(1, 1.6 * inch))
story.append(Paragraph(
    '<font color="#FFFFFF">Foolproof</font><br/>'
    '<font color="#5AF4AC">iOS Clone Prompts</font><br/>'
    '<font color="#FFFFFF">Playbook</font>',
    title_xl,
))
story.append(Spacer(1, 0.2 * inch))
story.append(Paragraph(
    'Copy/paste prompts that ship an Expo + FastAPI iOS app to '
    'TestFlight with zero rebuild loops.',
    ParagraphStyle("cs1", parent=styles["Normal"], fontName="Helvetica",
                   fontSize=14, leading=20, textColor=HexColor("#C5D6CC"))
))
story.append(Spacer(1, 0.5 * inch))

# Big "do this" box on the cover
who = [
    "● You are about to clone an iOS app and ship it to TestFlight.",
    "● You don't want a 20-build, 20-credit loop like the last time.",
    "● You want to read three pages, copy, paste, walk away.",
    "● This playbook is built for exactly that.",
]
cover_pill = Table(
    [[Paragraph(
        f'<font color="#5AF4AC"><b>HOW TO USE</b></font><br/><br/>' +
        '<br/>'.join(f'<font color="#FFFFFF" size="11">{line}</font>' for line in who),
        ParagraphStyle("cv", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=11, leading=18, textColor=PAPER),
    )]],
    colWidths=[PAGE_W - 2 * MARGIN]
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

story.append(Spacer(1, 0.45 * inch))
story.append(Paragraph(
    '<font color="#5AF4AC"><b>BASED ON</b></font>'
    '&nbsp;&nbsp;'
    '<font color="#FFFFFF" size="10">'
    'Builds #11 → #20 of Satoshi Cloud Miner. We made every mistake so you '
    'do not have to. The prompts below would have collapsed that journey '
    'into 1-2 EAS builds.'
    '</font>',
    ParagraphStyle("based", parent=styles["Normal"], fontName="Helvetica",
                   fontSize=10, leading=16, textColor=PAPER)
))

# --- PAGE 2: HOW IT WORKS ---------------------------------------------------
story.append(NextPageTemplate("content"))
story.append(PageBreak())

story.append(section_pill("0 · QUICKSTART"))
story.append(Spacer(1, 6))
story.append(Paragraph("How to use this playbook", h1))
story.append(Paragraph(
    "This document contains <b>10 numbered prompts</b> + <b>1 master prompt</b>. "
    "If you follow them in order, you will skip every painful rebuild loop "
    "we hit on the Satoshi Cloud Miner project (App Store Connect IAP "
    "mismatches, icon white-borders, simulated data, iPad screenshot rejections, "
    "tracking-permission rejections, etc.).",
    body,
))
story.append(Spacer(1, 6))
story.append(Paragraph("The three rules", h2))

rules_data = [
    [Paragraph("<b>1 · Send the Master Prompt first.</b>", body),
     Paragraph("It declares every constraint upfront. Without it, the agent invents assumptions that cost you credits.", body)],
    [Paragraph("<b>2 · Send each follow-up prompt in order.</b>", body),
     Paragraph("Each one assumes the previous step is done. Do not skip ahead — they are sequential.", body)],
    [Paragraph("<b>3 · Replace every <font face='Courier'>&lt;…&gt;</font> placeholder.</b>", body),
     Paragraph("Wherever you see angle brackets, paste your real value. If you can't fill one, ask the agent to source it for you in the same chat.", body)],
]
t = Table(rules_data, colWidths=[1.7 * inch, PAGE_W - 2 * MARGIN - 1.7 * inch])
t.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 8),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ("BACKGROUND", (0, 0), (0, -1), HexColor("#F4F6F8")),
    ("LINEABOVE", (0, 0), (-1, 0), 0.5, BOX_BORDER),
    ("LINEBELOW", (0, -1), (-1, -1), 0.5, BOX_BORDER),
    ("LINEBETWEEN", (0, 0), (-1, -1), 0.3, BOX_BORDER),
]))
story.append(t)
story.append(Spacer(1, 12))

story.append(Paragraph("Before you paste anything — collect these credentials", h2))
creds = [
    ["Item", "Where to get it", "Placeholder you'll replace"],
    ["Apple Team ID", "https://developer.apple.com → Membership", "<TEAM_ID>"],
    ["ASC App Manager API key (.p8)", "App Store Connect → Users & Access → Integrations → App Store Connect API", "<ASC_KEY_ID> / <ASC_ISSUER_ID> / <ASC_P8>"],
    ["In-App Purchase Server API key (.p8)", "App Store Connect → Users & Access → Integrations → In-App Purchase", "<IAP_KEY_ID> / <IAP_P8>"],
    ["Expo personal access token", "https://expo.dev → account settings → access tokens", "<EXPO_TOKEN>"],
    ["Existing ASC app record", "App Store Connect → Apps", "<BUNDLE_ID> / <ASC_APP_ID>"],
    ["LLM key", "Either Emergent universal LLM key (recommended), or your OpenAI/Anthropic/Gemini key", "<LLM_KEY>"],
    ["Payment / wallet keys", "Whatever vendor (Stripe, Blink, BTCPay, Twilio…)", "<VENDOR_KEY>"],
]
ct = Table(creds, colWidths=[1.8 * inch, 3.0 * inch, 2.4 * inch])
ct.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), INK),
    ("TEXTCOLOR", (0, 0), (-1, 0), NEON),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SOFT]),
    ("LINEBELOW", (0, 0), (-1, -1), 0.3, BOX_BORDER),
    ("FONTNAME", (2, 1), (2, -1), "Courier"),
]))
story.append(ct)

# --- PAGE 3: THE MASTER PROMPT ---------------------------------------------
story.append(PageBreak())
story.append(section_pill("1 · THE MASTER PROMPT"))
story.append(Spacer(1, 6))
story.append(Paragraph("Send this one prompt FIRST. Always.", h1))
story.append(Paragraph(
    "This is the single most important message in the whole playbook. "
    "Send it as the very first message in a fresh chat. Every gotcha that "
    "burned credits on the Satoshi Cloud Miner project is preempted by a "
    "constraint in this prompt.",
    body,
))
story.append(callout(
    "Without this prompt, the agent will assume sensible defaults that don't "
    "match Apple's reality (e.g. iPad screenshots required, hardcoded BTC "
    "rate, AI-generated icon with white border).",
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

# --- PAGE 4: GOTCHAS TABLE -------------------------------------------------
story.append(PageBreak())
story.append(section_pill("2 · THE 7 GOTCHAS"))
story.append(Spacer(1, 6))
story.append(Paragraph("Failures we hit — and the one sentence that would have prevented each", h1))
story.append(Paragraph(
    "Add ALL seven lines to the bottom of the Master Prompt if you want belt-and-suspenders coverage.",
    muted,
))
story.append(Spacer(1, 8))

gdata = [
    ["#", "What went wrong on Satoshi Cloud Miner", "Sentence to add to prompt"],
    ["1",
     "starter_099 IAP existed in backend code but Apple never had it. Every TestFlight tap returned 'Purchase failed'.",
     "Before writing IAP code, enumerate App Store Connect IAPs via the v2 API and use those product IDs as the source of truth."],
    ["2",
     "BTC_USD_RATE = 65000.0 hardcoded as a 'simulated rate' — ran in production for weeks.",
     "Any price/FX/rate must come from a live API with a fallback cascade. No magic numbers outside true constants like SATS_PER_BTC."],
    ["3",
     "AI Trading Agents were deterministic random — the UI said 'AI' but the data was random.choice().",
     "Anywhere the UI shows an 'AI'/'live' value, it must be a real LLM/API call with cache + offline fallback. No fake AI."],
    ["4",
     "AI-generated icon was JPEG bytes saved as .png → EAS build failed expo-doctor.",
     "For every generated image, verify the file's magic bytes match the extension. Re-encode through PIL if mismatched."],
    ["5",
     "Icon had a 69-px white border baked in → visible white ring around the app icon on the home screen.",
     "Sample the four edges of any 1024x1024 icon; if pixels >235,>235,>235 are found within 80px of the edge, replace with the brand background."],
    ["6",
     "supportsTablet: true + unused NSUserTrackingUsageDescription caused submission rejection.",
     "Default supportsTablet:false. Never add a permission string unless I explicitly request the feature."],
    ["7",
     "Apple's 'first IAP must ship with first version' + screenshot lockout once WAITING_FOR_REVIEW caught us mid-flow.",
     "Use the reviewSubmissions API (not inAppPurchaseSubmissions). Upload all metadata + screenshots BEFORE attaching version to review submission."],
]
gt = Table(gdata, colWidths=[0.3 * inch, 3.1 * inch, 3.7 * inch])
gt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), INK),
    ("TEXTCOLOR", (0, 0), (-1, 0), NEON),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 9),
    ("FONTSIZE", (0, 1), (-1, -1), 8.6),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 7),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SOFT]),
    ("LINEBELOW", (0, 0), (-1, -1), 0.3, BOX_BORDER),
    ("ALIGN", (0, 0), (0, -1), "CENTER"),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0, 1), (0, -1), ACCENT),
]))
story.append(gt)

# --- PAGE 5+: PHASE-BY-PHASE PROMPTS ---------------------------------------
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

# Prompt 01 — Product spec
story.append(prompt_box(
    "01",
    "Lock in the product spec",
    [
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
    ],
    dark=False,
))

# Prompt 02 — Skeleton
story.append(prompt_box(
    "02",
    "Build the backend + Expo skeleton (no UI yet)",
    [
        "Build the FastAPI backend + Expo Router skeleton.",
        "&nbsp;&nbsp;- Auth: email+password + JWT, with /api/auth/{register,login,me}.",
        "&nbsp;&nbsp;- All data models from the spec, with MongoDB indexes.",
        "&nbsp;&nbsp;- Every API endpoint stubbed with real schema responses (200 OK).",
        "&nbsp;&nbsp;- expo-router wired with app/(tabs)/_layout.tsx, but tabs",
        "&nbsp;&nbsp;&nbsp;&nbsp;render placeholder Text only — no real UI yet.",
        "&nbsp;",
        "Then run the deep_testing_backend_v2 agent and paste the report.",
        "Do NOT proceed to UI until backend regression is green.",
    ],
    dark=True,
))

# Prompt 03 — ASC bootstrap
story.append(prompt_box(
    "03",
    "Bootstrap App Store Connect (BEFORE any IAP code)",
    [
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
    ],
    dark=False,
))

# Prompt 04 — Integrations
story.append(PageBreak())
story.append(prompt_box(
    "04",
    "Wire integrations one at a time, prove each is live",
    [
        "For each integration in my spec, do this loop:",
        "&nbsp;&nbsp;1. Write the integration module (one file in backend/integrations/).",
        "&nbsp;&nbsp;2. Add a /api/diag/&lt;integration_name&gt; endpoint that performs ONE",
        "&nbsp;&nbsp;&nbsp;&nbsp;real round-trip to the vendor (e.g. fetch BTC rate, validate a",
        "&nbsp;&nbsp;&nbsp;&nbsp;test Apple receipt, send a $0.001 Lightning ping).",
        "&nbsp;&nbsp;3. Hit it and paste the JSON response in your reply.",
        "&nbsp;",
        "Do NOT move to the next integration until the diag endpoint returns",
        "a real, non-mocked response. No 'MOCKED' values anywhere.",
    ],
    dark=True,
))

# Prompt 05 — UI build
story.append(prompt_box(
    "05",
    "Build the UI from the spec",
    [
        "Build every screen from PRODUCT_SPEC.md.",
        "&nbsp;&nbsp;- After EVERY screen, run yarn tsc --noEmit and npx expo-doctor.",
        "&nbsp;&nbsp;- Capture a screenshot of the rendered screen from the web preview",
        "&nbsp;&nbsp;&nbsp;&nbsp;(http://localhost:3000) at iPhone 14 Pro dimensions and paste it.",
        "&nbsp;&nbsp;- Use real data from the integrations wired in Prompt 04 — no",
        "&nbsp;&nbsp;&nbsp;&nbsp;placeholder text, no Lorem Ipsum, no MOCK_*.",
        "&nbsp;",
        "If any check fails, stop and fix that screen before moving on.",
        "Do not pile up TODOs.",
    ],
    dark=False,
))

# Prompt 06 — Marketing assets
story.append(prompt_box(
    "06",
    "Generate marketing assets — with pixel-level verification",
    [
        "Generate all App Store marketing assets in ONE batch:",
        "&nbsp;&nbsp;- App icon: 1024x1024 PNG, RGB only (no alpha), brand-colored",
        "&nbsp;&nbsp;&nbsp;&nbsp;full-bleed background, glyph centered, NO white border.",
        "&nbsp;&nbsp;- 12 screenshots: 1290x2796 (iPhone 6.7), 1242x2688 (6.5), 1242x2208 (5.5).",
        "&nbsp;&nbsp;- 1 App Preview video: 1080x1920 H.264, 15-30s, STEREO or SILENT",
        "&nbsp;&nbsp;&nbsp;&nbsp;audio only (no mono — Apple's encoder rejects MOV_RESAVE_STEREO).",
        "&nbsp;",
        "Then run a verification pass that PROVES:",
        "&nbsp;&nbsp;- icon edge pixels (sample 10 corners at &lt;20px from edge) are NOT white",
        "&nbsp;&nbsp;- every PNG starts with bytes 89 50 4E 47",
        "&nbsp;&nbsp;- video probe (ffprobe) shows acodec=aac stereo OR no audio stream",
        "&nbsp;",
        "Paste the pixel-sample report. Re-encode if anything fails.",
    ],
    dark=True,
))

# Prompt 07 — App.json hardening
story.append(prompt_box(
    "07",
    "Harden app.json for Apple submission",
    [
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
    ],
    dark=False,
))

# Prompt 08 — One-shot ship
story.append(PageBreak())
story.append(prompt_box(
    "08",
    "Ship to App Store Connect end-to-end (one shot)",
    [
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
    ],
    dark=True,
))

# Prompt 09 — auto_ship watcher
story.append(prompt_box(
    "09",
    "Arm the auto_ship watcher for v1.0.1+",
    [
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
    ],
    dark=False,
))

# Prompt 10 — Final smoke test
story.append(prompt_box(
    "10",
    "Final smoke test + hand-off",
    [
        "Run a final regression pass:",
        "&nbsp;&nbsp;- deep_testing_backend_v2 (all critical endpoints).",
        "&nbsp;&nbsp;- Take a fresh web preview screenshot of every tab.",
        "&nbsp;&nbsp;- curl GET /api/system/btc_rate (or your live-data endpoint) and",
        "&nbsp;&nbsp;&nbsp;&nbsp;paste the JSON to prove no simulated data is left.",
        "&nbsp;&nbsp;- Show the ASC final state: version, build, IAP states, reviewSubmission.",
        "&nbsp;",
        "Then write a /app/HANDOFF.md that documents:",
        "&nbsp;&nbsp;- every credential the app uses + where it lives",
        "&nbsp;&nbsp;- every cron job + its schedule",
        "&nbsp;&nbsp;- how to invoke the auto_ship watcher manually if needed",
        "I want to be able to hand this to ANY future engineer in one file.",
    ],
    dark=True,
))

# --- PAGE 8: TWO LINES THAT WOULD HAVE SAVED 70% --------------------------
story.append(PageBreak())
story.append(section_pill("4 · IF YOU ONLY READ TWO LINES"))
story.append(Spacer(1, 6))
story.append(Paragraph("The two sentences that would have saved ~70% of the credits on Satoshi Cloud Miner", h1))
story.append(Paragraph(
    "If you can only send two sentences before letting the agent work, these are the two:",
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

story.append(Spacer(1, 22))
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

# --- PAGE 9: TL;DR ---------------------------------------------------------
story.append(PageBreak())
story.append(section_pill("5 · TL;DR — THE ONE LESSON"))
story.append(Spacer(1, 6))
story.append(Paragraph("Verify the platform's reality BEFORE writing the code that depends on it", h1))
story.append(Spacer(1, 6))

tldr = (
    "Both of the most expensive bugs on the Satoshi Cloud Miner project — the "
    "<b>starter_099 'Purchase failed'</b> in TestFlight and the <b>white-border app "
    "icon</b> — came from the same mistake: writing code based on what we "
    "<i>assumed</i> the platform / asset-generator had produced, instead of "
    "programmatically inspecting what was actually there."
)
story.append(Paragraph(tldr, body))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "If every future iOS clone starts with a 5-minute <i>'enumerate the "
    "platform reality'</i> step (list ASC's actual IAPs, sample the icon's "
    "actual edge pixels, probe the actual video's audio track), we ship in "
    "1–2 EAS builds. Not 20.",
    body,
))

story.append(Spacer(1, 22))
story.append(Paragraph("The four reality-checks every iOS clone needs on Day 1", h2))
checks_data = [
    ["#", "Reality check", "How (one line)"],
    ["1", "What product IDs exist in App Store Connect?",
     "GET /v1/apps/<id>/inAppPurchasesV2 — list and pin those as your SKU table."],
    ["2", "What does the 1024x1024 icon actually look like at the edges?",
     "PIL: sample 10 random pixels within 30px of each edge. Assert non-white."],
    ["3", "What's the live BTC/FX/whatever rate right now?",
     "curl the provider. Cache. Add 2 fallback providers. No constants in code."],
    ["4", "What audio track does my preview video really have?",
     "ffprobe -v error -show_streams app-preview.mp4 | grep audio — assert stereo or none."],
]
ck = Table(checks_data, colWidths=[0.3 * inch, 3.0 * inch, 3.8 * inch])
ck.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), INK),
    ("TEXTCOLOR", (0, 0), (-1, 0), NEON),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 9),
    ("FONTSIZE", (0, 1), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ("TOPPADDING", (0, 0), (-1, -1), 7),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SOFT]),
    ("LINEBELOW", (0, 0), (-1, -1), 0.3, BOX_BORDER),
    ("ALIGN", (0, 0), (0, -1), "CENTER"),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0, 1), (0, -1), ACCENT),
    ("FONTNAME", (2, 1), (2, -1), "Courier"),
    ("FONTSIZE", (2, 1), (2, -1), 8.4),
]))
story.append(ck)

story.append(Spacer(1, 22))
story.append(Paragraph("Final word", h2))
story.append(Paragraph(
    "Send the <b>Master Prompt</b> (page 3) + the <b>10 Numbered Prompts</b> "
    "(pages 5–7) in order, and you will be in TestFlight in a handful of "
    "EAS builds, not twenty. Keep this PDF next to every new iOS project — "
    "it pays for itself the first time you use it.",
    body,
))
story.append(Spacer(1, 16))
story.append(Paragraph(
    "<font color='#5AF4AC'><b>— end of playbook —</b></font>",
    ParagraphStyle("end", parent=body, alignment=TA_CENTER, fontSize=11),
))


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
doc = BaseDocTemplate(
    str(OUT_PATH),
    pagesize=LETTER,
    leftMargin=MARGIN,
    rightMargin=MARGIN,
    topMargin=0.65 * inch,
    bottomMargin=0.55 * inch,
    title="Foolproof iOS Clone Prompts Playbook",
    author="Satoshi Cloud Miner Build Postmortem",
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
