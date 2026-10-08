"""
Tests for backend/cover_image.py: every cover is validated and re-encoded to a small, metadata-free JPEG.

The risky parts: nothing the user uploaded is stored as-is, location data is stripped, a decompression bomb is refused
before it is decoded, and transparent or rotated phone photos come out right.
"""
import io

import pytest
from PIL import Image

from backend.cover_image import (
    BACKGROUND,
    MAX_OUTPUT_BYTES,
    MAX_WIDTH,
    MIN_WIDTH,
    CoverImageError,
    process_cover_image,
)


def encode(img, fmt="PNG", **kw):
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


def solid(size, color=(40, 110, 160), mode="RGB"):
    return Image.new(mode, size, color)


def test_png_becomes_a_jpeg_with_the_same_proportions():
    jpeg, w, h = process_cover_image(encode(solid((1600, 400))))
    assert jpeg[:3] == b"\xff\xd8\xff"
    assert (w, h) == (1600, 400)
    assert Image.open(io.BytesIO(jpeg)).format == "JPEG"


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_all_three_allowed_formats_work(fmt):
    jpeg, w, h = process_cover_image(encode(solid((1200, 300)), fmt))
    assert Image.open(io.BytesIO(jpeg)).size == (1200, 300)


def test_wide_images_are_shrunk_to_the_widest_place_they_show():
    jpeg, w, h = process_cover_image(encode(solid((3000, 600))))
    assert (w, h) == (MAX_WIDTH, 384)
    assert Image.open(io.BytesIO(jpeg)).size == (MAX_WIDTH, 384)


def test_width_boundary():
    process_cover_image(encode(solid((MIN_WIDTH, 200))))
    with pytest.raises(CoverImageError) as e:
        process_cover_image(encode(solid((MIN_WIDTH - 1, 200))))
    assert f"{MIN_WIDTH - 1} px wide" in str(e.value)


def test_transparent_png_is_flattened_onto_the_dark_background_not_black():
    img = Image.new("RGBA", (1000, 300), (0, 0, 0, 0))  # fully transparent
    jpeg, _, _ = process_cover_image(encode(img))
    px = Image.open(io.BytesIO(jpeg)).getpixel((500, 150))
    assert all(abs(a - b) <= 6 for a, b in zip(px, BACKGROUND)), px


def test_location_and_camera_metadata_is_removed():
    exif = Image.Exif()
    exif[0x010F] = "SomeCamera"
    exif[0x8825] = {1: "N", 2: (40.0, 44.0, 0.0)}
    original = encode(solid((1600, 400)), "JPEG", exif=exif)
    assert b"Exif" in original  # the input really has metadata
    jpeg, _, _ = process_cover_image(original)
    assert b"Exif" not in jpeg
    assert not Image.open(io.BytesIO(jpeg)).getexif()


def test_phone_rotation_is_honoured():
    portrait = solid((900, 1700))
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90": the file is stored sideways, the viewer turns it upright
    jpeg, w, h = process_cover_image(encode(portrait, "JPEG", exif=exif))
    assert (w, h) == (1700, 900)  # after rotation it is wide enough to use


def test_not_an_allowed_image_is_refused():
    gif = encode(solid((1200, 300), mode="P"), "GIF")
    for bad in (b"", b"just text", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", gif,
                b"\x89PNG\r\n\x1a\n" + b"truncated"):
        with pytest.raises(CoverImageError):
            process_cover_image(bad)


def test_decompression_bomb_is_refused_before_it_is_decoded():
    huge = Image.new("1", (60000, 1000))  # 60 million pixels, tiny as a file
    data = encode(huge)
    assert len(data) < 200_000
    with pytest.raises(CoverImageError) as e:
        process_cover_image(data)
    assert "too many pixels" in str(e.value)


def test_output_never_exceeds_the_size_cap():
    import os
    noise = Image.frombytes("RGB", (1920, 1100), os.urandom(1920 * 1100 * 3))  # worst case for compression
    try:
        jpeg, _, _ = process_cover_image(encode(noise))
    except CoverImageError as e:
        assert "too detailed" in str(e)
    else:
        assert len(jpeg) <= MAX_OUTPUT_BYTES


def test_animated_image_uses_its_first_frame():
    frames = [solid((1000, 250), (200, 0, 0)), solid((1000, 250), (0, 200, 0))]
    data = encode(frames[0], "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)
    jpeg, w, h = process_cover_image(data)
    r, g, b = Image.open(io.BytesIO(jpeg)).getpixel((500, 125))
    assert r > 150 and g < 60  # the first (red) frame
