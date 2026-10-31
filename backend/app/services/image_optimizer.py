"""Compress an uploaded crossword image for storage and display.

The parser and Gemini keep using the original bytes; only the Firestore
snapshot served by ``GET /rooms/{roomId}/image`` is downscaled and re-encoded
as JPEG so it stays under the Firestore document size limit.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps

from .limits import Limits


class ImageOptimizationError(Exception):
    pass


_DEFAULT_MAX_DIMENSION = 2000
_DEFAULT_QUALITY = 82
_DEFAULT_MAX_BYTES = 700_000
_MIN_DIMENSION = 500
_FALLBACK_QUALITIES = (75, 68, 60, 52)


def _open_image(image_bytes: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        raise ImageOptimizationError("Image could not be decoded") from exc


def _normalize_to_rgb(image: Image.Image) -> Image.Image:
    try:
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB")
    except Exception as exc:
        raise ImageOptimizationError("Image could not be normalized") from exc


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


def optimize_for_display(
    image_bytes: bytes, limits: Limits | None = None
) -> bytes:
    """Return a compressed JPEG copy suitable for Firestore storage.

    The original ``image_bytes`` are never modified. Raises
    :class:`ImageOptimizationError` when the input cannot be decoded or encoded.
    """
    max_dimension = (
        limits.max_stored_image_dimension
        if limits is not None
        else _DEFAULT_MAX_DIMENSION
    )
    quality = (
        limits.stored_image_quality if limits is not None else _DEFAULT_QUALITY
    )
    max_bytes = (
        limits.max_stored_image_bytes if limits is not None else _DEFAULT_MAX_BYTES
    )

    source = _normalize_to_rgb(_open_image(image_bytes))

    qualities = [quality] + [
        candidate for candidate in _FALLBACK_QUALITIES if candidate < quality
    ]

    best: bytes = b""
    current_dimension = max_dimension
    while True:
        resized = source.copy()
        resized.thumbnail((current_dimension, current_dimension), Image.Resampling.LANCZOS)

        for candidate in qualities:
            try:
                encoded = _encode_jpeg(resized, candidate)
            except Exception as exc:
                raise ImageOptimizationError("Image could not be encoded") from exc

            if not best or len(encoded) < len(best):
                best = encoded
            if len(encoded) <= max_bytes:
                return encoded

        if current_dimension <= _MIN_DIMENSION:
            break
        current_dimension = max(_MIN_DIMENSION, int(current_dimension * 0.85))

    if not best:
        raise ImageOptimizationError("Image could not be encoded")
    return best
