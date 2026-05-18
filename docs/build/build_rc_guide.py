"""
Generate RC_IMPLEMENTATION_GUIDE.pdf -- the printable companion to
the v5 RC bridge.

Matches the visual style of ROADMAP.pdf (same palette, same page
template, same flowable patterns). All diagrams are drawn
programmatically -- no fabricated photographs.

Run:   python docs/build/build_rc_guide.py
Out:   docs/build/RC_IMPLEMENTATION_GUIDE.pdf
"""

import os
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Flowable, KeepTogether,
)
from reportlab.pdfgen import canvas as canvas_mod

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_PATH = os.path.join(HERE, "RC_IMPLEMENTATION_GUIDE.pdf")

# Palette (matches build_pdf.py for ROADMAP)
INK     = colors.HexColor("#0d1726")
HEAD    = colors.HexColor("#0d2538")
DIM     = colors.HexColor("#5a6473")
RULE    = colors.HexColor("#cad3df")
PANEL   = colors.HexColor("#f1f5f9")
PANEL2  = colors.HexColor("#e2e8f0")
ACCENT  = colors.HexColor("#1e6fd9")
GREEN   = colors.HexColor("#15803d")
YELLOW  = colors.HexColor("#b45309")
ORANGE  = colors.HexColor("#c2410c")
RED     = colors.HexColor("#b91c1c")
WHITE   = colors.white


class PageDeco:
    def __init__(self, title="Tesla Rack Control · RC Implementation Guide"):
        self.title = title

    def draw(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE); canvas.setLineWidth(0.5)
        canvas.line(0.75 * inch, 0.55 * inch, 7.75 * inch, 0.55 * inch)
        canvas.setFillColor(DIM); canvas.setFont("Helvetica", 8)
        canvas.drawString(0.75 * inch, 0.40 * inch, self.title)
        canvas.drawRightString(7.75 * inch, 0.40 * inch, f"Page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.line(0.75 * inch, 10.45 * inch, 7.75 * inch, 10.45 * inch)
        canvas.setFont("Helvetica-Bold", 8); canvas.setFillColor(HEAD)
        canvas.drawString(0.75 * inch, 10.55 * inch, "TESLA RACK CONTROL")
        canvas.setFont("Helvetica", 8); canvas.setFillColor(DIM)
        canvas.drawRightString(7.75 * inch, 10.55 * inch, "v5.0.0-rc2")
        canvas.restoreState()


# ============================================================================
# Diagrams
# ============================================================================

class SystemBlockDiagram(Flowable):
    """The top-of-page block diagram: DX8 -> AR6200 -> Nano -> Laptop -> CAN -> Rack."""

    HEIGHT = 1.9 * inch

    def __init__(self):
        super().__init__()
        self.width = 7.0 * inch
        self.height = self.HEIGHT

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        # Six rounded blocks in a row, with arrows between them.
        blocks = [
            ("DX8",              "transmitter\nDSMX air",            ACCENT),
            ("AR6200",           "receiver\n6 PWM ch",                ACCENT),
            ("Arduino\nNano",    "PCINT reader\nCOBS @ 100 Hz",      GREEN),
            ("Laptop",           "tesla_control_rc.py\nv5",          GREEN),
            ("SYS TEC",          "USB-CANmodul1",                    ORANGE),
            ("Tesla\nrack",      "patched EPAS",                     RED),
        ]
        n = len(blocks)
        margin = 0.05 * inch
        gap = 0.10 * inch
        block_w = (self.width - 2 * margin - (n - 1) * gap) / n
        block_h = 0.95 * inch
        baseline_y = (self.height - block_h) / 2 + 0.05 * inch

        x = margin
        centers = []
        for (title, subtitle, color) in blocks:
            c.setStrokeColor(color); c.setFillColor(WHITE); c.setLineWidth(1.5)
            c.roundRect(x, baseline_y, block_w, block_h, 6, stroke=1, fill=1)
            c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 9.5)
            # Title (possibly two lines)
            for i, line in enumerate(title.split("\n")):
                c.drawCentredString(x + block_w / 2,
                                    baseline_y + block_h - 0.18 * inch - i * 0.14 * inch,
                                    line)
            # Subtitle (smaller, multi-line)
            c.setFillColor(DIM); c.setFont("Helvetica", 7.5)
            sub_lines = subtitle.split("\n")
            for i, line in enumerate(sub_lines):
                c.drawCentredString(x + block_w / 2,
                                    baseline_y + 0.20 * inch - i * 0.12 * inch,
                                    line)
            centers.append((x + block_w, baseline_y + block_h / 2))
            x += block_w + gap

        # Arrows between blocks
        for i in range(n - 1):
            x1, y = centers[i]
            x2 = x1 + gap
            c.setStrokeColor(DIM); c.setLineWidth(1.3)
            c.line(x1, y, x2 - 0.04 * inch, y)
            # arrowhead
            c.setFillColor(DIM)
            p = c.beginPath()
            p.moveTo(x2 - 0.04 * inch, y)
            p.lineTo(x2 - 0.12 * inch, y + 0.04 * inch)
            p.lineTo(x2 - 0.12 * inch, y - 0.04 * inch)
            p.close()
            c.drawPath(p, stroke=0, fill=1)


