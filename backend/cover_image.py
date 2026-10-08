"""
Cover image processing.

Every campaign cover is re-encoded on the server before it is stored, whether it was uploaded directly or copied
from the Images tab. That gives us one predictable file: a JPEG no wider than 1920px, a few hundred KB, with no
metadata (so no GPS location or camera details from a phone photo) and nothing hidden in the original bytes.
Nothing the user sent is stored as-is.
"""
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MIN_WIDTH = 800                      # narrower looks blurry once it is stretched across a card or the header
MAX_WIDTH = 1920                     # wider is wasted bytes: the widest place it shows is a 1920px header
MAX_INPUT_PIXELS = 50_000_000        # refuse decompression bombs before decoding anything
MAX_OUTPUT_BYTES = 3 * 1024 * 1024   # the stored cover must stay small, it loads on every page view
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
BACKGROUND = (19, 21, 31)            # transparent areas become the app's dark background, not black
QUALITIES = (85, 78, 70, 60)


class CoverImageError(ValueError):
    """The image can't be used as a cover. The message is safe to show to the user."""


def process_cover_image(data: bytes):
    """Validate and re-encode an image. Returns (jpeg_bytes, width, height) or raises CoverImageError."""
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in ALLOWED_FORMATS:
            raise CoverImageError("The image must be a JPEG, PNG, or WebP file.")

        width, height = img.size  # read from the header, nothing decoded yet
        if width * height > MAX_INPUT_PIXELS:
            raise CoverImageError("That image has too many pixels. Please use a smaller one.")

        img.seek(0)  # animated PNG/WebP: use the first frame only
        img = ImageOps.exif_transpose(img)  # honour phone-camera rotation
        width, height = img.size
        if width < MIN_WIDTH:
            raise CoverImageError(
                f"That image is only {width} px wide. Please use one at least {MIN_WIDTH} px wide (1600 x 400 is ideal)."
            )

        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            flat = Image.new("RGB", rgba.size, BACKGROUND)
            flat.paste(rgba, mask=rgba.getchannel("A"))
            img = flat
        else:
            img = img.convert("RGB")

        if width > MAX_WIDTH:
            height = max(1, round(height * MAX_WIDTH / width))
            width = MAX_WIDTH
            img = img.resize((width, height), Image.LANCZOS)

        for quality in QUALITIES:
            out = io.BytesIO()
            # no exif= argument: every piece of metadata is dropped
            img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
            if out.tell() <= MAX_OUTPUT_BYTES:
                return out.getvalue(), width, height
        raise CoverImageError("That image is too detailed to shrink to a reasonable size. Please try a different one.")
    except CoverImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, EOFError):
        raise CoverImageError("That image could not be read. Please try a different file.")
