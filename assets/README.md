# assets/

Optional runtime art for `tesla_control.py`.

## `wheel.png`

If a transparent-background `wheel.png` lives in this folder, the GUI's
steering-wheel widget shows it rotating with the commanded angle. Without
the file, the GUI falls back to a minimal vector wheel.

### How to make one

Easiest path:

1. Drop a steering-wheel photo here as `wheel_source.jpg` (or .png /
   .jpeg / .webp). The photo should have a mostly-white background --
   most marketing photos already do.
2. From the repo root run:

   ```
   python tools/prepare_wheel.py
   ```

   That removes near-white pixels, crops to content, and writes
   `assets/wheel.png`.

If your source has a coloured or busy background, use a proper
background-removal tool (https://remove.bg, Photopea) and drop the
resulting transparent PNG straight in here as `wheel.png`.

The GUI re-reads the file at startup, so after you drop a new image
just close the program and reopen.
