"""
Generate RC_IMPLEMENTATION_GUIDE_SLT3.pdf -- the printable companion
to the v5.1.0 RC bridge for the Spektrum SLT3 + SR315 combination.

Matches the visual style of ROADMAP.pdf (same palette, same page
template, same flowable patterns). All diagrams are drawn
programmatically -- no fabricated photographs.

Run:   python docs/build/build_rc_guide_slt3.py
Out:   docs/build/RC_IMPLEMENTATION_GUIDE_SLT3.pdf
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
OUT_PATH = os.path.join(HERE, "RC_IMPLEMENTATION_GUIDE_SLT3.pdf")

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
    def __init__(self, title="Tesla Rack Control · RC Implementation Guide (SLT3 + SR315)"):
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
        canvas.drawRightString(7.75 * inch, 10.55 * inch, "v5.1.0")
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
            ("SLT3",             "wheel + trigger\nSLT FHSS",        ACCENT),
            ("SR315",            "surface receiver\nDSMR/SLT 3 ch",  ACCENT),
            ("Arduino\nNano",    "PCINT reader\nCOBS @ 100 Hz",      GREEN),
            ("Laptop",           "tesla_control_rc.py\nv5.1",        GREEN),
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
                            "Spektrum SR315")
        c.setFillColor(DIM); c.setFont("Helvetica", 7.5)
        c.drawCentredString(rx_x + rx_w / 2, rx_y + rx_h - 0.42 * inch,
                            "(SPMSR315)")

        # Channel rows. SR315 has 3 channels: STR, THR, AUX1. All used.
        # Spread them more vertically since there are only 3.
        ch_top_y    = rx_y + rx_h - 0.95 * inch
        ch_pitch_y  = 1.00 * inch
        ch_label_x  = rx_x + 0.15 * inch
        ch_pin_x    = rx_x + rx_w - 0.45 * inch     # x of the SIG pin
        pin_dx      = 0.13 * inch

        sig_coords = {}
        # ch_id maps to (label, key for sig_coords). For the routing
        # logic below we need to remember which SR315 channel is the
        # steering channel (we use it for power+GND too).
        for i, (ch_id, label) in enumerate([
                (1, "ch1 STR  (wheel)"),
                (2, "ch2 THR  (trigger)"),
                (3, "ch3 AUX1 (rocker)"),
        ]):
            y = ch_top_y - i * ch_pitch_y
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(HEAD)
            c.drawString(ch_label_x, y - 0.04 * inch, label)

            for j, role in enumerate(["GND", "V+", "SIG"]):
                px = ch_pin_x - (2 - j) * pin_dx
                c.setFillColor({"GND": HEAD, "V+": RED, "SIG": ACCENT}[role])
                c.circle(px, y, 0.045 * inch, stroke=0, fill=1)
                if role == "SIG":
                    sig_coords[ch_id] = (px, y)
                # Use ch1 (STR) as the source of power/ground -- same
                # convention as the AR6200 variant. SR315 has internal
                # rails so the other channels don't need their own
                # power wires.
                if role == "V+" and ch_id == 1:
                    sig_coords["V+"] = (px, y)
                if role == "GND" and ch_id == 1:
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

        sig_wire(sig_coords[1], nano_pin_coords["D2"], ACCENT, "STEER")
        sig_wire(sig_coords[2], nano_pin_coords["D3"], ACCENT, "P (trigger)")
        sig_wire(sig_coords[3], nano_pin_coords["D4"], ACCENT, "R / N / D")

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
    story.append(Paragraph("RC Implementation Guide (SLT3)", title_style))
    sub_style = ParagraphStyle(
        "Sub", fontName="Helvetica", fontSize=11,
        textColor=DIM, alignment=TA_LEFT,
        leading=13, spaceAfter=0.18 * inch,
    )
    story.append(Paragraph(
        f"v5.1.0 &nbsp;·&nbsp; "
        f"Spektrum SLT3 → SR315 → Arduino Nano → Tesla rack &nbsp;·&nbsp; "
        f"{datetime.now().strftime('%d %B %Y')}",
        sub_style))

    story.append(SystemBlockDiagram())

    # ---- Overview ----
    story.append(heading("1. What v5.1 (SLT3) does"))
    story.append(body(
        "v5.1 is the SLT3 variant of the v5 RC bridge. The plane "
        "sticks of the DX8 are replaced by a Spektrum <b>SLT3 wheel "
        "and trigger surface transmitter</b> bound to a <b>SR315 "
        "dual-protocol surface receiver</b>. Steering is on the "
        "wheel; the trigger fires the P button when pushed forward "
        "and held; the AUX rocker selects R / N / D. The Arduino "
        "bridge, the Python program, the CAN protocol, and "
        "v4.3.3's safety architecture are all unchanged."))
    story.append(body(
        "<b>Steering math is openpilot's "
        "<i>tools/joystick/joystickd.py</i> pattern</b>: runtime min/max "
        "calibration of the wheel endpoints, a 3% normalized deadband, "
        "and a cubic-blend expo curve (<i>0.4·x³ + 0.6·x</i>). This is "
        "the same shape commaai ships in production for joystick "
        "control. Result: small wheel movements give small Tesla-wheel "
        "movements (for parking-lot corrections), full wheel rotation "
        "reaches full lock-to-lock (±360°)."))

    story.append(heading("2. Hardware list"))
    story.append(tbl([
        ["Item",                                       "Purpose",                       "Source"],
        ["Spektrum SLT3 transmitter (SPMSLT300)",      "Operator radio (wheel/trigger)","owned"],
        ["Spektrum SR315 receiver (SPMSR315)",         "Receives SLT, emits 3 PWM",     "owned"],
        ["Arduino Nano (ATmega328P)",                  "PWM → USB serial bridge",       "bench supply"],
        ["3× servo lead wires + 2× jumpers",           "Rx → Nano",                     "bench supply"],
        ["Mini-USB cable",                             "Nano → laptop",                 "bench supply"],
        ["SYS TEC USB-CANmodul1 (model 3204001)",      "Laptop → car CAN",              "unchanged from v4"],
    ], col_widths=[2.8 * inch, 2.6 * inch, 1.6 * inch]))

    story.append(heading("3. Binding the SR315 to the SLT3"))
    story.append(body(
        "SR315 uses a <b>bind button</b> (not a bind plug). SLT3 "
        "transmits SLT FHSS only; SR315 supports both DSMR and SLT "
        "and auto-detects which protocol the transmitter is using. "
        "References: SR315 SLT Bind slip sheet "
        "(<font color='#1e6fd9'>horizonhobby.com/.../SPMSR315-Slip_Sheet.pdf</font>) "
        "and SLT3 user guide "
        "(<font color='#1e6fd9'>horizonhobby.com/.../SPMSLT300-manual-en.pdf</font>)."))
    story.append(tbl([
        ["Step", "Action"],
        ["1",    "Power the SR315 (any servo port: GND + 5V is enough)."],
        ["2",    "Press the SR315 bind button THREE TIMES quickly (within 1.5 s)."],
        ["3",    "The receiver LED begins flashing with a pause pattern (bind mode)."],
        ["4",    "Hold the SLT3 wheel CENTERED, trigger AT REST, AUX1 rocker CENTERED."],
        ["5",    "Power on the SLT3. Both LEDs go solid -- bound. Takes ~2 seconds."],
    ], col_widths=[0.50 * inch, 6.5 * inch]))

    story.append(callout(
        "Failsafe positions are captured at bind time",
        "Whatever positions the wheel / trigger / AUX1 are in when "
        "the SLT3 powers on become the receiver's failsafe values. "
        "Bind with the wheel centered, trigger at rest center, and "
        "AUX1 in N. If you later reverse a channel or change the "
        "physical orientation of a control, re-bind.",
        ORANGE))

    story.append(callout(
        "If the LEDs don't go solid",
        "The SR315 may need a firmware update to SLT mode if it was "
        "purchased standalone. The one bundled with the SLT3 ships "
        "SLT-ready. Re-press the bind button three times, retry. "
        "A re-bind never harms either device.",
        YELLOW))

    story.append(PageBreak())

    # ---- Wiring page ----
    story.append(heading("4. Wiring: SR315 → Arduino Nano"))
    story.append(body(
        "All three SR315 channels are wired into the Nano: <b>ch1 STR</b> "
        "for the wheel, <b>ch2 THR</b> for the trigger (P button "
        "gesture), and <b>ch3 AUX1</b> for the R/N/D rocker. The "
        "receiver is powered from the Nano's 5V regulated rail "
        "through ch1's positive lead; ch2 and ch3 only need their "
        "signal wires connected. SR315's internal rails distribute "
        "power across all three servo ports once any one is energized."))

    story.append(PinoutDiagram())

    story.append(heading("5. Pin-by-pin table", size=11))
    story.append(tbl([
        ["SR315 channel & pin",  "Wire color (servo lead)", "Goes to Nano pin", "Carries"],
        ["ch1 STR  SIG",         "white / orange",          "D2 (PCINT18)",     "Wheel PWM (steering)"],
        ["ch1 STR  V+",          "red",                     "5V",               "Power to Rx"],
        ["ch1 STR  GND",         "black / brown",           "GND",              "Common ground"],
        ["ch2 THR  SIG",         "white / orange",          "D3 (PCINT19)",     "Trigger PWM (P button)"],
        ["ch3 AUX1 SIG",         "white / orange",          "D4 (PCINT20)",     "Rocker PWM (R/N/D)"],
    ], col_widths=[1.85 * inch, 1.8 * inch, 1.45 * inch, 1.9 * inch]))

    story.append(callout(
        "ch2 and ch3 share power with ch1",
        "Once ch1 is wired up, SR315's internal rails energize every "
        "servo port. ch2 (trigger) and ch3 (AUX1) therefore only "
        "need their signal wires connected to the Nano. Tie a single "
        "GND between the SR315 and the Nano, not three.",
        ACCENT))

    story.append(callout(
        "Do not double-power the SR315",
        "If the SR315 is also connected to a separate battery (e.g. "
        "the bench BEC), DO NOT connect 5V from the Nano too. Tie "
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
    story.append(heading("7. PRND mapping (AUX1 rocker + trigger)"))
    story.append(body(
        "<b>AUX1 rocker (SR315 ch3)</b> on the SLT3 is a 3-position "
        "switch. The program reads the PWM width and selects D / N / R "
        "using these hysteresis bands. Rocker LOW selects drive, "
        "center is neutral, rocker HIGH selects reverse."))
    story.append(tbl([
        ["PWM width (us)", "AUX1 position",  "Gear"],
        ["< 1250",         "rocker LOW",     "D (drive)"],
        ["1250 to 1750",   "rocker CENTER",  "N (neutral)"],
        ["> 1750",         "rocker HIGH",    "R (reverse)"],
    ], col_widths=[1.4 * inch, 1.6 * inch, 2.0 * inch]))
    story.append(body(
        "A shift is dispatched only when the switch position "
        "<b>changes</b>: holding the switch in D does not continuously "
        "fire shift requests. The existing v4.3.3 non-blocking 200 Hz "
        "shift burst handles the SBW_RQ_SCCM transmission unchanged."))

    story.append(body("&nbsp;"))

    story.append(body(
        "<b>Trigger (SR315 ch2)</b> is the spring-return throttle "
        "trigger on the SLT3. At rest it sits near center (~1500 us). "
        "<b>Pushing the trigger FORWARD (full brake direction) drops "
        "the PWM toward 1000 us and counts as the P button being "
        "pressed</b>. Hold the trigger fully forward for 200 ms to "
        "request a shift to P. The trigger springs back to center on "
        "release; a 1-second cooldown prevents double-fire."))
    story.append(tbl([
        ["Trigger PWM (us)", "Position",            "Meaning"],
        ["<= 1250",          "full forward (brake)", "P button PRESSED"],
        ["1250 to 1500",     "deadband",             "transitioning"],
        ["> 1500",           "at rest or pulled",    "P button RELEASED"],
    ], col_widths=[1.4 * inch, 1.7 * inch, 2.0 * inch]))

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
        "Once the Nano is flashed and wired, the SLT3 is bound to "
        "the SR315, and the SYS TEC USB-CAN is plugged into both the "
        "laptop and the car's chassis CAN tap, run:"))
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
        ["1", "Power SLT3, power SR315, plug Nano into laptop."],
        ["2", "Plug SYS TEC into laptop USB and into the car's chassis CAN tap."],
        ["3", "python tesla_control_rc.py --rc-port <PORT>"],
        ["4", "In the GUI, click CONNECT. Confirm the bus diagnostic panel populates."],
        ["5", "Sweep the SLT3 wheel fully left and right once to seed calibration."],
        ["6", "Verify the RC INPUT panel shows STEER us tracking the wheel."],
        ["7", "Click ENGAGE. EAC transitions INHIBITED → AVAILABLE → ACTIVE."],
        ["8", "Steer with the wheel. AUX1 rocker picks D/N/R. Trigger pushed forward and held = P."],
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

    # ---- Signal-loss detection ----
    story.append(heading("10. Signal-loss detection"))
    story.append(body(
        "Spektrum receivers <b>hold the last value</b> on transmitter "
        "power-off (SmartSafe). The SR315 keeps emitting whatever "
        "PWM widths it last decoded, the Arduino keeps framing them, "
        "and the laptop keeps reading them. Without explicit "
        "detection, a dead SLT3 looks identical to a stationary "
        "wheel. v5 surfaces this in two ways:"))
    story.append(tbl([
        ["Indicator",     "Trigger",                                       "What it means"],
        ["NO SERIAL",     "No COBS frame for > 200 ms",                    "Arduino died, USB stalled, or cable unplugged"],
        ["TX LOST",       "Aileron PWM unchanged > 2 us for > 3 s",        "Spektrum holding last value; TX off / out of range"],
        ["LIVE (green)",  "Frames arriving, stick changing",               "Normal operation"],
    ], col_widths=[1.1 * inch, 2.7 * inch, 3.2 * inch]))

    story.append(body(
        "<b>The SIGNAL pill</b> in the RC INPUT panel shows the current "
        "state at all times. By itself the indicator does not interrupt "
        "operation -- you decide whether to E-STOP. For unattended "
        "or in-car testing, enable the <b>auto-disengage on signal "
        "loss</b> checkbox in the same panel. When checked, the "
        "program drops <i>ctrl.engaged</i> on the next UI tick if "
        "either SIGNAL condition fires. This is not an E-STOP -- "
        "you can re-engage once signal returns -- but it stops the "
        "rack from continuing to track a stale target."))

    story.append(callout(
        "Why not auto-disengage by default",
        "On a bench setup with a flaky USB cable or a laptop that "
        "stutters its USB hub, the program would re-disengage every "
        "few seconds, which is more annoying than helpful. The "
        "checkbox lets you flip it on once the bench setup is known-"
        "good and you're moving to in-car testing where the "
        "consequence of a stuck stick matters more.",
        ACCENT))

    story.append(callout(
        "TX LOST is a heuristic, not proof",
        "If you legitimately hold the stick perfectly still for 3 "
        "seconds, you'll see TX LOST. That's expected -- 3 seconds of "
        "perfect stillness is unusual on a real RC operator's stick. "
        "If you're driving slow and steady and trip the indicator, "
        "raise RC_FROZEN_STICK_TIMEOUT_S in the source.",
        YELLOW))

    story.append(PageBreak())

    # ---- Troubleshooting ----
    story.append(heading("11. Troubleshooting"))
    story.append(tbl([
        ["Symptom",                                       "Likely cause",                  "Fix"],
        ["RC port FAILED to open",                        "Wrong port / driver missing",   "Re-check Device Manager. CH340 driver if clone Nano."],
        ["STEER us stays at 0",                           "White wire not on D2, or SR315 not bound", "Re-bind SR315 to SLT3, re-check wiring against Section 4"],
        ["STEER us frozen at 1500",                       "TX off, receiver holds last",   "Power SLT3 on. Spektrum holds last value on signal loss."],
        ["AUX1 wobbles between R and N",                  "Rocker sits near a hysteresis edge", "Adjust AUX1 EPA on the SLT3 to push endpoints further out"],
        ["Shifts spam the log",                           "PWM noise on AUX1",             "Increase hysteresis bands in tesla_control_rc.py"],
        ["Wheel travel doesn't reach ±360 deg",           "Calibration sweep not done",    "Sweep the SLT3 wheel fully left, then fully right, once"],
        ["Wheel jitters at center",                       "Dead band too tight for your wheel", "Increase RC_DEADBAND_NORM from 0.03 to 0.05"],
        ["Wheel won't move past ~60 deg",                 "Rack is in MIN_SPEED gating",   "Enable 30 MPH MODE in the GUI (jacked-up only)"],
        ["Trigger fires P at rest",                       "Trigger center is below 1250 us at rest", "Raise RC_P_PRESS_THRESH_US or adjust SLT3 trigger trim"],
        ["SIGNAL pill shows TX LOST when wheel is still", "Holding wheel perfectly still > 3 s", "Normal heuristic; raise RC_FROZEN_STICK_TIMEOUT_S if too sensitive"],
        ["SIGNAL pill shows NO SERIAL intermittently",    "USB cable noise or hub power dip", "Plug Nano directly into laptop USB, not through a hub"],
    ], col_widths=[2.0 * inch, 1.9 * inch, 3.1 * inch]))

    story.append(heading("12. What v5 is NOT", size=12))
    story.append(body(
        "Throttle, brake, and longitudinal control are NOT in v5. The "
        "pre-AP 2013 Model S has no CAN-commandable throttle and no "
        "iBooster -- adding those is the v6 scope (a pedal interceptor "
        "is required). The v5 RC bridge is steering-and-gear only."))
    story.append(body(
        "v5 also does not replace the keyboard or slider modes. "
        "tesla_control.py v4.3.3 still runs exactly as before. v5 is "
        "an additional way to drive the same rack, not a replacement."))

    story.append(heading("13. References", size=12))
    story.append(body(
        "openpilot tools/joystick: "
        "<font color='#1e6fd9'>github.com/commaai/openpilot/blob/master/tools/joystick/joystickd.py</font><br/>"
        "Spektrum SR315 product page: "
        "<font color='#1e6fd9'>spektrumrc.com/product/sr315-3-channel-dsmr-slt-receiver/SPMSR315.html</font><br/>"
        "Spektrum SR315 SLT bind slip sheet: "
        "<font color='#1e6fd9'>horizonhobby.com/.../SPMSR315-Slip_Sheet.pdf</font><br/>"
        "Spektrum SLT3 product page (SPMSLT300 bundle): "
        "<font color='#1e6fd9'>spektrumrc.com/product/slt3-3-channel-transmitter-with-sr315-receiver/SPMSLT300.html</font><br/>"
        "Spektrum SLT3 user guide: "
        "<font color='#1e6fd9'>horizonhobby.com/.../SPMSLT300-manual-en.pdf</font><br/>"
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
