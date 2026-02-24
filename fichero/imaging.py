"""Image processing for Fichero D11s thermal label printer."""

import logging

from PIL import Image, ImageDraw, ImageFont, ImageOps

from fichero.printer import PRINTHEAD_PX

log = logging.getLogger(__name__)


def prepare_image(img: Image.Image, max_rows: int = 240) -> Image.Image:
    """Convert any image to 96px wide, 1-bit, black on white."""
    img = img.convert("L")
    w, h = img.size
    new_h = int(h * (PRINTHEAD_PX / w))
    if new_h > max_rows:
        log.warning("Image height %dpx exceeds max %dpx, cropping bottom", new_h, max_rows)
        new_h = max_rows
    img = img.resize((PRINTHEAD_PX, new_h), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.point(lambda x: 1 if x < 128 else 0, "1")
    return img


def image_to_raster(img: Image.Image) -> bytes:
    """Pack 1-bit image into raw raster bytes, MSB first."""
    if img.mode != "1":
        raise ValueError(f"Expected mode '1', got '{img.mode}'")
    if img.width != PRINTHEAD_PX:
        raise ValueError(f"Expected width {PRINTHEAD_PX}, got {img.width}")
    return img.tobytes()


def text_to_image(text: str, font_size: int = 30, label_height: int = 240) -> Image.Image:
    """Render crisp 1-bit text, rotated 90 degrees for label printing."""
    canvas_w = label_height
    canvas_h = PRINTHEAD_PX
    img = Image.new("L", (canvas_w, canvas_h), 255)
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1"  # disable antialiasing - pure 1-bit glyph rendering

    font = ImageFont.load_default(size=font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (canvas_w - tw) // 2
    y = (canvas_h - th) // 2
    draw.text((x, y), text, fill=0, font=font)

    img = img.rotate(90, expand=True)
    return img
