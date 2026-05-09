"""
Prepare a steering-wheel image for tesla_control.py's WheelCanvas.

Use this when you have a photo of a steering wheel against a mostly
white (or light) background and you want to drop it into the GUI as
a rotating wheel.

USAGE
    python tools/prepare_wheel.py PATH/TO/SOURCE_IMAGE
    python tools/prepare_wheel.py                       (looks in assets/)

WHAT IT DOES
    - Loads the source image (JPG or PNG).
    - Treats near-white pixels as transparent (background removal by
      threshold). Default threshold is 240/255 per channel.
    - Crops to the non-transparent bounding box.
    - Writes the result to assets/wheel.png with an RGBA alpha channel.

NOTES
    - The threshold is intentionally simple. If your source has
      shadows or a colored backdrop, lower the threshold with
      `--threshold 220` or use a real bg-removal tool (remove.bg,
      Photopea) and drop the resulting transparent PNG straight into
      assets/wheel.png yourself.
    - The image is centered and rotated by the GUI; you don't have
      to align the wheel to a specific orientation, but a "wheel
      sitting straight, logo at top" source looks the most natural
      at 0 degrees commanded angle.
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.stderr.write(
        "ERROR: Pillow is not installed. Run `pip install Pillow` first.\n"
    )
    sys.exit(1)


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")
OUTPUT = os.path.join(ASSETS, "wheel.png")


def remove_white(img: Image.Image, threshold: int) -> Image.Image:
    img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    cleared = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (r, g, b, 0)
                cleared += 1
    print(f"  cleared {cleared:,} of {w*h:,} pixels "
          f"({cleared * 100 / (w*h):.1f}%) at threshold {threshold}")
    return img


def crop_to_content(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    if not bbox:
        return img
    cropped = img.crop(bbox)
    print(f"  cropped to {cropped.size[0]}x{cropped.size[1]}")
    return cropped


def find_default_source():
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = os.path.join(ASSETS, "wheel_source" + ext)
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "source", nargs="?",
        help="path to source image; defaults to "
             "assets/wheel_source.{png,jpg,jpeg,webp}",
    )
    ap.add_argument(
        "--threshold", type=int, default=240,
        help="per-channel pixel value above which a pixel becomes "
             "transparent (default 240)",
    )
    ap.add_argument(
        "--output", default=OUTPUT,
        help=f"output path (default {OUTPUT})",
    )
    args = ap.parse_args()

    src = args.source or find_default_source()
    if not src:
        sys.stderr.write(
            "ERROR: no source image. Pass a path, or drop one at "
            f"{ASSETS}/wheel_source.png\n"
        )
        sys.exit(1)
    if not os.path.exists(src):
        sys.stderr.write(f"ERROR: source not found: {src}\n")
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print(f"reading  {src}")
    img = Image.open(src)
    print(f"  size {img.size[0]}x{img.size[1]}, mode {img.mode}")

    print("removing background...")
    img = remove_white(img, args.threshold)

    print("cropping to content...")
    img = crop_to_content(img)

    img.save(args.output)
    print(f"wrote    {args.output}  ({img.size[0]}x{img.size[1]} RGBA)")
    print()
    print("Restart tesla_control.py to see the new wheel.")


if __name__ == "__main__":
    main()