class PinoutDiagram(Flowable):
    """The AR6200 -> Arduino Nano wiring diagram.

    Visual no-overlap design:
    - AR6200 is the left block. Only the 3 USED channels (2, 5, 6) show
      a 3-pin servo header. Unused channels are just text rows.
    - 5 wires total. The SIG wires (ch2/5/6 -> D2/D3/D4) run as simple
      L-shapes in their own horizontal band, no crossings.
    - Power/ground exit ch2's V+ and GND pins through a short stub,
      then drop BELOW the receiver into a power rail, then run right
      and UP into the Nano's 5V/GND pins. This keeps the power wires
      entirely out of the SIG wire band.
    - Wire labels live at the L-bend, away from any channel labels or
      Nano pin labels.
    """

    HEIGHT = 5.4 * inch

    def __init__(self):
        super().__init__()
        self.width = 7.0 * inch
        self.height = self.HEIGHT

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        W = self.width

        # ---- Receiver block (left) ----
        rx_x = 0.45 * inch
        rx_y = 0.85 * inch       # leave room BELOW for power rail
        rx_w = 2.1 * inch
        rx_h = 4.1 * inch

        c.setStrokeColor(HEAD); c.setLineWidth(1.8); c.setFillColor(WHITE)
        c.roundRect(rx_x, rx_y, rx_w, rx_h, 6, stroke=1, fill=1)

        # Header in its own band at the top
        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(rx_x + rx_w / 2, rx_y + rx_h - 0.27 * inch,
                            "Spektrum AR6200")
        c.setFillColor(DIM); c.setFont("Helvetica", 7.5)
        c.drawCentredString(rx_x + rx_w / 2, rx_y + rx_h - 0.42 * inch,
                            "(SPMAR6200)")

        # Channel rows, well below the header
        ch_top_y    = rx_y + rx_h - 0.80 * inch
        ch_pitch_y  = 0.50 * inch
        ch_label_x  = rx_x + 0.15 * inch
        ch_pin_x    = rx_x + rx_w - 0.45 * inch     # x of the SIG pin
        pin_dx      = 0.13 * inch
        used_ch = {2, 5, 6}

        sig_coords = {}

        for i, ch in enumerate([1, 2, 3, 4, 5, 6]):
            y = ch_top_y - i * ch_pitch_y
            highlight = ch in used_ch
            c.setFont("Helvetica-Bold" if highlight else "Helvetica", 9)
            c.setFillColor(HEAD if highlight else DIM)
            label = {1: "ch1 THRO", 2: "ch2 AILE", 3: "ch3 ELEV",
                     4: "ch4 RUDD", 5: "ch5 GEAR", 6: "ch6 AUX1"}[ch]
            c.drawString(ch_label_x, y - 0.04 * inch, label)

            for j, role in enumerate(["GND", "V+", "SIG"]):
                px = ch_pin_x - (2 - j) * pin_dx
                if highlight:
                    c.setFillColor({"GND": HEAD, "V+": RED, "SIG": ACCENT}[role])
                else:
                    c.setFillColor(RULE)
                c.circle(px, y, 0.045 * inch, stroke=0, fill=1)
                if role == "SIG" and highlight:
                    sig_coords[ch] = (px, y)
                if role == "V+" and ch == 2:
                    sig_coords["V+"] = (px, y)
                if role == "GND" and ch == 2:
                    sig_coords["GND"] = (px, y)

        # Single pin role legend on the receiver (below ch6, inside the
        # box) so we don't paint role text against every channel.
        c.setFillColor(DIM); c.setFont("Helvetica-Oblique", 6.5)
        legend_y = rx_y + 0.25 * inch
        c.drawCentredString(ch_pin_x - pin_dx, legend_y, "GND")
        c.drawCentredString(ch_pin_x, legend_y, "V+")
        c.drawCentredString(ch_pin_x + pin_dx, legend_y, "SIG")
        c.setFont("Helvetica", 6.5)
        c.drawString(rx_x + 0.15 * inch, legend_y,
                     "pin roles →")

        # ---- Arduino Nano (right) ----
        nano_x = W - 0.45 * inch - 1.85 * inch
        nano_y = rx_y + 0.10 * inch
        nano_w = 1.85 * inch
        nano_h = 3.4 * inch

        c.setStrokeColor(HEAD); c.setLineWidth(1.8); c.setFillColor(WHITE)
        c.roundRect(nano_x, nano_y, nano_w, nano_h, 6, stroke=1, fill=1)

        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(nano_x + nano_w / 2,
                            nano_y + nano_h - 0.27 * inch,
                            "Arduino Nano")
        c.setFillColor(DIM); c.setFont("Helvetica", 7.5)
        c.drawCentredString(nano_x + nano_w / 2,
                            nano_y + nano_h - 0.42 * inch,
                            "(ATmega328P, 16 MHz)")

        # USB end visualization on the FAR right of the Nano
        usb_x = nano_x + nano_w
        usb_y = nano_y + nano_h - 0.65 * inch
        c.setStrokeColor(HEAD); c.setLineWidth(1.2); c.setFillColor(PANEL2)
        c.rect(usb_x, usb_y - 0.08 * inch, 0.15 * inch, 0.16 * inch,
               stroke=1, fill=1)
        c.setFillColor(DIM); c.setFont("Helvetica-Oblique", 7)
        c.drawString(usb_x + 0.18 * inch, usb_y - 0.02 * inch,
                     "mini-USB")
        c.drawString(usb_x + 0.18 * inch, usb_y - 0.13 * inch,
                     "to laptop")

        # Nano pins: LEFT side of the Nano, top to bottom in the SAME
        # ORDER that wires arrive from the left so we never cross.
        # Top-to-bottom on left side: D2, D3, D4 (signal wires from
        # ch2/5/6 SIG, which themselves go top-to-bottom on the rx).
        # GND and 5V are placed BELOW D2-D4 at the bottom of the Nano
        # so they line up with the bottom power rail.
        nano_pins = [
            ("D2",  ACCENT),
            ("D3",  ACCENT),
            ("D4",  ACCENT),
            ("5V",  RED),
            ("GND", HEAD),
        ]
        nano_pin_x = nano_x + 0.18 * inch
        pin_top_y  = nano_y + nano_h - 0.85 * inch
        pin_bot_y  = nano_y + 0.45 * inch
        pin_step   = (pin_top_y - pin_bot_y) / (len(nano_pins) - 1)

        nano_pin_coords = {}
        for i, (label, col) in enumerate(nano_pins):
            py = pin_top_y - i * pin_step
            c.setFillColor(col)
            c.circle(nano_pin_x, py, 0.055 * inch, stroke=0, fill=1)
            c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 9)
            c.drawString(nano_pin_x + 0.14 * inch, py - 0.04 * inch, label)
            nano_pin_coords[label] = (nano_pin_x, py)

        # ---- Wires ----
        # Each SIG wire: L-shape, signal pin -> drop/rise to D-pin y ->
        # in to D-pin x. Vertical order is preserved on both ends, so
        # the three SIG wires can never cross each other.
        def sig_wire(start_xy, end_xy, color, label_text, label_dy=0.05):
            (sx, sy) = start_xy
            (ex, ey) = end_xy
            c.setStrokeColor(color); c.setLineWidth(2.0)
            mid_x = sx + 0.45 * inch
            c.line(sx, sy, mid_x, sy)
            c.line(mid_x, sy, mid_x, ey)
            c.line(mid_x, ey, ex, ey)
            # Label on the long horizontal run, above the line, away
            # from any channel labels (mid_x is to the RIGHT of the rx).
            c.setFillColor(color); c.setFont("Helvetica-Bold", 7.5)
            c.drawString(mid_x + 0.10 * inch, (sy + ey) / 2 + label_dy * inch,
                         label_text)

        sig_wire(sig_coords[2], nano_pin_coords["D2"], ACCENT, "STEER")
        sig_wire(sig_coords[5], nano_pin_coords["D3"], ACCENT, "P latch")
        sig_wire(sig_coords[6], nano_pin_coords["D4"], ACCENT, "R / N / D")

        # Power rail. Route ch2 V+ and ch2 GND so they DO NOT pass
        # visually through any other channel's V+ / GND dots.
        #
        # Trick: V+ leaves ch2 going LEFT a short stub (toward the
        # body of the receiver, then drops below all channels in a
        # column to the left of the SIG dots. Then exits the bottom
        # of the receiver and runs right under everything to the Nano.
        # Same for GND but with a slightly different left-stub x so
        # the two power wires don't overlap each other vertically.
        rail_5v_y    = rx_y - 0.25 * inch
        rail_gnd_y   = rx_y - 0.45 * inch
        # Drop columns for the two power wires. Inside the receiver
        # box but to the LEFT of all V+/GND/SIG dots, so they don't
        # visually intersect any pin on the way down.
        drop_x_v     = ch_pin_x - 2 * pin_dx - 0.20 * inch  # left of GND col
        drop_x_g     = ch_pin_x - 2 * pin_dx - 0.35 * inch  # further left

        # 5V wire: V+ pin -> left stub -> drop -> right under rx -> up into 5V
        v_sx, v_sy = sig_coords["V+"]
        n5v_x, n5v_y = nano_pin_coords["5V"]
        c.setStrokeColor(RED); c.setLineWidth(2.0)
        c.line(v_sx, v_sy, drop_x_v, v_sy)              # left stub
        c.line(drop_x_v, v_sy, drop_x_v, rail_5v_y)     # drop
        c.line(drop_x_v, rail_5v_y, n5v_x, rail_5v_y)   # right along rail
        c.line(n5v_x, rail_5v_y, n5v_x, n5v_y)          # up into pin
        c.setFillColor(RED); c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString((drop_x_v + n5v_x) / 2,
                            rail_5v_y + 0.06 * inch, "+5V (red)")

        # GND wire: GND pin -> left stub -> drop -> right under rx -> up into GND
        g_sx, g_sy = sig_coords["GND"]
        ngx, ngy = nano_pin_coords["GND"]
        c.setStrokeColor(HEAD); c.setLineWidth(2.0)
        c.line(g_sx, g_sy, drop_x_g, g_sy)
        c.line(drop_x_g, g_sy, drop_x_g, rail_gnd_y)
        c.line(drop_x_g, rail_gnd_y, ngx, rail_gnd_y)
        c.line(ngx, rail_gnd_y, ngx, ngy)
        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString((drop_x_g + ngx) / 2,
                            rail_gnd_y + 0.06 * inch, "GND (black)")

        # ---- Legend bar (below everything) ----
        leg_y = rx_y - 0.75 * inch
        leg_x = rx_x
        c.setFont("Helvetica-Bold", 8); c.setFillColor(HEAD)
        c.drawString(leg_x, leg_y, "LEGEND")
        c.setFont("Helvetica", 8); c.setFillColor(DIM)
        legend_items = [
            (ACCENT, "signal (white)"),
            (RED,    "+5V (red)"),
            (HEAD,   "GND (black)"),
        ]
        lx = leg_x + 0.70 * inch
        for col, txt in legend_items:
            c.setStrokeColor(col); c.setLineWidth(2.0)
            c.line(lx, leg_y + 0.03 * inch, lx + 0.25 * inch, leg_y + 0.03 * inch)
            c.setFillColor(DIM)
            c.drawString(lx + 0.30 * inch, leg_y, txt)
            lx += 1.50 * inch


