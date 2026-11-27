"""Image adapter. Placeholder mode makes an abstract gradient SVG derived from the tradition id.

No tradition-specific logic lives here: colours come from a hash of the id.
"""

import colorsys
import hashlib
from typing import Protocol

from app.config import Settings


class ImageSource(Protocol):
    def image_for(self, tradition: str, theme: str, time_of_day: str) -> tuple[bytes, str]:
        """Return (bytes, mime type)."""
        ...


def _hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class PlaceholderImages:
    def image_for(self, tradition: str, theme: str, time_of_day: str) -> tuple[bytes, str]:
        digest = hashlib.sha256(f"{tradition}|{theme}|{time_of_day}".encode()).digest()
        hue = digest[0] / 255
        top, bottom = _hex(hue, 0.35, 0.85), _hex(hue + 0.12, 0.55, 0.45)
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
            '</linearGradient></defs><rect width="1024" height="1024" fill="url(#g)"/></svg>'
        )
        return svg.encode(), "image/svg+xml"


def get_images(settings: Settings) -> ImageSource:
    if settings.image_mode == "placeholder":
        return PlaceholderImages()
    raise NotImplementedError("Image library / generation is wired up in M7")
