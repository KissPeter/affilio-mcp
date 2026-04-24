"""DUMMY QR code generator using segno.

NOTE: This is a standalone implementation for affilio-mcp usage.
It generates real QR codes using the segno library (if installed),
or falls back to a placeholder image. Does not fetch external logos.
"""
from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageDraw


def _hex_to_rgb(hex_color: str) -> tuple[int, ...]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _is_finder(x: int, y: int, module_count: int) -> bool:
    return (
        (x < 8 and y < 8)
        or (x >= module_count - 8 and y < 8)
        or (x < 8 and y >= module_count - 8)
    )


class QRCodeGenerator:
    """Generate QR code images using segno."""

    def __init__(
        self,
        url: str,
        logo: Optional[str] = None,
        background_color: str = "#FFFFFF",
        background_transparent: bool = True,
        color: str = "#000000",
        rounded: bool = True,
    ):
        self.url = url
        self.logo = logo
        self.bg = background_color
        self.transparent = background_transparent
        self.color = color
        self.rounded = rounded

    def get_qr_code(self) -> Image.Image:
        try:
            import segno
        except ImportError:
            # Fallback: return a placeholder image if segno not installed
            img = Image.new("RGBA", (360, 360), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(0, 0), (359, 359)], outline=(0, 0, 0), width=2)
            draw.text((10, 10), self.url[:50], fill=(0, 0, 0))
            return img

        qr = segno.make(self.url, error="h")
        buf = io.BytesIO()
        qr.save(
            buf,
            kind="png",
            dark=self.color,
            light=None if self.transparent else self.bg,
            scale=10,
            border=4,
        )
        buf.seek(0)
        return Image.open(buf).convert("RGBA")
