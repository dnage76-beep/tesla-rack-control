"""
Generate V6_OPENPILOT_PLAN.pdf -- the printable v6 plan: how the
comma 3X connects to the pre-AP Model S, how to install and test
the openpilot fork, and a commercial cost analysis of selling the
integration.

All diagrams are drawn programmatically in vector form (no
fabricated photographic content), matching docs/build/build_pdf.py.
Facts are sourced from v6/V6_PLAN.md, v6/ANALYSIS_PROMPT1.md and
PROJECT_MEMORY.md; commercial numbers are estimates and are
labelled as such on the page.

Run: python docs/build/build_v6_pdf.py
Output: docs/build/V6_OPENPILOT_PLAN.pdf (lives next to ROADMAP.pdf)
"""

import math
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as canvas_mod
from reportlab.platypus import (
    Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "V6_OPENPILOT_PLAN.pdf")

# Print palette -- identical to docs/build/build_pdf.py
INK = colors.HexColor("#0d1726")
HEAD = colors.HexColor("#0d2538")
DIM = colors.HexColor("#5a6473")
RULE = colors.HexColor("#cad3df")
PANEL = colors.HexColor("#f1f5f9")
PANEL2 = colors.HexColor("#e2e8f0")
ACCENT = colors.HexColor("#1e6fd9")
GREEN = colors.HexColor("#15803d")
YELLOW = colors.HexColor("#b45309")
RED = colors.HexColor("#b91c1c")
WHITE = colors.white


class PageDeco:
    def __init__(self, title="Tesla Rack Control · v6 openpilot plan"):
        self.title = title

    def draw(self, canvas: canvas_mod.Canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(0.75 * inch, 0.55 * inch, 7.75 * inch, 0.55 * inch)
        canvas.setFillColor(DIM)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.75 * inch, 0.40 * inch, self.title)
        canvas.drawRightString(7.75 * inch, 0.40 * inch, f"Page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.line(0.75 * inch, 10.45 * inch, 7.75 * inch, 10.45 * inch)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(HEAD)
        canvas.drawString(0.75 * inch, 10.55 * inch, "TESLA RACK CONTROL · V6")
        canvas.setFillColor(DIM)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(7.75 * inch, 10.55 * inch,
                               datetime.now().strftime("%Y-%m-%d"))
        canvas.restoreState()


def _box(c, x, y, w, h, label, fill=PANEL, stroke=DIM, text=INK,
         bold=False, font_size=9, radius=4):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    c.setFillColor(text)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
    lines = label.split("\n")
    line_h = font_size * 1.15
    total = line_h * len(lines)
    y0 = y + h / 2 + (total - line_h) / 2 - line_h / 3
    for i, ln in enumerate(lines):
        c.drawCentredString(x + w / 2, y0 - i * line_h, ln)


def _arrow(c, x1, y1, x2, y2, color=DIM, width=1.2, dashed=False,
           label=None, label_dy=4):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    if dashed:
        c.setDash(3, 2)
    else:
        c.setDash()
    c.line(x1, y1, x2, y2)
    c.setDash()
    angle = math.atan2(y2 - y1, x2 - x1)
    ah = 5
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - ah * math.cos(angle - math.pi / 7),
             y2 - ah * math.sin(angle - math.pi / 7))
    p.lineTo(x2 - ah * math.cos(angle + math.pi / 7),
             y2 - ah * math.sin(angle + math.pi / 7))
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    if label:
        c.setFillColor(color)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + label_dy, label)


