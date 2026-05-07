"""
Generate ROADMAP.pdf -- a professional write-up of the project plan
with verified wiring diagrams, flowcharts, and field-test imagery.

All diagrams are drawn programmatically in vector form (no
fabricated photographic content). Numbers and labels are sourced
from PROJECT_MEMORY.md, opendbc tesla_can.dbc, and the May 2026
session logs.

Run: python docs/build/build_pdf.py
Output: docs/build/ROADMAP.pdf
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image,
    Table, TableStyle, Flowable, KeepTogether,
)
from reportlab.pdfgen import canvas as canvas_mod

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_PATH = os.path.join(HERE, "ROADMAP.pdf")

# ============================================================================
# Print-friendly palette (derived from the GitHub-dark used in the GUI but
# inverted for paper)
# ============================================================================
INK     = colors.HexColor("#0d1726")   # near-black, for body text
HEAD    = colors.HexColor("#0d2538")   # navy, for headings
DIM     = colors.HexColor("#5a6473")   # muted text
RULE    = colors.HexColor("#cad3df")   # subtle dividers
PANEL   = colors.HexColor("#f1f5f9")   # light gray for callout boxes
PANEL2  = colors.HexColor("#e2e8f0")
ACCENT  = colors.HexColor("#1e6fd9")   # accessible blue
GREEN   = colors.HexColor("#15803d")
YELLOW  = colors.HexColor("#b45309")
ORANGE  = colors.HexColor("#c2410c")
RED     = colors.HexColor("#b91c1c")
WHITE   = colors.white


# ============================================================================
# Page template (header + footer)
# ============================================================================

class PageDeco:
    """Header / footer / page number drawn on every page."""

    def __init__(self, title="Tesla Rack Control · Roadmap"):
        self.title = title

    def draw(self, canvas: canvas_mod.Canvas, doc):
        canvas.saveState()
        # Footer rule + page number
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(0.75 * inch, 0.55 * inch,
                    7.75 * inch, 0.55 * inch)
        canvas.setFillColor(DIM)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.75 * inch, 0.40 * inch, self.title)
        canvas.drawRightString(7.75 * inch, 0.40 * inch,
                               f"Page {doc.page}")
        # Header rule
        canvas.setStrokeColor(RULE)
        canvas.line(0.75 * inch, 10.45 * inch,
                    7.75 * inch, 10.45 * inch)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(HEAD)
        canvas.drawString(0.75 * inch, 10.55 * inch,
                          "TESLA RACK CONTROL")
        canvas.setFillColor(DIM)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(7.75 * inch, 10.55 * inch,
                               datetime.now().strftime("%Y-%m-%d"))
        canvas.restoreState()


# ============================================================================
# Vector flowables: block diagram, flowchart, wiring diagram
# ============================================================================

def _box(c, x, y, w, h, label, fill=PANEL, stroke=DIM, text=INK,
         bold=False, font_size=9, radius=4):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    c.setFillColor(text)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
    # Multi-line center
    lines = label.split("\n")
    line_h = font_size * 1.15
    total = line_h * len(lines)
    y0 = y + h / 2 + (total - line_h) / 2 - line_h / 3
    for i, ln in enumerate(lines):
        c.drawCentredString(x + w / 2, y0 - i * line_h, ln)


def _arrow(c, x1, y1, x2, y2, color=DIM, width=1.2, dashed=False, label=None):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    if dashed:
        c.setDash(3, 2)
    else:
        c.setDash()
    c.line(x1, y1, x2, y2)
    c.setDash()
    # Arrowhead
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    ah = 5
    c.setFillColor(color)
    c.beginPath()
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
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        c.drawCentredString(mx, my + 4, label)


class SystemBlockDiagram(Flowable):
    """End-to-end signal flow: input source -> bridge -> CAN bus -> rack."""

    width = 6.8 * inch
    height = 3.6 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        # Flowable.__init__ resets self.width/height to 0; pull from class
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        cls = type(self)
        H = cls.height
        c.saveState()

        # Sources (left)
        sx = 0.0
        _box(c, sx, 1.7 * inch, 1.3 * inch, 0.45 * inch,
             "DX8 transmitter\n(Phase 4+)", fill=WHITE, stroke=DIM,
             font_size=8, bold=True)
        _box(c, sx, 1.0 * inch, 1.3 * inch, 0.45 * inch,
             "Arduino Nano\n(SBUS → CAN)", fill=WHITE, stroke=DIM,
             font_size=8, bold=True)
        _box(c, sx, 0.3 * inch, 1.3 * inch, 0.45 * inch,
             "Laptop\ntesla_control.py", fill=PANEL, stroke=ACCENT,
             font_size=8, bold=True)

        # Bridges (mid-left)
        bx = 1.6 * inch
        _box(c, bx, 1.7 * inch, 1.4 * inch, 0.45 * inch,
             "RC controller hardware\n(planned)", fill=WHITE,
             stroke=DIM, font_size=8)
        _box(c, bx, 0.3 * inch, 1.4 * inch, 0.45 * inch,
             "SYS TEC USB-CAN\n(production today)", fill=PANEL,
             stroke=ACCENT, font_size=8)

        # Aggregator (mid)
        mx = 3.3 * inch
        _box(c, mx, 1.0 * inch, 1.0 * inch, 0.6 * inch,
             "Chassis CAN\n500 kbps\nX437 / TDC tap",
             fill=PANEL2, stroke=HEAD, bold=True, font_size=8.5)

        # Bus consumers (right) -- one column
        rx = 4.7 * inch
        modules = [
            ("EPAS rack", "patched, accepts 0x488", PANEL, ACCENT),
            ("GTW", "real, sends 0x101 @ 10 Hz", WHITE, DIM),
            ("ESP", "real, sends 0x155 @ 50 Hz", WHITE, DIM),
            ("DI", "real, sends 0x118 @ 100 Hz", WHITE, DIM),
            ("SCCM (stalk)", "real, sends 0x6D @ 100 Hz", WHITE, DIM),
        ]
        for i, (name, role, fill, stroke) in enumerate(modules):
            y = 2.55 * inch - i * 0.50 * inch
            _box(c, rx, y, 1.95 * inch, 0.42 * inch,
                 f"{name}\n{role}", fill=fill, stroke=stroke,
                 font_size=7.5, bold=True)

        # Arrows
        _arrow(c, sx + 1.3 * inch, 1.92 * inch,
               bx, 1.92 * inch, color=DIM, width=1)
        _arrow(c, sx + 1.3 * inch, 1.22 * inch,
               bx, 1.92 * inch, color=DIM, width=1)
        _arrow(c, sx + 1.3 * inch, 0.52 * inch,
               bx, 0.52 * inch, color=ACCENT, width=1.4)
        _arrow(c, bx + 1.4 * inch, 1.92 * inch,
               mx + 0.5 * inch, 1.6 * inch, color=DIM, width=1)
        _arrow(c, bx + 1.4 * inch, 0.52 * inch,
               mx + 0.5 * inch, 1.0 * inch, color=ACCENT, width=1.4)
        # Bus to modules
        for i in range(5):
            y = 2.55 * inch - i * 0.50 * inch + 0.21 * inch
            _arrow(c, mx + 1.0 * inch, 1.3 * inch,
                   rx, y, color=DIM, width=0.7)
        c.restoreState()


class WiringDiagram(Flowable):
    """SYS TEC USB-CAN to X437/TDC chassis CAN tap."""

    width = 6.8 * inch
    height = 2.7 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        # Flowable.__init__ resets self.width/height to 0; pull from class
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        cls = type(self)
        H = cls.height
        c.saveState()

        # Laptop
        _box(c, 0.0, 1.7 * inch, 1.0 * inch, 0.6 * inch,
             "Laptop\nWindows", fill=PANEL, stroke=ACCENT,
             bold=True, font_size=9)
        # USB cable
        c.setStrokeColor(DIM); c.setLineWidth(1.2)
        c.line(1.0 * inch, 2.0 * inch, 1.6 * inch, 2.0 * inch)
        c.setFont("Helvetica-Oblique", 7); c.setFillColor(DIM)
        c.drawString(1.05 * inch, 2.08 * inch, "USB-A")
        # SYS TEC
        _box(c, 1.6 * inch, 1.7 * inch, 1.4 * inch, 0.6 * inch,
             "SYS TEC USB-CAN\nsysWORXX 3204001",
             fill=PANEL, stroke=ACCENT, bold=True, font_size=8)
        # DB9 cable
        c.setStrokeColor(DIM); c.setLineWidth(1.2)
        c.line(3.0 * inch, 2.0 * inch, 3.6 * inch, 2.0 * inch)
        c.drawString(3.05 * inch, 2.08 * inch, "DB9")
        # DB9 connector with pinout
        _box(c, 3.6 * inch, 1.5 * inch, 1.4 * inch, 1.0 * inch,
             "", fill=WHITE, stroke=DIM)
        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(4.3 * inch, 2.35 * inch, "DB9 pinout")
        c.setFillColor(INK); c.setFont("Helvetica", 7.5)
        c.drawString(3.7 * inch, 2.10 * inch, "pin 7  ->  CAN H")
        c.drawString(3.7 * inch, 1.92 * inch, "pin 2  ->  CAN L")
        c.drawString(3.7 * inch, 1.74 * inch, "pin 3  ->  GND")
        c.drawString(3.7 * inch, 1.56 * inch, "(others NC)")
        # Two-wire harness to vehicle
        c.setStrokeColor(GREEN); c.setLineWidth(1.5)
        c.line(5.0 * inch, 2.15 * inch, 5.7 * inch, 2.15 * inch)
        c.setStrokeColor(YELLOW); c.setLineWidth(1.5)
        c.line(5.0 * inch, 1.85 * inch, 5.7 * inch, 1.85 * inch)
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(GREEN)
        c.drawString(5.05 * inch, 2.22 * inch, "CAN H (green)")
        c.setFillColor(YELLOW)
        c.drawString(5.05 * inch, 1.72 * inch, "CAN L (yellow)")
        # X437 connector
        _box(c, 5.7 * inch, 1.3 * inch, 1.1 * inch, 1.4 * inch,
             "", fill=PANEL2, stroke=HEAD)
        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(6.25 * inch, 2.60 * inch, "X437 / TDC")
        c.setFillColor(DIM); c.setFont("Helvetica-Oblique", 7)
        c.drawCentredString(6.25 * inch, 2.48 * inch,
                            "(under center screen)")
        # X437 pin pattern (just show 4 example pins)
        c.setFont("Helvetica", 7.5)
        for i, label in enumerate(["chassis CAN H", "chassis CAN L",
                                   "powertrain H", "powertrain L"]):
            y = 2.25 * inch - i * 0.20 * inch
            color = GREEN if i == 0 else YELLOW if i == 1 else DIM
            c.setFillColor(color)
            c.circle(5.85 * inch, y, 2, fill=1, stroke=0)
            c.setFillColor(INK)
            c.drawString(5.95 * inch, y - 2, label)

        # Caption / safety
        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 8.5)
        c.drawString(0, 0.95 * inch, "Verification before live tap:")
        c.setFillColor(INK); c.setFont("Helvetica", 8)
        for i, line in enumerate([
            "1. Multimeter: ~2.5V on both CAN H and CAN L when bus is idle (recessive state).",
            "2. Run can_sniffer.py at 500 kbps. Two or more known Tesla IDs visible confirms chassis CAN.",
            "3. If pins 1/9 of OBD-II are populated on this car, that pair also reaches chassis CAN.",
        ]):
            c.drawString(0, 0.75 * inch - i * 0.18 * inch, line)
        c.restoreState()


class PhaseFlowchart(Flowable):
    """Six-phase plan as a flowchart. Status colors per phase."""

    width = 6.8 * inch
    height = 3.6 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        # Flowable.__init__ resets self.width/height to 0; pull from class
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        c.saveState()

        phases = [
            ("Phase 0", "Close v4.2", "gear shift\nin-car",        ACCENT),
            ("Phase 1", "In-motion",  "steering at\n3-5 mph",      ACCENT),
            ("Phase 2", "Throttle",   "+ brake\nreverse-eng",      YELLOW),
            ("Phase 3", "Rest-roll",  "shift + creep\nprimitive",  YELLOW),
            ("Phase 4", "DX8 RC",     "Spektrum +\nArduino",       ORANGE),
            ("Phase 5", "openpilot",  "long-term\nintegration",    DIM),
        ]
        # Two rows of three boxes
        cols = 3
        bw = 1.7 * inch
        bh = 0.85 * inch
        gap_x = 0.45 * inch
        gap_y = 0.35 * inch
        x0 = 0.4 * inch
        y_top = 1.95 * inch

        positions = []
        for i, (title, name, sub, color) in enumerate(phases):
            r = i // cols
            col = i % cols
            x = x0 + col * (bw + gap_x)
            y = y_top - r * (bh + gap_y)
            positions.append((x + bw / 2, y + bh / 2))
            # Title bar
            c.setFillColor(color)
            c.setStrokeColor(color)
            c.roundRect(x, y + bh - 0.22 * inch, bw, 0.22 * inch,
                        2, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawCentredString(x + bw / 2,
                                y + bh - 0.16 * inch, title)
            # Body
            c.setFillColor(WHITE)
            c.setStrokeColor(color)
            c.setLineWidth(0.8)
            c.roundRect(x, y, bw, bh - 0.22 * inch, 2, fill=1, stroke=1)
            c.setFillColor(HEAD)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(x + bw / 2,
                                y + bh - 0.42 * inch, name)
            c.setFillColor(INK)
            c.setFont("Helvetica", 7.5)
            for j, ln in enumerate(sub.split("\n")):
                c.drawCentredString(x + bw / 2,
                                    y + bh - 0.58 * inch - j * 9, ln)

        # Arrows in row 1: P0 -> P1 -> P2
        for i in range(2):
            x1 = positions[i][0] + bw / 2
            x2 = positions[i + 1][0] - bw / 2
            y = positions[i][1]
            _arrow(c, x1, y, x2, y, color=DIM, width=1)
        # Wrap from P2 down to P3 (right-to-left snake)
        # P2 -> down to P3 (which is at col 0 of row 2)
        # Actually phases are laid out left-to-right top row, then left-to-right bottom row
        # So P2 (top-right) -> P5 (bottom-right) wouldn't be the order.
        # Phases above were laid out P0 P1 P2 / P3 P4 P5
        # So flow is P2 -> P3 (right-top to left-bottom)
        x1 = positions[2][0]
        y1 = positions[2][1] - bh / 2
        x2 = positions[3][0]
        y2 = positions[3][1] + bh / 2
        # Right side down then left then down to P3 top
        _arrow(c, x1 + bw / 2 - 4, y1, x1 + bw / 2 - 4,
               y1 - gap_y / 2 - 2, color=DIM, width=1)
        c.setStrokeColor(DIM); c.setLineWidth(1)
        c.line(x1 + bw / 2 - 4, y1 - gap_y / 2 - 2,
               x2 - bw / 2 + 4, y1 - gap_y / 2 - 2)
        _arrow(c, x2 - bw / 2 + 4, y1 - gap_y / 2 - 2,
               x2 - bw / 2 + 4, y2, color=DIM, width=1)

        # Arrows in row 2: P3 -> P4 -> P5
        for i in range(3, 5):
            x1 = positions[i][0] + bw / 2
            x2 = positions[i + 1][0] - bw / 2
            y = positions[i][1]
            _arrow(c, x1, y, x2, y, color=DIM, width=1)

        c.restoreState()


class CanBusDiagram(Flowable):
    """Pre-AP Model S three-bus topology."""

    width = 6.8 * inch
    height = 3.0 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        # Flowable.__init__ resets self.width/height to 0; pull from class
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        c.saveState()

        buses = [
            ("Chassis CAN 500 kbps",
             ["EPAS rack",  "GTW",  "ESP",  "EPB",  "SCCM",  "DI (chassis side)"],
             ACCENT, 1.95 * inch),
            ("Powertrain CAN 500 kbps",
             ["BMS",  "Charger",  "DI (PT side)",  "TPMS"],
             YELLOW, 1.10 * inch),
            ("Body / OBD-II CAN 500 kbps",
             ["Various body modules",  "OBD-II default pins"],
             DIM, 0.30 * inch),
        ]
        bus_x = 0.0
        bus_w = 6.8 * inch
        for (name, members, color, y) in buses:
            # Bus line
            c.setStrokeColor(color); c.setLineWidth(2.4)
            c.line(bus_x + 1.8 * inch, y, bus_x + bus_w - 0.4 * inch, y)
            c.setFillColor(color); c.setFont("Helvetica-Bold", 9)
            c.drawString(bus_x, y - 3, name)
            # Members as small boxes attached above the bus
            mx = bus_x + 1.85 * inch
            for m in members:
                w = max(0.85 * inch, len(m) * 4.5)
                _box(c, mx, y + 0.05 * inch, w, 0.30 * inch,
                     m, fill=PANEL, stroke=color, font_size=7.5)
                # Tail down to bus
                c.setStrokeColor(color); c.setLineWidth(0.6)
                c.line(mx + w / 2, y + 0.05 * inch, mx + w / 2, y)
                mx += w + 0.10 * inch

        # Tap callout
        c.setStrokeColor(HEAD); c.setLineWidth(0.6)
        c.setDash(2, 2)
        c.line(0.4 * inch, 1.95 * inch + 0.05 * inch,
               0.4 * inch, 0.30 * inch + 0.30 * inch)
        c.setDash()
        c.setFillColor(HEAD); c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(0.0, 0.05 * inch,
                     "X437 / TDC under center screen exposes all 3 buses on "
                     "different pin pairs.")

        c.restoreState()


class DecisionFlowchart(Flowable):
    """Decision tree: based on Phase 0/1 results, what to do next."""

    width = 6.8 * inch
    height = 4.2 * inch

    def wrap(self, availWidth, availHeight):
        cls = type(self)
        # Flowable.__init__ resets self.width/height to 0; pull from class
        return (cls.width, cls.height)

    def draw(self):
        c = self.canv
        cls = type(self)
        c.saveState()

        # Top: Phase 0 outcome
        cx = cls.width / 2
        # Decision diamond: shift works?
        def diamond(c, cx, cy, w, h, label, fill=PANEL2, stroke=HEAD):
            c.setFillColor(fill); c.setStrokeColor(stroke)
            c.setLineWidth(0.8)
            p = c.beginPath()
            p.moveTo(cx - w / 2, cy)
            p.lineTo(cx, cy + h / 2)
            p.lineTo(cx + w / 2, cy)
            p.lineTo(cx, cy - h / 2)
            p.close()
            c.drawPath(p, fill=1, stroke=1)
            c.setFillColor(INK); c.setFont("Helvetica-Bold", 8)
            for i, ln in enumerate(label.split("\n")):
                c.drawCentredString(cx, cy + (1 - i) * 9 - 5, ln)

        diamond(c, cx, 3.65 * inch, 2.0 * inch, 0.55 * inch,
                "Phase 0:\nshift works in-car?")
        # Yes -> Phase 1; No -> further reverse engineering
        _arrow(c, cx - 1.0 * inch, 3.65 * inch,
               1.5 * inch, 3.65 * inch, color=GREEN,
               width=1.2, label="YES")
        _arrow(c, cx + 1.0 * inch, 3.65 * inch,
               5.3 * inch, 3.65 * inch, color=RED,
               width=1.2, label="NO")
        _box(c, 0.2 * inch, 3.45 * inch, 1.3 * inch, 0.45 * inch,
             "Tag v4.2.0 →\nPhase 1", fill=PANEL, stroke=GREEN,
             font_size=8, bold=True)
        _box(c, 5.3 * inch, 3.45 * inch, 1.5 * inch, 0.45 * inch,
             "More 0x6D capture\nLonger burst, etc.",
             fill=PANEL, stroke=RED, font_size=8)

        # Phase 1 outcome
        diamond(c, cx, 2.55 * inch, 2.2 * inch, 0.55 * inch,
                "Phase 1: in-motion\nsteering tracks?")
        _arrow(c, cx, 3.30 * inch, cx, 2.85 * inch,
               color=DIM, width=1)
        _arrow(c, cx - 1.1 * inch, 2.55 * inch,
               1.4 * inch, 2.55 * inch, color=GREEN,
               width=1.2, label="YES")
        _arrow(c, cx + 1.1 * inch, 2.55 * inch,
               5.3 * inch, 2.55 * inch, color=YELLOW,
               width=1.2, label="DEGRADED")
        _box(c, 0.1 * inch, 2.32 * inch, 1.3 * inch, 0.45 * inch,
             "Phase 2: throttle\nreverse-eng",
             fill=PANEL, stroke=GREEN, font_size=8, bold=True)
        _box(c, 5.3 * inch, 2.32 * inch, 1.5 * inch, 0.45 * inch,
             "Tune control loop\nLPF / rate limit",
             fill=PANEL, stroke=YELLOW, font_size=8)

        # Phase 2 outcome
        diamond(c, cx, 1.45 * inch, 2.2 * inch, 0.55 * inch,
                "Phase 2: throttle\ncommand accepted?")
        _arrow(c, cx, 2.20 * inch, cx, 1.75 * inch,
               color=DIM, width=1)
        _arrow(c, cx - 1.1 * inch, 1.45 * inch,
               1.4 * inch, 1.45 * inch, color=GREEN,
               width=1.2, label="YES")
        _arrow(c, cx + 1.1 * inch, 1.45 * inch,
               5.3 * inch, 1.45 * inch, color=ORANGE,
               width=1.2, label="NO")
        _box(c, 0.1 * inch, 1.22 * inch, 1.3 * inch, 0.45 * inch,
             "Phase 3:\nrest-and-roll",
             fill=PANEL, stroke=GREEN, font_size=8, bold=True)
        _box(c, 5.3 * inch, 1.22 * inch, 1.5 * inch, 0.45 * inch,
             "Hardware retrofit\nor scope reduction",
             fill=PANEL, stroke=ORANGE, font_size=8)

        # Phase 3 -> Phase 4 -> Phase 5
        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(cx, 0.85 * inch,
                            "→ Phase 3 → Phase 4 (DX8 RC) → "
                            "Phase 5 (openpilot, long-term)")

        c.restoreState()


# ============================================================================
# Compose document
# ============================================================================

def figure_caption(text, styles):
    return Paragraph(
        f"<b>{text}</b>",
        ParagraphStyle("FigCap", parent=styles["body"],
                        fontSize=9, alignment=TA_CENTER,
                        textColor=HEAD, spaceBefore=4, spaceAfter=10))


def get_styles():
    s = getSampleStyleSheet()
    base = s["BodyText"]
    body = ParagraphStyle("Body", parent=base, fontName="Helvetica",
                          fontSize=10, leading=14, textColor=INK,
                          alignment=TA_JUSTIFY, spaceAfter=6)
    h1 = ParagraphStyle("H1", parent=s["Heading1"], fontName="Helvetica-Bold",
                        fontSize=20, leading=26, textColor=HEAD,
                        spaceBefore=18, spaceAfter=10)
    h2 = ParagraphStyle("H2", parent=s["Heading2"], fontName="Helvetica-Bold",
                        fontSize=14, leading=18, textColor=HEAD,
                        spaceBefore=14, spaceAfter=6)
    h3 = ParagraphStyle("H3", parent=s["Heading3"], fontName="Helvetica-Bold",
                        fontSize=11, leading=14, textColor=ACCENT,
                        spaceBefore=10, spaceAfter=4)
    callout = ParagraphStyle("Callout", parent=body, fontSize=9,
                              backColor=PANEL, borderColor=RULE,
                              borderWidth=0.5, borderPadding=8,
                              leftIndent=0, rightIndent=0,
                              spaceBefore=8, spaceAfter=8,
                              alignment=TA_LEFT)
    code = ParagraphStyle("Code", parent=body, fontName="Courier",
                           fontSize=9, leading=12, textColor=INK,
                           backColor=PANEL2, borderColor=RULE,
                           borderWidth=0.5, borderPadding=6,
                           leftIndent=0, alignment=TA_LEFT,
                           spaceAfter=6)
    cover_title = ParagraphStyle("CoverTitle", parent=s["Title"],
                                  fontName="Helvetica-Bold", fontSize=32,
                                  leading=38, textColor=HEAD,
                                  alignment=TA_CENTER, spaceAfter=18)
    cover_sub = ParagraphStyle("CoverSub", parent=body, fontSize=14,
                                leading=18, textColor=DIM,
                                alignment=TA_CENTER, spaceAfter=6)
    return {"body": body, "h1": h1, "h2": h2, "h3": h3,
            "callout": callout, "code": code,
            "cover_title": cover_title, "cover_sub": cover_sub}


def status_table():
    data = [
        ["State", "Status", "Where verified"],
        ["Steering on jacks (±60°)",       "Production",     "session 232457"],
        ["Steering in-motion (3-5 mph)",   "Untested",       "Phase 1"],
        ["Standstill ground steering",     "Out of scope",   "physics"],
        ["Gear shift command",             "Bench-correct",  "commit eae24c4"],
        ["30 MPH MODE in-car",             "Refused (safe)", "session 000935"],
        ["Brake / gear / DI speed read",   "Production",     "session 002425"],
        ["Theory C flicker",               "Resolved",       "Section 8"],
        ["ESP contention",                 "Resolved",       "Section 9"],
        ["Throttle / brake / shift RC",    "Not started",    "Phase 2-4"],
    ]
    t = Table(data, colWidths=[2.6 * inch, 1.6 * inch, 2.4 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 9.5),
        ("ALIGN",      (0, 0), (-1, 0), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BACKGROUND", (0, 1), (-1, -1), WHITE),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 1), (-1, -1), 9),
        ("TEXTCOLOR",  (0, 1), (-1, -1), INK),
        ("GRID",       (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL]),
    ]))
    return t


def can_proto_table():
    data = [
        ["ID",   "Name",                "Direction", "Rate",     "Notes"],
        ["0x488", "DAS_steeringControl", "TX",       "50 Hz",    "Steering command (4 B, sum checksum)"],
        ["0x214", "EPB_epasControl",     "TX",       "10 Hz",    "Required keepalive (3 B, sum checksum)"],
        ["0x101", "GTW_epasControl",     "TX optional", "20 Hz", "Off when real GTW alive (3 B)"],
        ["0x155", "ESP_B fake speed",    "TX optional", "200 Hz","30 MPH MODE only (8 B)"],
        ["0x6D",  "SBW_RQ_SCCM",         "TX (burst)", "100 Hz", "Gear shift (4 B, CRC-8/J1850)"],
        ["0x370", "EPAS_sysStatus",      "RX",        "~100 Hz", "Rack status (8 B)"],
        ["0x118", "DI_torque2",          "RX",        "~100 Hz", "Gear, brake, DI speed (6 B)"],
    ]
    t = Table(data, colWidths=[0.65 * inch, 1.65 * inch, 0.95 * inch,
                                0.65 * inch, 2.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 1), (-1, -1), 8.5),
        ("FONTNAME",   (0, 1), (0, -1), "Courier"),
        ("FONTSIZE",   (0, 1), (0, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.4, RULE),
        ("ALIGN",      (3, 0), (3, -1), "RIGHT"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL]),
    ]))
    return t


def build():
    styles = get_styles()
    deco = PageDeco()
    doc = SimpleDocTemplate(
        OUT_PATH, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.85 * inch, bottomMargin=0.75 * inch,
    )
    story = []

    # ---- Cover ----
    story.append(Spacer(1, 1.4 * inch))
    story.append(Paragraph("Tesla Rack Control", styles["cover_title"]))
    story.append(Paragraph("Implementation Roadmap", styles["cover_title"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("From v4.2 bench validation through<br/>"
                            "RC integration to openpilot",
                            styles["cover_sub"]))
    story.append(Spacer(1, 1.2 * inch))
    cover_table = Table([
        ["Project", "Tesla Rack Control"],
        ["Vehicle", "2013 Tesla Model S, pre-AP, post-May 2013 build"],
        ["Current version", "v4.2.0-dev"],
        ["Branch", "dev/v4.2-prnd"],
        ["Authors", "Derek Nagel · Jordan · Charlie Yonkura · Claude"],
        ["Document date", datetime.now().strftime("%Y-%m-%d")],
    ], colWidths=[1.6 * inch, 4.2 * inch])
    cover_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), HEAD),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(
        "<i>This document plans implementation only. Read "
        "PROJECT_MEMORY.md for the canonical reference of verified "
        "facts. Read SAFETY.md before any field test.</i>",
        ParagraphStyle("CoverNote", parent=styles["body"],
                       textColor=DIM, alignment=TA_CENTER, fontSize=9,
                       fontName="Helvetica-Oblique")))
    story.append(PageBreak())

    # ---- Section 1: Executive summary ----
    story.append(Paragraph("1. Executive summary", styles["h1"]))
    story.append(Paragraph(
        "The tesla-rack-control project commands a 2013 Tesla Model S "
        "EPAS rack from a laptop over CAN, with the patched rack "
        "firmware accepting <font face='Courier' size='9'>0x488 "
        "DAS_steeringControl</font> directly. As of v4.2.0-dev "
        "(2026-05-07), the steering control loop is production-ready "
        "for on-jacks tests at &plusmn;60 degrees and is ready for "
        "in-motion validation at 3-5 mph in a parking lot.",
        styles["body"]))
    story.append(Paragraph(
        "The end goal is a fully RC-controlled car: laptop or Spektrum "
        "DX8 transmitter via Arduino commands steering, throttle, "
        "brake, and gear shift over CAN, with eventual openpilot "
        "integration once the control surfaces are stable.",
        styles["body"]))
    story.append(Paragraph(
        "<b>Standstill steering with wheels on the ground is out of "
        "scope.</b> Per Tesla&apos;s own production behavior and the "
        "physics of static tire friction, full-authority steering at "
        "literal zero speed is not achievable without invasive hardware "
        "modification. The realistic equivalent is a "
        "<b>rest-and-roll</b> primitive: brief brake release, tiny "
        "creep, steer, re-apply brake. This is what every modern "
        "park-assist system does.",
        styles["callout"]))
    story.append(Paragraph("Current state at a glance",
                            styles["h3"]))
    story.append(status_table())
    story.append(PageBreak())

    # ---- Section 2: System overview ----
    story.append(Paragraph("2. System overview", styles["h1"]))
    story.append(Paragraph(
        "The project converges two input paths onto the chassis CAN "
        "bus. The laptop path (currently in production) uses a "
        "SYS TEC USB-CAN adapter and the Python "
        "<font face='Courier' size='9'>tesla_control.py</font> "
        "program. The future Spektrum DX8 path will use an Arduino as "
        "an SBUS-to-CAN bridge. Only one path is active at a time -- "
        "they share the same CAN arbitration ID space.",
        styles["body"]))
    story.append(SystemBlockDiagram())
    story.append(figure_caption(
        "Figure 1. System block diagram. Two input paths "
        "converge on the chassis CAN bus; only one is active.",
        styles))
    story.append(Paragraph("Hardware wiring", styles["h2"]))
    story.append(Paragraph(
        "The SYS TEC USB-CAN adapter connects to the Tesla chassis "
        "CAN bus via the X437 / TDC connector under the center "
        "screen. This is the most reliable tap point on pre-AP cars; "
        "OBD-II pins 1 and 9 are sometimes populated with chassis CAN "
        "but vary by build date.",
        styles["body"]))
    story.append(WiringDiagram())
    story.append(figure_caption(
        "Figure 2. SYS TEC USB-CAN to X437 / TDC chassis CAN tap. "
        "Verified pin assignments.",
        styles))
    story.append(PageBreak())

    # ---- Section 3: CAN bus topology + protocol ----
    story.append(Paragraph("3. CAN bus & protocol",
                            styles["h1"]))
    story.append(Paragraph(
        "Pre-AP Model S has three independent CAN buses. We use the "
        "chassis bus exclusively. Verified against the Tinkla wiki "
        "and TeslaMotorsClub reverse-engineering threads.",
        styles["body"]))
    story.append(CanBusDiagram())
    story.append(figure_caption(
        "Figure 3. Pre-AP Model S CAN bus topology. Three independent "
        "buses; we tap chassis at X437 / TDC.",
        styles))
    story.append(Paragraph("Messages we use", styles["h2"]))
    story.append(Paragraph(
        "All bit positions verified against the opendbc "
        "<font face='Courier' size='9'>tesla_can.dbc</font> file. "
        "Two integrity algorithms are in play: a simple sum checksum "
        "for the steering control set, and CRC-8/SAE-J1850 (poly "
        "<font face='Courier' size='9'>0x1D</font>) for the gear "
        "shift and stalk messages. Both algorithms verified against "
        "BogGyver/panda&apos;s reference implementation and 18,414 "
        "real captured stalk frames.",
        styles["body"]))
    story.append(can_proto_table())
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "<b>Sign convention</b> (verified by Jordan in-car "
        "2026-05-03): positive commanded angle = wheel turns RIGHT.",
        styles["callout"]))
    story.append(PageBreak())

    # ---- Section 4: Phased plan ----
    story.append(Paragraph("4. Phased plan", styles["h1"]))
    story.append(Paragraph(
        "Six phases from current state to long-term openpilot "
        "integration. Each phase has explicit acceptance criteria. "
        "The roadmap is gated: progression depends on the previous "
        "phase&apos;s outcome (see Figure 5).",
        styles["body"]))
    story.append(PhaseFlowchart())
    story.append(figure_caption(
        "Figure 4. Six-phase plan. Color-coded by status: blue = "
        "active or imminent, yellow = upcoming, gray = long-term.",
        styles))

    phase_blocks = [
        ("Phase 0  ·  Close out v4.2", "this week",
         "Validate the gear shift fix in-car. The byte 0/1 fix from commit "
         "<font face='Courier' size='9'>eae24c4</font> is bench-correct (matches all six "
         "captured shift frames byte-for-byte) but has not yet been re-tested in-car.",
         "Clicking N/D/R in the GUI causes the Gear cell to update within 300 ms with brake pressed."),
        ("Phase 1  ·  In-motion steering", "next week",
         "Drive the car at 3-5 mph in a safe parking lot, command steering from the laptop. "
         "Real ESP reports actual speed, rack opens its at-speed envelope honestly, no spoofing required. "
         "This is the cleanest possible validation of the steering control loop.",
         "Rack tracks commanded angles within 2 deg divergence at 3-5 mph, no E-STOPs, no flicker, "
         "session log saved to repo."),
        ("Phase 2  ·  Throttle &amp; brake reverse engineering", "weeks 2-4",
         "Identify and command the CAN messages for go-pedal and brake-pedal on this 2013 "
         "Model S. Pre-AP uses vacuum-based braking; full software brake authority may not be "
         "achievable without hardware additions.",
         "Laptop can command 0-10% throttle and 0-30% brake from a stationary rolled position, "
         "with auto-disengage on any anomaly."),
        ("Phase 3  ·  Rest-and-roll primitive", "week 4",
         "Combine steering + gear control such that the laptop holds the car in P, commands "
         "shift to D, briefly releases brake, executes a small steering command during the "
         "creep, re-applies brake, returns to P. Mirrors Tesla&apos;s own Autopark routine.",
         "Scripted maneuver completes from stop, moves the car ~1 ft, returns to stop with "
         "brake applied."),
        ("Phase 4  ·  Spektrum DX8 + Arduino bridge", "weeks 5-6",
         "Replace the laptop GUI with a DX8 transmitter as primary control. Spektrum receiver "
         "on Arduino Nano UART, MCP2515 CAN module wired into chassis CAN. Channel mapping: "
         "left stick X = steering, right stick Y = throttle, switch = gear.",
         "DX8 transmitter steers, accelerates, brakes, and shifts the car. Laptop is optional "
         "(used for logging only)."),
        ("Phase 5  ·  openpilot integration", "long-term",
         "Out of scope for v4.x. Once steering + throttle + brake + shift are all "
         "CAN-commandable, openpilot&apos;s controlsd can emit those commands instead of the "
         "DX8. Likely path: fork BogGyver, integrate our improvements, write the safety model "
         "in the panda firmware.",
         "openpilot drives the car with our control surfaces. Specific success criteria "
         "deferred until Phase 4 lessons land."),
    ]

    for title, when, desc, accept in phase_blocks:
        block = []
        block.append(Paragraph(title, styles["h2"]))
        block.append(Paragraph(
            f"<font color='#5a6473'><i>Timing: {when}</i></font>",
            styles["body"]))
        block.append(Paragraph(desc, styles["body"]))
        block.append(Paragraph(
            f"<b>Acceptance:</b> {accept}", styles["callout"]))
        block.append(Spacer(1, 0.05 * inch))
        story.append(KeepTogether(block))

    story.append(PageBreak())

    # ---- Section 5: Decision flow ----
    story.append(Paragraph("5. Decision flow", styles["h1"]))
    story.append(Paragraph(
        "Each phase has an outcome that gates progression. If a "
        "phase fails its acceptance criteria, the project does not "
        "blindly continue -- we either iterate within the phase, "
        "scope-reduce, or pivot.",
        styles["body"]))
    story.append(DecisionFlowchart())
    story.append(figure_caption(
        "Figure 5. Decision tree after each phase. Diamonds are "
        "decision points; rectangles are the resulting next action.",
        styles))
    story.append(PageBreak())

    # ---- Section 6: Risks ----
    story.append(Paragraph("6. Risks &amp; mitigations",
                            styles["h1"]))
    risk_data = [
        ["Risk",                                              "Probability",  "Impact",  "Mitigation"],
        ["Rack stall torque insufficient even at full envelope", "Medium",   "High",    "Rest-and-roll (Phase 3)"],
        ["Pre-AP vacuum brake limits brake authority",           "Medium",   "Medium",  "Scope-limit Phase 2"],
        ["Throttle reverse engineering takes longer than 3 wks", "High",     "Medium",  "Pre-budget 4-5 weeks"],
        ["Real stalk wins 0x6D arbitration after byte fix",      "Low",      "Low",     "Longer burst, faster rate"],
        ["Repeated rack reflash bricks the rack",                "Low",      "Critical","Don't reflash without reason"],
        ["ESP contention on second toggle attempt",              "Mitigated","--",      "Pre-flight check refuses (v4.2)"],
        ["3X-style 0x488 contention on second device",           "Mitigated","--",      "Bus diag panel auto-flags (v4.2)"],
    ]
    rt = Table(risk_data, colWidths=[3.0 * inch, 0.85 * inch, 0.75 * inch, 1.65 * inch])
    rt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 1), (-1, -1), 8.5),
        ("GRID",       (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",(0, 0), (-1, -1), 5),
        ("RIGHTPADDING",(0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL]),
    ]))
    story.append(rt)
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "<b>Anti-patterns to avoid:</b> 30 MPH MODE on a live in-car bus "
        "(causes ESP cascade); leaving a comma 3X on chassis CAN while "
        "running tesla_control.py (Theory C contention); trusting the "
        "DBC blindly for CRC-protected commands (we caught two missing "
        "fixed-bit fields by capturing real stalk frames). All "
        "preventable; all already mitigated in v4.2.",
        styles["callout"]))
    story.append(PageBreak())

    # ---- Section 7: Safety summary ----
    story.append(Paragraph("7. Safety summary", styles["h1"]))
    story.append(Paragraph(
        "The full safety model lives in <font face='Courier' size='9'>"
        "SAFETY.md</font> and <font face='Courier' size='9'>"
        "tesla_control.py</font>. This section is a one-page summary "
        "for quick reference.",
        styles["body"]))
    story.append(Paragraph("Hard rules", styles["h2"]))
    for rule in [
        "Front wheels off the ground or tie rods disconnected before any active testing.",
        "No passengers in or near the car during testing.",
        "No driving on a public road. Ever.",
        "Driver hands off the wheel during ENGAGE.",
        "30 MPH MODE on jacks only -- never with the real ESP module on the bus.",
    ]:
        story.append(Paragraph(f"• {rule}", styles["body"]))
    story.append(Paragraph("Defense in depth (in tesla_control.py)",
                            styles["h2"]))
    for layer in [
        "Hard angle clamp (180 deg in software, ~60 deg enforced by rack at standstill).",
        "Rate limit (150 deg/sec) and 150 ms low-pass filter on user input.",
        "RX timeout watchdog: 0x370 lost > 500 ms triggers E-STOP.",
        "Bus error watchdog: > 50 CAN error frames triggers E-STOP.",
        "Loop overrun watchdog: 50 Hz TX loop late > 100 ms triggers E-STOP.",
        "EAC bounce watchdog: > 5 EAC transitions in 1 second triggers E-STOP.",
        "Real-motion auto-disengage if DI vehicle speed > 1 mph while engaged.",
        "Gear-out-of-park auto-disengage if gear leaves P while engaged.",
        "Park-to-engage gate: ENGAGE refused if gear is not P (when DI visible).",
        "30 MPH MODE pre-flight check: refuses if real ESP traffic detected.",
        "Four manual E-STOP paths: red button, ESC, Q, window close.",
    ]:
        story.append(Paragraph(f"• {layer}", styles["body"]))
    story.append(PageBreak())

    # ---- Appendix A: Field test screenshots ----
    story.append(Paragraph("Appendix A. Field test evidence",
                            styles["h1"]))
    story.append(Paragraph(
        "Screenshots from the May 2026 field test sessions, captured "
        "by Charlie. These show prior versions of the GUI under load "
        "(v2 / v3 architectures); the current v4.2 GUI is documented "
        "in <font face='Courier' size='9'>docs/GUIDE.md</font>.",
        styles["body"]))
    images = [
        ("03May2026_1.png", "Session 03 May 2026 -- early test script + GUI"),
        ("03May2026_2354_2.png", "Session 03 May 2026 23:54 -- HIGH_ANGLE_RATE_REQ flicker visible"),
        ("04May2026_0006_3.png", "Session 04 May 2026 00:06 -- HIGH_ANGLE_RATE_REQ during active test"),
        ("04May2026_0025_4.png", "Session 04 May 2026 00:25 -- HIGH_ANGLE_REQ at +90° standstill"),
    ]
    for i, (fname, caption) in enumerate(images):
        path = os.path.join(REPO_ROOT, "field_testing", fname)
        if not os.path.exists(path):
            story.append(Paragraph(f"[image {fname} not found]",
                                    styles["body"]))
            continue
        try:
            # Use PIL to read the actual image dimensions and scale
            # to fit the page width while preserving aspect ratio.
            from PIL import Image as PILImage
            with PILImage.open(path) as pim:
                native_w, native_h = pim.size
            target_w = 6.5 * inch
            scale = target_w / native_w
            target_h = native_h * scale
            # Cap at ~3.7 inch tall so two images fit per page
            if target_h > 3.7 * inch:
                target_h = 3.7 * inch
                target_w = native_w * (target_h / native_h)
            img = Image(path, width=target_w, height=target_h)
            cap = Paragraph(f"<i>{caption}</i>",
                            ParagraphStyle("ImgCap",
                                           parent=styles["body"],
                                           alignment=TA_CENTER,
                                           textColor=DIM,
                                           fontSize=8.5,
                                           spaceBefore=2,
                                           spaceAfter=14))
            story.append(KeepTogether([img, cap]))
            # Force a page break after every two images so they get
            # the full width and don't squeeze.
            if (i + 1) % 2 == 0 and i < len(images) - 1:
                story.append(PageBreak())
        except Exception as e:
            story.append(Paragraph(
                f"[image {fname} skipped: {e}]", styles["body"]))

    story.append(PageBreak())

    # ---- Appendix B: References ----
    story.append(Paragraph("Appendix B. References",
                            styles["h1"]))
    story.append(Paragraph("Verified sources used in this roadmap",
                            styles["h3"]))
    refs = [
        ("gregjhogan/tesla-pre-ap-epas-patch",
         "https://github.com/gregjhogan/tesla-pre-ap-epas-patch",
         "EPAS firmware patch source. Three patched bytes verified at addresses "
         "0x031750, 0x031892, 0x031974."),
        ("BogGyver/panda safety_tesla.h",
         "https://github.com/BogGyver/panda/blob/tesla_unity_dev/board/safety/safety_tesla.h",
         "Reference panda firmware. tesla_compute_crc lookup table verified to use "
         "polynomial 0x1D (CRC-8/J1850)."),
        ("opendbc tesla_can.dbc",
         "https://github.com/BYDcar/opendbc-byd/blob/master/tesla_can.dbc",
         "Bit positions and enums for all Tesla CAN messages used."),
        ("Tinkla wiki",
         "https://tinkla.us/index.php/Welcome_to_Tinkla!",
         "Pre-AP retrofit ecosystem. CAN bus topology and OBD-II pin info."),
        ("Tesla recall: loss of EPAS at 0 mph",
         "https://www.tesla.com/support/recall-vehicle-firmware-correct-loss-of-epas",
         "Confirms Tesla&apos;s production EPAS is intended to assist at 0 mph."),
        ("comma openpilot tools/joystick",
         "https://github.com/commaai/openpilot/tree/master/tools/joystick",
         "Reference implementation of joystick-based CAN steering control."),
        ("MUXSAN 3-port CAN MITM bridge",
         "https://www.tindie.com/products/muxsan/can-mitm-bridge-3-port-rev-25/",
         "Commercial precedent for the hardware MITM bridge approach (Phase 2 alt)."),
        ("Open-source CAN bridge by Emile Nijssen",
         "https://www.hackster.io/news/emile-nijssen-s-open-source-can-bridge-makes-automotive-man-in-the-middle-a-cinch-b4dfeb952b04",
         "Open-source MITM precedent for cheaper alternative."),
    ]
    for title, url, note in refs:
        story.append(Paragraph(
            f"<b>{title}</b><br/>"
            f"<font face='Courier' size='8' color='#1e6fd9'>{url}</font><br/>"
            f"{note}",
            ParagraphStyle("Ref", parent=styles["body"],
                            spaceAfter=10, fontSize=9.5)))

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Project-internal verified artifacts",
                            styles["h3"]))
    story.append(Paragraph(
        "<font face='Courier' size='9'>field_testing/captures/"
        "20260507_011220_shift_diagnostic/capture.csv</font> -- 18,414 "
        "real stalk frames captured by Charlie 2026-05-07. CRC verified, "
        "byte 0 / byte 1 fixed bits discovered. All shift positions "
        "confirmed.",
        styles["body"]))
    story.append(Paragraph(
        "<font face='Courier' size='9'>logs/session_20260506_232457.log"
        "</font> -- Theory C flicker fingerprint: 280+ EAC transitions "
        "in 67 seconds when 30 MPH MODE was toggled on.",
        styles["body"]))
    story.append(Paragraph(
        "<font face='Courier' size='9'>logs/session_20260507_000935.log"
        "</font> -- Pre-flight ESP check working: 30 MPH MODE refused "
        "twice with clear log message.",
        styles["body"]))

    # ---- Build ----
    doc.build(story, onFirstPage=deco.draw, onLaterPages=deco.draw)
    print(f"OK: wrote {OUT_PATH} ({os.path.getsize(OUT_PATH):,} bytes)")


if __name__ == "__main__":
    build()