class ExpoCurveDiagram(Flowable):
    """Plot the openpilot expo curve: output = 0.4*x^3 + 0.6*x."""

    HEIGHT = 3.2 * inch

    def __init__(self):
        super().__init__()
        self.width = 6.5 * inch
        self.height = self.HEIGHT

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        # Axes
        margin = 0.45 * inch
        plot_x = margin
        plot_y = margin
        plot_w = self.width - 2 * margin
        plot_h = self.height - 2 * margin

        # Frame
        c.setStrokeColor(RULE); c.setLineWidth(0.6)
        c.rect(plot_x, plot_y, plot_w, plot_h, stroke=1, fill=0)

        # Axes through origin
        cx = plot_x + plot_w / 2
        cy = plot_y + plot_h / 2
        c.setStrokeColor(DIM); c.setLineWidth(0.8)
        c.line(plot_x, cy, plot_x + plot_w, cy)
        c.line(cx, plot_y, cx, plot_y + plot_h)

        # Linear reference (dashed)
        c.setStrokeColor(RULE); c.setLineWidth(0.8); c.setDash(2, 2)
        c.line(plot_x, plot_y, plot_x + plot_w, plot_y + plot_h)
        c.setDash()

        # Expo curve (cubic blend) -- plot a polyline through 41 samples
        import math
        c.setStrokeColor(ACCENT); c.setLineWidth(2.0)
        prev = None
        n_samples = 81
        for i in range(n_samples):
            x = -1.0 + 2.0 * i / (n_samples - 1)
            y = 0.4 * x**3 + 0.6 * x
            px = cx + x * (plot_w / 2)
            py = cy + y * (plot_h / 2)
            if prev is not None:
                c.line(prev[0], prev[1], px, py)
            prev = (px, py)

        # Axis labels
        c.setFillColor(HEAD); c.setFont("Helvetica-Bold", 9)
        c.drawString(plot_x + plot_w - 0.65 * inch, cy - 0.18 * inch,
                     "stick x")
        c.drawString(cx + 0.06 * inch, plot_y + plot_h - 0.18 * inch,
                     "angle / 360 deg")
        c.setFont("Helvetica", 7); c.setFillColor(DIM)
        c.drawCentredString(plot_x + plot_w / 2,
                            plot_y - 0.20 * inch,
                            "openpilot expo:  output = 0.4 x^3 + 0.6 x")

        # Tick marks at key stick positions
        c.setFillColor(DIM); c.setFont("Helvetica", 7)
        for sx, sd in [(-1.0, "-360"), (-0.5, "-126"), (0.0, "0"),
                       (+0.5, "+126"), (+1.0, "+360")]:
            sy = 0.4 * sx**3 + 0.6 * sx
            px = cx + sx * (plot_w / 2)
            py = cy + sy * (plot_h / 2)
            c.setFillColor(ACCENT)
            c.circle(px, py, 0.04 * inch, stroke=0, fill=1)
            c.setFillColor(DIM)
            c.drawCentredString(px, cy - 0.30 * inch, f"{sx:+.1f}")
            c.drawString(cx + 0.05 * inch, py - 0.05 * inch, sd)


