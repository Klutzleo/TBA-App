"""
generate_icons.py
Run once to export icon-192.png and icon-512.png from icon.svg.

Option A — use cairosvg (pip install cairosvg):
    python generate_icons.py

Option B — drop your own PNG file named 'icon-source.png' next to this script
    and it will resize to 192 + 512. Requires Pillow (pip install Pillow).

Option C — just export your graphic directly from your design tool as:
    static/icons/icon-192.png  (192×192 px)
    static/icons/icon-512.png  (512×512 px)
and skip this script entirely.
"""

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
svg_path   = os.path.join(script_dir, "icon.svg")
source_png = os.path.join(script_dir, "icon-source.png")


def from_svg():
    try:
        import cairosvg  # type: ignore
    except ImportError:
        print("cairosvg not installed. Run: pip install cairosvg")
        return False

    for size in (192, 512):
        out = os.path.join(script_dir, f"icon-{size}.png")
        cairosvg.svg2png(url=svg_path, write_to=out, output_width=size, output_height=size)
        print(f"✅ Wrote {out}")
    return True


def from_source_png():
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        print("Pillow not installed. Run: pip install Pillow")
        return False

    if not os.path.exists(source_png):
        print(f"No source PNG found at {source_png}")
        return False

    img = Image.open(source_png).convert("RGBA")
    for size in (192, 512):
        out = os.path.join(script_dir, f"icon-{size}.png")
        img.resize((size, size), Image.LANCZOS).save(out, "PNG")
        print(f"✅ Wrote {out}")
    return True


if __name__ == "__main__":
    if os.path.exists(source_png):
        print("Found icon-source.png — resizing…")
        success = from_source_png()
    else:
        print("Using icon.svg — converting…")
        success = from_svg()

    if not success:
        print("\nFallback: export your icon manually as icon-192.png and icon-512.png")
        sys.exit(1)