class V6ArchitectureDiagram(Flowable):
    """comma 3X -> OBD-C adapter -> chassis CAN -> car modules, with the
    forbidden simultaneous laptop path shown dashed in red."""

    width = 6.9 * inch
    height = 4.0 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        c.saveState()

        # comma 3X (top-left)
        _box(c, 0.0, 2.9 * inch, 1.5 * inch, 0.7 * inch,
             "comma 3X\nwindshield mount\ncamera + compute",
             fill=PANEL, stroke=ACCENT, bold=True, font_size=8)
        # OBD-C cable
        _arrow(c, 1.5 * inch, 3.25 * inch, 2.3 * inch, 3.25 * inch,
               color=ACCENT, width=1.4, label="OBD-C cable", label_dy=6)
        # Adapter
        _box(c, 2.3 * inch, 2.9 * inch, 1.6 * inch, 0.7 * inch,
             "pre-AP OBD-C adapter\n(xnor preAP kit)\npanda inside",
             fill=PANEL, stroke=ACCENT, bold=True, font_size=8)
        # OBD2 port
        _arrow(c, 3.9 * inch, 3.25 * inch, 4.6 * inch, 3.25 * inch,
               color=ACCENT, width=1.4, label="plugs in")
        _box(c, 4.6 * inch, 2.9 * inch, 1.2 * inch, 0.7 * inch,
             "OBD2 port\npins 1 / 9\n(driver footwell)",
             fill=WHITE, stroke=HEAD, bold=True, font_size=8)

        # Chassis CAN spine
        _box(c, 4.6 * inch, 1.7 * inch, 1.2 * inch, 0.6 * inch,
             "Chassis CAN\n500 kbps", fill=PANEL2, stroke=HEAD,
             bold=True, font_size=9)
        _arrow(c, 5.2 * inch, 2.9 * inch, 5.2 * inch, 2.3 * inch,
               color=HEAD, width=1.4)

        # Modules (right column) -- role text inside the box so nothing
        # collides with the box below
        modules = [
            ("EPAS rack\npatched: takes 0x488", PANEL, ACCENT),
            ("GTW\ngateway", WHITE, DIM),
            ("ESP\nreal speed on 0x155", WHITE, DIM),
            ("DI\ndrive inverter 0x118", WHITE, DIM),
            ("SCCM\nstalks / cruise lever", WHITE, DIM),
        ]
        rx = 5.95 * inch
        for i, (label, fill, stroke) in enumerate(modules):
            y = 3.35 * inch - i * 0.62 * inch
            _box(c, rx, y, 0.95 * inch, 0.5 * inch,
                 label, fill=fill, stroke=stroke, font_size=6.5,
                 bold=True)
            _arrow(c, 5.8 * inch, 2.0 * inch, rx, y + 0.25 * inch,
                   color=DIM, width=0.7)

        # Forbidden laptop path (bottom-left, dashed red)
        _box(c, 0.0, 0.5 * inch, 1.5 * inch, 0.6 * inch,
             "Laptop\ntesla_control.py", fill=WHITE, stroke=RED,
             text=RED, bold=True, font_size=8)
        _box(c, 2.3 * inch, 0.5 * inch, 1.6 * inch, 0.6 * inch,
             "SYS TEC USB-CAN\n(X437 / TDC tap)", fill=WHITE,
             stroke=RED, text=RED, bold=True, font_size=8)
        _arrow(c, 1.5 * inch, 0.8 * inch, 2.3 * inch, 0.8 * inch,
               color=RED, width=1.0, dashed=True)
        _arrow(c, 3.9 * inch, 0.8 * inch, 4.9 * inch, 1.7 * inch,
               color=RED, width=1.0, dashed=True)
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(0.0, 1.35 * inch,
                     "NEVER while the 3X is connected -- two 0x488 "
                     "transmitters = Theory C contention")
        c.restoreState()