# ============================================================================
# Build the document
# ============================================================================

def heading(text, size=14, color=HEAD, space_before=0.20, space_after=0.10):
    style = ParagraphStyle(
        f"H_{text[:10]}",
        fontName="Helvetica-Bold",
        fontSize=size,
        textColor=color,
        spaceBefore=space_before * inch,
        spaceAfter=space_after * inch,
        leading=size * 1.2,
    )
    return Paragraph(text, style)


def body(text):
    style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9.5,
        textColor=INK,
        leading=12,
        spaceAfter=0.05 * inch,
    )
    return Paragraph(text, style)


def code_block(text):
    style = ParagraphStyle(
        "Code",
        fontName="Courier",
        fontSize=8.5,
        textColor=INK,
        leading=11,
        spaceBefore=0.03 * inch,
        spaceAfter=0.05 * inch,
        backColor=PANEL,
        borderColor=RULE,
        borderWidth=0.5,
        borderPadding=4,
        leftIndent=0.05 * inch,
    )
    return Paragraph(text.replace("\n", "<br/>"), style)


def tbl(rows, col_widths=None):
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    style = TableStyle([
        ("FONT",       (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT",       (0, 1), (-1, -1), "Helvetica", 9),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("BACKGROUND", (0, 0), (-1, 0), HEAD),
        ("TEXTCOLOR",  (0, 1), (-1, -1), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL]),
        ("ALIGN",      (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",(0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LINEBELOW",  (0, 0), (-1, 0), 0.5, RULE),
    ])
    t.setStyle(style)
    return t


def callout(title, text, color=ACCENT):
    inner = [
        Paragraph(f"<b>{title}</b>",
                  ParagraphStyle("co_t", fontName="Helvetica-Bold",
                                 fontSize=9, textColor=color)),
        Paragraph(text,
                  ParagraphStyle("co_b", fontName="Helvetica",
                                 fontSize=9, textColor=INK, leading=12)),
    ]
    t = Table([[inner]], colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 1, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def build():
    deco = PageDeco()
    doc = SimpleDocTemplate(
        OUT_PATH, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.85 * inch, bottomMargin=0.70 * inch,
        title="RC Implementation Guide",
        author="Derek Nagel + Claude",
    )

    story = []

    # ---- Title ----
    title_style = ParagraphStyle(
        "Title", fontName="Helvetica-Bold", fontSize=22,
        textColor=HEAD, alignment=TA_LEFT,
        leading=26, spaceAfter=0.06 * inch,
    )
    story.append(Paragraph("RC Implementation Guide", title_style))
    sub_style = ParagraphStyle(
        "Sub", fontName="Helvetica", fontSize=11,
        textColor=DIM, alignment=TA_LEFT,
        leading=13, spaceAfter=0.18 * inch,
    )
    story.append(Paragraph(
        f"v5.0.0-rc2 &nbsp;·&nbsp; "
        f"Spektrum DX8 → AR6200 → Arduino Nano → Tesla rack &nbsp;·&nbsp; "
        f"{datetime.now().strftime('%d %B %Y')}",
        sub_style))

    story.append(SystemBlockDiagram())

    # ---- Overview ----
    story.append(heading("1. What v5 does"))
    story.append(body(
        "v5 keeps the v4.3.3 program (<i>tesla_control.py</i>) "
        "exactly as it was. It adds a sibling program "
        "<i>tesla_control_rc.py</i> and an Arduino Nano firmware "
        "(<i>arduino/tesla_rc_bridge/</i>) that lets you steer the "
        "Tesla rack from a Spektrum DX8 transmitter. Inside the "
        "laptop, the RC variant subclasses the v4.3.3 program and "
        "imports the existing CAN worker, all safety guards, and the "
        "session logger verbatim --the wire-level protocol is "
        "unchanged."))
    story.append(body(
        "<b>Steering math follows openpilot's "
        "<i>tools/joystick/joystickd.py</i> pattern</b>: runtime min/max "
        "calibration of the stick endpoints, a 3% normalized deadband, "
        "and a cubic-blend expo curve (<i>0.4·x³ + 0.6·x</i>). This is "
        "the same shape commaai ships in production for joystick "
        "control. Result: small stick movements give small wheel "
        "movements (for parking-lot corrections), large movements "
        "reach full lock-to-lock (±360°)."))

    story.append(heading("2. Hardware list"))
    story.append(tbl([
        ["Item",                                   "Purpose",                     "Source"],
        ["Spektrum DX8 transmitter (any gen)",     "Operator radio",              "owned"],
        ["Spektrum AR6200 receiver (SPMAR6200)",   "Receives DSMX, emits 6 PWM",  "owned"],
        ["Arduino Nano (ATmega328P)",              "PWM → USB serial bridge",     "bench supply"],
        ["3× servo lead wires + 2× jumpers",       "Rx → Nano",                   "bench supply"],
        ["Mini-USB cable",                         "Nano → laptop",               "bench supply"],
        ["SYS TEC USB-CANmodul1 (model 3204001)",  "Laptop → car CAN",            "unchanged from v4"],
    ], col_widths=[2.8 * inch, 2.6 * inch, 1.6 * inch]))

    story.append(heading("3. Binding the AR6200 to the DX8"))
    story.append(body(
        "DX8 transmits DSMX with DSM2 fallback. AR6200 is a DSM2 "
        "aircraft receiver. They bind. Reference: "
        "<i>Spektrum AR6200 user guide</i>, PDF at "
        "<font color='#1e6fd9'>spektrumrc.com/ProdInfo/Files/SPMAR6200.pdf</font>."))
    story.append(tbl([
        ["Step", "Action"],
        ["1",    "Insert the bind plug into the AR6200's BIND/DATA port."],
        ["2",    "Power the AR6200 (any servo port: GND + 5V is enough)."],
        ["3",    "The receiver LED flashes rapidly while in bind mode."],
        ["4",    "On the DX8, hold the trainer / bind switch while powering on."],
        ["5",    "Within a few seconds the AR6200 LED goes solid -- bound."],
        ["6",    "Power-cycle the AR6200, remove the bind plug. Future power-ups auto-link."],
    ], col_widths=[0.50 * inch, 6.5 * inch]))

    story.append(callout(
        "If the LED keeps flashing past 30 s",
        "The DX8 isn't in bind mode or the receiver isn't seeing it. "
        "Move closer, check antenna routing, retry. A re-bind never "
        "harms a receiver -- you can do it as many times as needed.",
        YELLOW))

    story.append(PageBreak())

    # ---- Wiring page ----
    story.append(heading("4. Wiring: AR6200 → Arduino Nano"))
    story.append(body(
        "Only three channels are wired into the Nano: <b>2 (AILE)</b> "
        "for steering, <b>5 (GEAR)</b> for the P latch, and <b>6 "
        "(AUX1)</b> for the R/N/D selector. The receiver is powered "
        "from the Nano's 5V regulated rail through channel 2's "
        "positive lead; channels 5 and 6 only need their signal wires."))

    story.append(PinoutDiagram())

    story.append(heading("5. Pin-by-pin table", size=11))
    story.append(tbl([
        ["AR6200 channel & pin", "Wire color (servo lead)", "Goes to Nano pin", "Carries"],
        ["ch2 SIG (innermost)",  "white / orange",          "D2 (PCINT18)",     "Steering PWM"],
        ["ch2 V+  (middle)",     "red",                     "5V",               "Power to Rx"],
        ["ch2 GND (outermost)",  "black / brown",           "GND",              "Common ground"],
        ["ch5 SIG (innermost)",  "white / orange",          "D3 (PCINT19)",     "P-latch PWM"],
        ["ch6 SIG (innermost)",  "white / orange",          "D4 (PCINT20)",     "R/N/D PWM"],
    ], col_widths=[1.85 * inch, 1.8 * inch, 1.45 * inch, 1.7 * inch]))

    story.append(callout(
        "Channels 5 and 6 share power",
        "Once channel 2 is wired up, the AR6200's internal rails "
        "energize every servo port. Channels 5 and 6 therefore only "
        "need their signal wires connected to the Nano. Tie a single "
        "GND between the receiver and the Nano, not three.",
        ACCENT))

    story.append(callout(
        "Do not double-power the AR6200",
        "If the AR6200 is also connected to a separate battery (e.g. "
        "an ESC's BEC), DO NOT connect 5V from the Nano too. Tie "
        "grounds together, leave the V+ pin to the Nano "
        "disconnected. Otherwise you back-feed two regulators "
        "against each other.",
        RED))

    story.append(PageBreak())

    # ---- Steering feel page ----
    story.append(heading("6. Steering feel (expo curve)"))
    story.append(body(
        "The stick-to-angle mapping uses openpilot's exact cubic-blend "
        "expo from <i>tools/joystick/joystickd.py</i>. The shape is "
        "<b>linear-ish near center</b>, where you make small "
        "corrections, and <b>more aggressive near full deflection</b>, "
        "where you do parking maneuvers. Full stick travel reaches "
        "exactly ±HARD_ANGLE_LIMIT_DEG (±360° in v4.3.x)."))

    story.append(ExpoCurveDiagram())

    story.append(heading("Stick travel → wheel angle, full table", size=11))
    expo_rows = [["Stick position", "Normalized x", "Wheel angle"]]
    for x in [-1.0, -0.75, -0.50, -0.25, -0.10, -0.05,
              0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 1.00]:
        y = 0.4 * x ** 3 + 0.6 * x
        deg = y * 360.0
        label = (
            "full left" if x == -1.0 else
            "full right" if x == 1.0 else
            f"{abs(x)*100:.0f}% {'left' if x<0 else 'right'}"
            if x != 0 else "centered"
        )
        expo_rows.append([label, f"{x:+.2f}", f"{deg:+7.1f}°"])
    story.append(tbl(expo_rows, col_widths=[2.0 * inch, 1.4 * inch, 1.6 * inch]))

    story.append(callout(
        "Why expo and not linear",
        "Linear mapping wastes resolution at the center (small stick "
        "movements = noticeable wheel jumps) AND makes full lock feel "
        "twitchy. Expo gives you fine control where you spend 95% of "
        "your driving time, and reserves the last 25% of stick travel "
        "for the times you really need to crank the wheel.",
        GREEN))

    story.append(PageBreak())

    # ---- Channel mapping ----
    story.append(heading("7. PRND switch mapping (AUX1 + GEAR)"))
    story.append(body(
        "<b>AUX1 (channel 6)</b> is a 3-position switch on the DX8. The "
        "program reads the PWM width and selects R / N / D using these "
        "hysteresis bands:"))
    story.append(tbl([
        ["PWM width (us)", "Gear"],
        ["< 1250",         "R (reverse)"],
        ["1250 – 1750",    "N (neutral)"],
        ["> 1750",         "D (drive)"],
    ], col_widths=[1.6 * inch, 2.0 * inch]))
    story.append(body(
        "A shift is dispatched only when the switch position "
        "<b>changes</b> -- holding the switch in D does not "
        "continuously fire shift requests. The existing v4.3.3 "
        "non-blocking 200 Hz shift burst handles the SBW_RQ_SCCM "
        "transmission unchanged."))

    story.append(body("&nbsp;"))

    story.append(body(
        "<b>GEAR switch (channel 5)</b> is a 2-position toggle. Holding "
        "it past PWM 1750 us for 200 ms requests a shift to <b>P</b>. "
        "A 1-second cooldown prevents double-fire. This matches how "
        "Tesla actually shifts to Park --via the stalk button, "
        "not the stalk paddle."))

    # ---- Flashing the Nano ----
    story.append(heading("8. Flashing the Arduino Nano"))
    story.append(body(
        "Install Arduino CLI from <font color='#1e6fd9'>"
        "arduino.github.io/arduino-cli/installation</font>, then:"))
    story.append(code_block(
        "cd arduino/tesla_rc_bridge\n"
        "arduino-cli core install arduino:avr\n"
        "arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 .\n"
        "arduino-cli upload  --fqbn arduino:avr:nano:cpu=atmega328 -p <PORT> ."))
    story.append(body(
        "Many Chinese-clone Nanos ship with the <b>old bootloader</b>. "
        "If upload fails with avrdude timeout, change the fqbn to "
        "<i>arduino:avr:nano:cpu=atmega328old</i>."))

    story.append(heading("Finding the serial port", size=11))
    story.append(tbl([
        ["OS",      "Where to look"],
        ["Windows", "Device Manager → Ports (COM & LPT). 'USB Serial Device (COMx)' or 'CH340'."],
        ["macOS",   "ls /dev/cu.usbserial-* /dev/cu.usbmodem*"],
        ["Linux",   "dmesg | tail -20 after plug-in. Usually /dev/ttyUSB0 or /dev/ttyACM0."],
    ], col_widths=[0.9 * inch, 6.1 * inch]))

    story.append(PageBreak())

    # ---- Running the program ----
    story.append(heading("9. Running the program"))
    story.append(body(
        "Once the Nano is flashed and wired, the DX8 is bound, and "
        "the SYS TEC USB-CAN is plugged into both the laptop and the "
        "car's chassis CAN tap, run:"))
    story.append(code_block(
        "python tesla_control_rc.py --rc-port COM5\n"
        "# macOS:\n"
        "python tesla_control_rc.py --rc-port /dev/cu.usbserial-XXX"))
    story.append(body(
        "The GUI is identical to v4.3.3 plus a new <b>RC INPUT</b> "
        "strip near the top showing the live channel widths, the "
        "auto-calibrated stick range, current frame count, and the "
        "currently selected gear."))
    story.append(body(
        "<b>Calibration</b> happens automatically. The first time "
        "you sweep the right stick fully left and right, the program "
        "records the actual endpoints and uses them from then on. "
        "Until that happens, the boot-default 1100..1900 us range is "
        "used (which works fine even uncalibrated -- calibration just "
        "tightens up the mapping for asymmetric trim)."))

    story.append(heading("Standard operating sequence", size=11))
    story.append(tbl([
        ["#", "Action"],
        ["1", "Power DX8, power AR6200, plug Nano into laptop."],
        ["2", "Plug SYS TEC into laptop USB and into the car's chassis CAN tap."],
        ["3", "python tesla_control_rc.py --rc-port <PORT>"],
        ["4", "In the GUI, click CONNECT. Confirm the bus diagnostic panel populates."],
        ["5", "Sweep the right stick fully left and right once to seed calibration."],
        ["6", "Verify the RC INPUT panel shows STEER us tracking the stick."],
        ["7", "Click ENGAGE. EAC transitions INHIBITED → AVAILABLE → ACTIVE."],
        ["8", "Steer with the right stick. Aux1 switch changes R/N/D. Gear switch held = P."],
        ["9", "ESC / Q / E-STOP button / close window = disengage."],
    ], col_widths=[0.30 * inch, 6.7 * inch]))

    story.append(callout(
        "Safety carries over from v4.3.3",
        "Hard angle clamp at ±360°. Rate limit on the worker side at "
        "150°/s. RX-timeout watchdog (500 ms with no 0x370 → E-STOP). "
        "EAC-bounce watchdog (>5 transitions/s → E-STOP). Real-motion "
        "auto-disengage when DI_vehicleSpeed > 1 mph. Park-to-engage "
        "gate. All of these still apply.",
        GREEN))

    story.append(PageBreak())

    # ---- Troubleshooting ----
    story.append(heading("10. Troubleshooting"))
    story.append(tbl([
        ["Symptom",                                       "Likely cause",                  "Fix"],
        ["RC port FAILED to open",                        "Wrong port / driver missing",   "Re-check Device Manager. CH340 driver if clone Nano."],
        ["STEER us stays at 0",                           "White wire not on D2, or AR6200 not bound", "Re-bind AR6200, re-check wiring against Section 4"],
        ["STEER us frozen at 1500",                       "TX off, receiver holds last",   "Power DX8 on. Spektrum holds last value on signal loss."],
        ["RND switch wobbles between R and N",            "Switch sits near a hysteresis edge", "Increase EPA on AUX1 on the DX8 to push endpoints out"],
        ["Shifts spam the log",                           "PWM noise on AUX1",             "Increase hysteresis bands in tesla_control_rc.py"],
        ["Stick travel doesn't reach ±360 deg",           "Calibration sweep not done",    "Push the stick fully left, then fully right, once"],
        ["Wheel jitters at center",                       "Dead band too tight for your stick", "Increase RC_DEADBAND_NORM from 0.03 to 0.05"],
        ["Wheel won't move past ~60 deg",                 "Rack is in MIN_SPEED gating",   "Enable 30 MPH MODE in the GUI (jacked-up only)"],
    ], col_widths=[2.0 * inch, 1.9 * inch, 3.1 * inch]))

    story.append(heading("11. What v5 is NOT", size=12))
    story.append(body(
        "Throttle, brake, and longitudinal control are NOT in v5. The "
        "pre-AP 2013 Model S has no CAN-commandable throttle and no "
        "iBooster -- adding those is the v6 scope (a pedal interceptor "
        "is required). The v5 RC bridge is steering-and-gear only."))
    story.append(body(
        "v5 also does not replace the keyboard or slider modes. "
        "tesla_control.py v4.3.3 still runs exactly as before. v5 is "
        "an additional way to drive the same rack, not a replacement."))

    story.append(heading("12. References", size=12))
    story.append(body(
        "openpilot tools/joystick: "
        "<font color='#1e6fd9'>github.com/commaai/openpilot/blob/master/tools/joystick/joystickd.py</font><br/>"
        "Spektrum AR6200 manual: "
        "<font color='#1e6fd9'>spektrumrc.com/ProdInfo/Files/SPMAR6200.pdf</font><br/>"
        "Spektrum DX8 Gen 2 product page: "
        "<font color='#1e6fd9'>spektrumrc.com/product/dx8-8-channel-dsmx-transmitter-only-gen-2/SPMR8000.html</font><br/>"
        "Consistent Overhead Byte Stuffing (Cheshire &amp; Baker, 1999): "
        "<font color='#1e6fd9'>en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing</font><br/>"
        "RCArduino multi-channel PWM read: "
        "<font color='#1e6fd9'>rcarduino.blogspot.com/2012/04/how-to-read-multiple-rc-channels-draft.html</font><br/>"
        "gregjhogan pre-AP EPAS patch: "
        "<font color='#1e6fd9'>github.com/gregjhogan/tesla-pre-ap-epas-patch</font>"))

    doc.build(story, onFirstPage=deco.draw, onLaterPages=deco.draw)
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    sz = os.path.getsize(path)
    print(f"Built: {path}  ({sz} bytes)")
