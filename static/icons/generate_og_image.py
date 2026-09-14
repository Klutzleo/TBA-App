"""Generate static/img/og-image.png — a 1200x630 link-preview card for tba-rpg.com.

Run: python static/icons/generate_og_image.py
Recolors the site's icon-512.png (black line-art logo on a light background) to
white-on-transparent and places it on a dark card matching index.html's
--bg/--purple/--gold palette, so the card matches the app icon used everywhere
else instead of introducing a new mark.
"""
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1200, 630
BG = (16, 18, 25)
BG2 = (22, 26, 38)
PANEL_BORDER = (51, 58, 82)
PURPLE = (167, 139, 250)
PURPLE_DIM = (108, 99, 255)
GOLD = (212, 175, 55)
TEXT = (237, 239, 245)
TEXT_DIM = (156, 163, 184)

FONT_DIR = r"C:\Windows\Fonts"

def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)

title_font = font("georgiab.ttf", 92)
accent_font = font("georgiab.ttf", 92)
lede_font = font("segoeui.ttf", 34)
brand_font = font("georgiab.ttf", 40)
url_font = font("segoeui.ttf", 28)

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img, "RGBA")

# Soft radial-ish glow behind the book icon (right side), drawn as overlapping circles.
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gdraw = ImageDraw.Draw(glow)
gdraw.ellipse((630, -100, 1350, 660), fill=(108, 99, 255, 70))
glow = glow.filter(ImageFilter.GaussianBlur(90))
img.paste(glow, (0, 0), glow)
draw = ImageDraw.Draw(img, "RGBA")

# Top panel band, matching the site's layered-panel look.
draw.rectangle((0, 0, W, 6), fill=PURPLE_DIM)

# --- App logo (icon-512.png), recolored white-on-transparent ---
_icon_dir = os.path.dirname(os.path.abspath(__file__))
_logo_gray = Image.open(os.path.join(_icon_dir, "icon-512.png")).convert("L")
# icon-512.png's "background" isn't pure white (~248), so a plain 255-v invert leaves
# a faint uniform alpha over the whole square -> visible rectangle over the glow.
# Threshold it: only real ink counts as opaque, everything else is fully transparent.
_logo_alpha = _logo_gray.point(lambda v: 255 - v if v < 235 else 0)
_logo_white = Image.new("RGBA", _logo_gray.size, (255, 255, 255, 255))
_logo_white.putalpha(_logo_alpha)

def paste_logo(target_img, cx, cy, size):
    logo = _logo_white.resize((size, size), Image.LANCZOS)
    target_img.paste(logo, (int(cx - size / 2), int(cy - size / 2)), logo)

paste_logo(img, 930, 315, 420)

# --- Text block (left-aligned) ---
LX = 80
draw.text((LX, 100), "Tell ", font=title_font, fill=TEXT)
tell_w = draw.textlength("Tell ", font=title_font)
draw.text((LX + tell_w, 100), "your", font=accent_font, fill=GOLD)
your_w = draw.textlength("your", font=accent_font)
draw.text((LX, 204), "story.", font=title_font, fill=TEXT)

draw.text((LX, 340), "Summon the party from anywhere.", font=lede_font, fill=TEXT_DIM)
draw.text((LX, 386), "Your", font=lede_font, fill=GOLD)
your2_w = draw.textlength("Your ", font=lede_font)
draw.text((LX + your2_w, 386), "legend awaits.", font=lede_font, fill=TEXT_DIM)

# Brand row: small logo + "TBA" wordmark + url
paste_logo(img, LX + 26, 530, 56)
draw.text((LX + 68, 505), "TBA", font=brand_font, fill=TEXT)
draw.text((LX + 68, 555), "tba-rpg.com", font=url_font, fill=PURPLE)

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "og-image.png")
img.save(out_path, "PNG")
print("wrote", out_path, img.size)