class ConnectionDiagram(Flowable):
    """Physical connection detail: mount, cable route, OBD2 pinout,
    fallback X437 tap."""

    width = 6.9 * inch
    height = 3.3 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        c.saveState()

        # Windshield (trapezoid)
        c.setStrokeColor(DIM)
        c.setFillColor(PANEL)
        c.setLineWidth(1)
        p = c.beginPath()
        p.moveTo(0.4 * inch, 1.7 * inch)
        p.lineTo(0.9 * inch, 3.1 * inch)
        p.lineTo(3.3 * inch, 3.1 * inch)
        p.lineTo(3.8 * inch, 1.7 * inch)
        p.close()
        c.drawPath(p, fill=1, stroke=1)
        c.setFillColor(DIM)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(0.5 * inch, 1.55 * inch, "windshield (cabin view)")

        # Device on glass, top-center
        _box(c, 1.75 * inch, 2.55 * inch, 0.7 * inch, 0.4 * inch,
             "3X", fill=WHITE, stroke=ACCENT, bold=True, font_size=9)
        c.setFillColor(INK)
        c.setFont("Helvetica", 7)
        c.drawCentredString(2.1 * inch, 2.42 * inch,
                            "high + centered, camera clear")

        # Cable route: device -> headliner -> A-pillar -> footwell
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.4)
        c.setDash()
        c.line(2.45 * inch, 2.75 * inch, 3.2 * inch, 3.0 * inch)   # to headliner
        c.line(3.2 * inch, 3.0 * inch, 3.7 * inch, 1.75 * inch)    # down A-pillar
        c.line(3.7 * inch, 1.75 * inch, 4.0 * inch, 0.9 * inch)    # to footwell
        c.setFillColor(ACCENT)
        c.setFont("Helvetica", 7)
        c.drawString(2.9 * inch, 3.15 * inch, "tuck into headliner")
        c.drawRightString(3.62 * inch, 2.35 * inch, "down A-pillar trim")

        # OBD2 connector face (right)
        ox, oy = 4.5 * inch, 1.9 * inch
        _box(c, ox, oy, 2.3 * inch, 1.1 * inch, "", fill=WHITE, stroke=HEAD)
        c.setFillColor(HEAD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(ox + 1.15 * inch, oy + 0.88 * inch,
                            "OBD2 port -- pin check FIRST")
        # 16 pins, two rows of 8
        for row in range(2):
            for col in range(8):
                pin = row * 8 + col + 1
                px = ox + 0.22 * inch + col * 0.24 * inch
                py = oy + 0.52 * inch - row * 0.26 * inch
                hot = pin in (1, 9)
                c.setFillColor(ACCENT if hot else PANEL2)
                c.setStrokeColor(HEAD if hot else DIM)
                c.rect(px, py, 0.16 * inch, 0.16 * inch, fill=1, stroke=1)
                c.setFillColor(WHITE if hot else DIM)
                c.setFont("Helvetica-Bold" if hot else "Helvetica", 5.5)
                c.drawCentredString(px + 0.08 * inch, py + 0.05 * inch,
                                    str(pin))
        c.setFillColor(INK)
        c.setFont("Helvetica", 7)
        c.drawString(ox + 0.1 * inch, oy - 0.16 * inch,
                     "pins 1 + 9 = chassis CAN pair (if populated --")
        c.drawString(ox + 0.1 * inch, oy - 0.30 * inch,
                     "build-date dependent; verify with can_sniffer.py)")

        # Footwell box + adapter
        _box(c, 3.6 * inch, 0.45 * inch, 1.3 * inch, 0.45 * inch,
             "OBD-C adapter\nin footwell", fill=PANEL, stroke=ACCENT,
             font_size=7.5, bold=True)
        _arrow(c, 4.9 * inch, 0.7 * inch, 5.6 * inch, 1.9 * inch,
               color=DIM, width=0.9, label=None)
        c.setFillColor(DIM)
        c.setFont("Helvetica", 7)
        c.drawString(5.05 * inch, 1.1 * inch, "plugs into port")

        # Fallback note (bottom-left)
        c.setFillColor(YELLOW)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(0.0, 0.85 * inch, "Fallback if pins 1/9 are empty:")
        c.setFillColor(INK)
        c.setFont("Helvetica", 7.5)
        c.drawString(0.0, 0.70 * inch,
                     "tap chassis CAN at X437/TDC under the center screen")
        c.drawString(0.0, 0.56 * inch,
                     "(same tap the laptop uses) and feed the adapter from")
        c.drawString(0.0, 0.42 * inch,
                     "there -- Tinkla's retrofit harness did exactly this.")
        c.restoreState()


class InstallFlowchart(Flowable):
    """Software decision flow from ANALYSIS_PROMPT1.md."""

    width = 6.9 * inch
    height = 4.5 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        c.saveState()
        W = 2.1 * inch   # box width
        H = 0.55 * inch  # box height
        cx = 0.3 * inch  # left column x

        _box(c, cx, 3.8 * inch, W, H,
             "Ask xnor Discord for the\ncurrent pre-AP 3X build + URL",
             fill=PANEL, stroke=ACCENT, bold=True, font_size=8)
        _arrow(c, cx + W / 2, 3.8 * inch, cx + W / 2, 3.35 * inch,
               color=DIM)
        _box(c, cx, 2.8 * inch, W, H,
             "URL confirmed?\n(diamond decision)",
             fill=WHITE, stroke=HEAD, bold=True, font_size=8)

        # YES branch (down)
        _arrow(c, cx + W / 2, 2.8 * inch, cx + W / 2, 2.35 * inch,
               color=GREEN, label="yes", label_dy=2)
        _box(c, cx, 1.8 * inch, W, H,
             "Factory-reset 3X, enter URL\nat Custom Software screen",
             fill=PANEL, stroke=GREEN, font_size=8)
        _arrow(c, cx + W / 2, 1.8 * inch, cx + W / 2, 1.35 * inch,
               color=GREEN)
        _box(c, cx, 0.8 * inch, W, H,
             "Fork flashes its own AGNOS,\nboots -- proceed to test plan",
             fill=PANEL, stroke=GREEN, bold=True, font_size=8)

        # NO branch (right): BogGyver spike
        bx = 3.1 * inch
        _arrow(c, cx + W, 3.07 * inch, bx, 3.07 * inch,
               color=YELLOW, label="not yet", label_dy=5)
        _box(c, bx, 2.8 * inch, W, H,
             "Try installer.comma.ai/\nBogGyver/tesla_unity_releaseC3",
             fill=WHITE, stroke=YELLOW, font_size=8)
        _arrow(c, bx + W / 2, 2.8 * inch, bx + W / 2, 2.35 * inch,
               color=DIM)
        _box(c, bx, 1.8 * inch, W, H,
             "Boots + sees CAN +\nfingerprints the car?",
             fill=WHITE, stroke=HEAD, bold=True, font_size=8)
        _arrow(c, bx + W / 2, 1.8 * inch, bx + W / 2, 1.35 * inch,
               color=GREEN, label="yes", label_dy=2)
        _box(c, bx, 0.8 * inch, W, H,
             "Interim baseline (frozen 0.9.6)\n-- still migrate to xnor later",
             fill=PANEL, stroke=GREEN, font_size=8)

        # Bootloop branch (far right)
        fx = 5.5 * inch
        _arrow(c, bx + W, 2.07 * inch, fx, 2.07 * inch,
               color=RED, label="no", label_dy=5)
        _box(c, fx - 0.1 * inch, 1.8 * inch, 1.45 * inch, H,
             "flash.comma.ai\nreflash, back to stock",
             fill=WHITE, stroke=RED, font_size=7.5)
        c.setFillColor(DIM)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(fx - 0.1 * inch, 1.55 * inch, "question answered, $0 lost")

        # Never box
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(0.3 * inch, 0.35 * inch,
                     "Never: installer.comma.ai/commaai/agnos8 (branch does "
                     "not exist) · never re-flash the EPAS patch (already done)")
        c.restoreState()


class MarketFunnel(Flowable):
    """Commercial section: market funnel bars."""

    width = 6.9 * inch
    height = 2.6 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        c.saveState()
        rows = [
            ("pre-AP Model S built (2012 - Oct 2014, worldwide)",
             "~55,000 (est.)", 6.0, PANEL2, DIM),
            ("still on the road, 12-14 years on (est. 65-75%)",
             "~38,000", 4.4, PANEL2, DIM),
            ("owners who would modify steering firmware on their car",
             "~1-2% -> ~400-800", 1.6, PANEL, YELLOW),
            ("reachable + willing to pay a US installer (est.)",
             "~40-120 lifetime", 0.55, WHITE, RED),
        ]
        y = 2.1 * inch
        for label, value, w_in, fill, stroke in rows:
            c.setFillColor(fill)
            c.setStrokeColor(stroke)
            c.setLineWidth(0.8)
            c.rect(0.0, y, w_in * inch, 0.38 * inch, fill=1, stroke=1)
            c.setFillColor(INK)
            c.setFont("Helvetica", 8)
            c.drawString(0.08 * inch, y + 0.23 * inch, label)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(0.08 * inch, y + 0.08 * inch, value)
            y -= 0.52 * inch
        c.setFillColor(DIM)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(0.0, 0.1 * inch,
                     "All figures estimates; fleet size from public Model S "
                     "delivery numbers, conversion rates are judgment calls "
                     "labelled as such.")
        c.restoreState()


def build():
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5,
                          leading=13.5, textColor=INK, alignment=TA_LEFT,
                          spaceAfter=6)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16,
                        leading=20, textColor=HEAD, spaceBefore=10,
                        spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12,
                        leading=15, textColor=HEAD, spaceBefore=10,
                        spaceAfter=6)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11,
                           textColor=DIM)
    warn = ParagraphStyle("warn", parent=body, textColor=RED,
                          fontName="Helvetica-Bold")

    cell_style = ParagraphStyle("cell", parent=styles["BodyText"],
                                fontSize=8, leading=10, textColor=INK,
                                spaceAfter=0, spaceBefore=0)
    cell_head = ParagraphStyle("cell_head", parent=cell_style,
                               fontName="Helvetica-Bold", textColor=HEAD)

    def table(data, widths, header=True, fs=8.5):
        wrapped = []
        for r, row in enumerate(data):
            st = cell_head if (header and r == 0) else cell_style
            wrapped.append([cell if isinstance(cell, Paragraph)
                            else Paragraph(str(cell).replace("\n", "<br/>"), st)
                            for cell in row])
        data = wrapped
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        style = [
            ("FONT", (0, 0), (-1, -1), "Helvetica", fs),
            ("TEXTCOLOR", (0, 0), (-1, -1), INK),
            ("GRID", (0, 0), (-1, -1), 0.5, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL]),
        ]
        if header:
            style += [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", fs),
                ("BACKGROUND", (0, 0), (-1, 0), PANEL2),
                ("TEXTCOLOR", (0, 0), (-1, 0), HEAD),
            ]
        t.setStyle(TableStyle(style))
        return t

    story = []

    # ---- Title page content ----
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("v6 — openpilot on the car", ParagraphStyle(
        "title", parent=h1, fontSize=24, leading=30)))
    story.append(Paragraph(
        "Connection plan, test plan, and commercial cost analysis for "
        "running a comma 3X with a pre-AP openpilot fork on the 2013 "
        "Tesla Model S.", body))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "v6 is a different family from v4/v5: the rack-control programs "
        "make the laptop the brain; v6 makes the comma 3X the brain and "
        "retires our code to a bench tool. The two are mutually exclusive "
        "on the bus — the device and tesla_control.py both transmit "
        "0x488 DAS_steeringControl, and two transmitters on one "
        "arbitration ID is exactly the Theory C contention confirmed in "
        "May 2026 (PROJECT_MEMORY.md §8).", body))
    story.append(Paragraph(
        "Companion documents: v6/V6_PLAN.md (research, with citations), "
        "v6/INSTALL_GUIDE.md (step-by-step), v6/ANALYSIS_PROMPT1.md "
        "(option comparison answering Charlie's prompt1.md).", small))

    # ---- 1. Architecture ----
    story.append(Paragraph("1. System architecture", h1))
    story.append(Paragraph(
        "The comma 3X mounts on the windshield and reaches chassis CAN "
        "through the pre-AP OBD-C adapter in the OBD2 port. The EPAS "
        "rack is already flashed with the gregjhogan patch (done by "
        "Jordan via the BogGyver UI), so it accepts 0x488 steering "
        "commands directly — the same mechanism the v4 laptop control "
        "uses today.", body))
    story.append(V6ArchitectureDiagram())
    story.append(Paragraph(
        "One transmitter at a time: before plugging in the 3X harness, "
        "physically disconnect the SYS TEC adapter. The v4.2 bus "
        "diagnostic panel's 0x488 RX-rate readout is the detection tool "
        "if there is ever any doubt.", warn))

    story.append(PageBreak())

    # ---- 2. Physical connection ----
    story.append(Paragraph("2. Physical connection", h1))
    story.append(Paragraph(
        "First physical task: open the OBD2 port cover in the driver "
        "footwell and check whether pins 1 and 9 are populated — on this "
        "platform that pair carries chassis CAN, but population depends "
        "on build date (our car is a post-May-31 2013 build, which is "
        "why this is a check and not an assumption). Photograph the "
        "port for the log either way.", body))
    story.append(ConnectionDiagram())
    story.append(Paragraph(
        "Verification before first power-on: with the adapter wired but "
        "the 3X NOT yet connected, put the laptop sniffer "
        "(can_sniffer.py) on the same pair and confirm real chassis "
        "traffic (0x370 EPAS, 0x155 ESP, 0x118 DI at their known "
        "rates). That proves the tap is chassis CAN and not body/diag "
        "CAN before any new device transmits on it.", body))
    story.append(Paragraph("Parts list", h2))
    story.append(table(
        [["Item", "Source", "Price", "Status"],
         ["comma 3X", "comma.ai", "$1,250 list (seen ~$1,050 on sale)",
          "in hand"],
         ["pre-AP OBD-C harness kit", "xnor.shop (ships from Germany)",
          "unpublished — confirm at order time (est. $100–250)",
          "to order after pin check"],
         ["OBD-C extension cable ~2 m", "included in xnor kit", "—", "—"],
         ["EPAS firmware patch", "gregjhogan/tesla-pre-ap-epas-patch",
          "$0", "ALREADY FLASHED — do not re-flash"],
         ["comma pedal interceptor (optional, later)",
          "comma / DIY", "~$300 (est.)",
          "extends ACC below ~18 mph; shared goal with v5 plan"]],
        [1.7 * inch, 1.9 * inch, 2.1 * inch, 1.2 * inch]))

    story.append(PageBreak())

    # ---- 3. Software install ----
    story.append(Paragraph("3. Software install", h1))
    story.append(Paragraph(
        "Decision flow from ANALYSIS_PROMPT1.md. The recommended target "
        "is the actively maintained xnor/Loetkolben build (the commaai "
        "community wiki's documented path for pre-AP Model S on a comma "
        "3X); the frozen BogGyver branch is a zero-cost spike worth one "
        "afternoon, never two days. No manual AGNOS step exists "
        "anywhere in this flow — every fork pins its AGNOS version in "
        "launch_env.sh and flashes it automatically on first boot "
        "(BogGyver C3 pins 9.1; xnor-c3 pins 12.8). The device "
        "currently runs stock AGNOS 18.4, which is fine: the installer "
        "handles the transition. The BogGyver installer URL is built "
        "from github.com/BogGyver/openpilot, branch "
        "tesla_unity_releaseC3 — that branch is the source of the "
        "AGNOS pin and the place to read the code before installing.",
        body))
    story.append(InstallFlowchart())

    # ---- 4. Test plan ----
    story.append(PageBreak())
    story.append(Paragraph("4. Test plan", h1))
    story.append(Paragraph(
        "Phases are gated: do not start a phase until the previous "
        "phase's acceptance criteria are met and logged. Save artifacts "
        "to field_testing/sessions/ with the same note discipline as "
        "the v4 sessions.", body))
    story.append(table(
        [["Phase", "Where", "What", "Acceptance criteria"],
         ["T0\npin check", "car, parked",
          "Inspect OBD2 pins 1/9; sniff the pair with can_sniffer.py",
          "Photo of port; capture showing 0x370/0x155/0x118 at known "
          "rates (or decision to use X437 fallback)"],
         ["T1\nbench boot", "bench, no car",
          "Factory reset; install fork via custom-software URL",
          "Fork boots reliably; Tesla preAP settings screen present; "
          "EPAS screen reports patched state WITHOUT prompting a "
          "re-flash"],
         ["T2\npassive drive", "car, human driving",
          "Harness in, laptop disconnected; drive normally, never "
          "engage",
          "Device fingerprints / accepts manual pre-AP selection; "
          "speed + steering angle on screen match reality; full route "
          "recorded; no DTCs, no EAC complaints, no flicker"],
         ["T3\nfirst engage", "open road, > 18 mph",
          "Engage via cruise stalk, hands on wheel; test override and "
          "brake disengage",
          "Smooth lateral hold; instant disengage on steering override "
          "AND on brake; repeatable across 3+ engagements; clean log"],
         ["T4\nhardening", "daily driving",
          "Longer routes, tuning, decide on pedal interceptor",
          "No safety events across multiple drives; go/no-go on "
          "low-speed ACC hardware"]],
        [0.75 * inch, 1.1 * inch, 2.3 * inch, 2.75 * inch]))
    story.append(Paragraph(
        "Standing rules: EAC flicker or cluster complaints during T2 = "
        "pull the harness and capture a log before anything else (bus-"
        "contention smell). The fork asking to flash EPAS = stop, "
        "investigate detection; the rack is already patched and working. "
        "tesla_control.py stays retired from the car for as long as the "
        "3X is wired in.", warn))
    story.append(Paragraph(
        "Known limits to not chase as bugs: no ACC below ~18 mph "
        "without a pedal interceptor (no radar, no CAN throttle on "
        "pre-AP); no stop-and-go or hard braking authority (vacuum "
        "brakes, no iBooster); no standstill steering (rack speed gate "
        "applies to openpilot exactly as it does to our laptop).", small))

    # ---- 5. Commercial analysis ----
    story.append(PageBreak())
    story.append(Paragraph("5. Could we sell this? Cost analysis", h1))
    story.append(Paragraph(
        "Question asked: if the v6 integration works, is there a "
        "business in selling it — and how profitable would it be given "
        "the integration cost? Short answer: as a product business, no; "
        "as a small local install service, marginal at best. The "
        "numbers below show why. Everything marked (est.) is an "
        "estimate, not a verified figure.", body))

    story.append(Paragraph("5.1 The market", h2))
    story.append(MarketFunnel())
    story.append(Paragraph(
        "The addressable market is small and shrinking: the newest "
        "eligible car was built in October 2014, every sale requires an "
        "owner willing to have their steering firmware modified, and "
        "the serious DIY slice of that population can already buy every "
        "piece themselves (comma sells the 3X, xnor sells the harness "
        "and maintains the software). Our sellable value-add is only "
        "the integration labor, the EPAS patch service, and a tested "
        "configuration.", body))

    story.append(Paragraph("5.2 Integration cost per car (turnkey install)", h2))
    story.append(table(
        [["Cost item", "Low", "High", "Notes"],
         ["comma 3X (at our cost)", "$1,050", "$1,250",
          "no dealer/volume pricing program exists (est.)"],
         ["xnor pre-AP harness kit + shipping", "$130", "$300",
          "price unpublished; DE shipping + duties (est.)"],
         ["Install labor: mount, route, pin check, possible X437 "
          "retrofit tap", "3 h", "8 h",
          "at $100/h shop rate: $300–$800"],
         ["EPAS patch flash (skip if already patched)", "1 h", "3 h",
          "includes backup of original firmware; carries brick risk"],
         ["Road validation (T2 + T3 equivalent)", "2 h", "4 h",
          "$200–$400; non-negotiable before handover"],
         ["Support reserve per car (first year)", "$150", "$400",
          "fork updates break things; customers call us, not xnor "
          "(est.)"],
         ["Total cost per delivered car", "~$1,930", "~$3,450",
          "before insurance/liability (see 5.4)"]],
        [2.5 * inch, 0.8 * inch, 0.8 * inch, 2.8 * inch]))

    story.append(Paragraph("5.3 Pricing scenarios and margin", h2))
    story.append(table(
        [["Scenario", "Price", "Margin/car", "Annual volume (est.)",
          "Annual profit (est.)"],
         ["A. Turnkey install\n(device + harness + install + validation)",
          "$2,950", "$400–$1,000\n(mid ~$700)", "5–15 cars",
          "$3,500–$10,500"],
         ["B. Install-only service\n(customer brings 3X + kit)",
          "$650", "$250–$400", "5–20 cars", "$1,500–$8,000"],
         ["C. Documentation / kit-less\n(publish guides, donations)",
          "$0", "$0", "—", "$0 — but also zero liability"]],
        [2.1 * inch, 0.7 * inch, 1.1 * inch, 1.3 * inch, 1.3 * inch]))
    story.append(Paragraph(
        "Break-even reality check on Scenario A: at a mid-case ~$700 "
        "margin, ten installs a year clears about $7,000 — before "
        "insurance, before a single warranty callback, before any "
        "marketing. One liability event, one bricked EPAS requiring a "
        "used rack (~$400–$900 + labor), or one customer whose fork "
        "update breaks at 2 a.m. erases weeks of margin. Volume cannot "
        "rescue it: the funnel above caps lifetime demand in the tens "
        "to low hundreds of units, total.", body))

    story.append(Paragraph("5.4 The disqualifying risks", h2))
    story.append(table(
        [["Risk", "Severity", "Why"],
         ["Liability", "disqualifying",
          "Selling modified steering firmware + an aftermarket "
          "self-steering install on customer cars. comma ships as L2 "
          "driver assistance under its own terms; a small installer "
          "has no such shield. One incident outweighs all revenue."],
         ["Platform dependence", "high",
          "The product is really comma's device + xnor's software. "
          "Either party changing course (3X EOL, fork abandoned -- "
          "which already happened once with BogGyver) strands "
          "customers we are on the hook for."],
         ["Shrinking market", "high",
          "Fleet ages out; every year the funnel narrows. No new "
          "supply of pre-AP cars, ever."],
         ["EPAS patch brick risk", "medium",
          "Flashing customer racks at scale means eventually bricking "
          "one. Backup/restore mitigates but does not eliminate."]],
        [1.3 * inch, 1.0 * inch, 4.6 * inch]))

    story.append(Paragraph("5.5 Verdict", h2))
    story.append(Paragraph(
        "Not a business. The integration cost per car (~$1,900–$3,400) "
        "against a defensible price ceiling around $3,000 leaves a "
        "margin that is thin in the best case and negative after one "
        "bad event, on a market measured in dozens of lifetime "
        "customers — all of it carrying steering-system liability we "
        "cannot insure away at this scale. If any commercial path is "
        "worth keeping open, it is Scenario C: publish the v6 "
        "documentation, build reputation in the xnor/openpilot "
        "community, and treat paid one-off installs for nearby owners "
        "as occasional shop work (Scenario B pricing) rather than a "
        "product line. The honest framing: v6 is worth doing for our "
        "car and for the project's openpilot end-goal — not for "
        "revenue.", body))

    # ---- 6. References ----
    story.append(PageBreak())
    story.append(Paragraph("6. Links — who solved this, and our paper trail", h1))
    story.append(Paragraph(
        "Our issue, in one line: we tried to install the legacy "
        "BogGyver/Tinkla software by downgrading AGNOS (using the "
        "nonexistent installer.comma.ai/commaai/agnos8 URL, based on a "
        "miscited GitHub issue) — when the actual blocker was that the "
        "legacy project is abandoned and was never the current path. "
        "The people who solved pre-AP Model S on a comma 3X are the "
        "xnor / Loetkolben project, which rebuilt the hardware and "
        "harnesses from scratch after BogGyver left and maintains the "
        "software today. Their links come first.", body))

    def linkrow(label, url):
        return [Paragraph(label, cell_style),
                Paragraph(f'<link href="{url}" color="#1e6fd9">{url}'
                          f'</link>', cell_style)]

    story.append(Paragraph("The solution (xnor / Loetkolben)", h2))
    story.append(table(
        [["What", "Link"],
         linkrow("Maintained openpilot fork (the successor; branches "
                 "active 2026)", "https://github.com/xnor-tech/openpilot"),
         linkrow("Wiki — install docs incl. Tesla preAP",
                 "https://wiki.xnor.shop/"),
         linkrow("Shop — Model S (preAP) OBD-C harness kit for comma 3X",
                 "https://xnor.shop/products/model-s-preap-kit"),
         linkrow("Discord — confirm the current pre-AP 3X build + "
                 "installer URL here FIRST", "https://discord.xnor.shop/"),
         linkrow("Maintainer (Loetkolben)", "https://loetkolben.org/")],
        [2.4 * inch, 4.5 * inch]))

    story.append(Paragraph("The legacy project (BogGyver / Tinkla — frozen Jan 2024)", h2))
    story.append(table(
        [["What", "Link"],
         linkrow("Fork source for the fallback spike (branch "
                 "tesla_unity_releaseC3; AGNOS 9.1 pin in launch_env.sh)",
                 "https://github.com/BogGyver/openpilot/tree/"
                 "tesla_unity_releaseC3"),
         linkrow("Panda safety code (CRC + 0x488 behavior we verified "
                 "against)", "https://github.com/BogGyver/panda"),
         linkrow("Tinkla site (2022-era docs; harnesses no longer sold)",
                 "https://tinkla.us")],
        [2.4 * inch, 4.5 * inch]))

    story.append(Paragraph("Context and prerequisites", h2))
    story.append(table(
        [["What", "Link"],
         linkrow("commaai community wiki, Tesla page (updated May 2026; "
                 "lists pre-AP S on comma 3X via xnor)",
                 "https://github.com/commaai/openpilot/wiki/tesla"),
         linkrow("EPAS firmware patch (already flashed on our rack — do "
                 "not re-flash)",
                 "https://github.com/gregjhogan/tesla-pre-ap-epas-patch"),
         linkrow("comma 3X hardware", "https://comma.ai/shop/comma-3x"),
         linkrow("Device recovery if an install attempt strands the 3X",
                 "https://flash.comma.ai"),
         linkrow("This project (branch with all v6 docs)",
                 "https://github.com/dnage76-beep/tesla-rack-control")],
        [2.4 * inch, 4.5 * inch]))
    story.append(Paragraph(
        "Markdown companions in the repo: v6/V6_PLAN.md, "
        "v6/INSTALL_GUIDE.md, v6/ANALYSIS_PROMPT1.md (all carry the "
        "same links with verification dates).", small))

    doc = SimpleDocTemplate(
        OUT_PATH, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        title="Tesla Rack Control — v6 openpilot plan",
        author="tesla-rack-control project")
    deco = PageDeco()
    doc.build(story, onFirstPage=deco.draw, onLaterPages=deco.draw)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
