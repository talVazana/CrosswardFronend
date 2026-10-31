import io

import pytest
from PIL import Image

from app.services.image_optimizer import ImageOptimizationError, optimize_for_display
from app.services.limits import Limits, get_limits


def png_bytes(width: int, height: int, mode: str = "RGB", color=(200, 40, 40)):
    image = Image.new(mode, (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_signature(data: bytes) -> bool:
    return data[:2] == b"\xff\xd8"


def decoded_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def test_large_png_is_downscaled_and_converted_to_jpeg():
    original = png_bytes(4000, 3000)
    result = optimize_for_display(original)

    assert jpeg_signature(result)
    width, height = decoded_size(result)
    assert max(width, height) <= get_limits().max_stored_image_dimension
    assert len(result) < len(original)


def test_small_image_is_not_upscaled():
    original = png_bytes(300, 200)
    result = optimize_for_display(original)

    width, height = decoded_size(result)
    assert width <= 300 and height <= 200
    assert jpeg_signature(result)


def test_rgba_png_converts_to_rgb_jpeg():
    original = png_bytes(400, 300, mode="RGBA", color=(10, 20, 30, 128))
    result = optimize_for_display(original)

    assert jpeg_signature(result)
    with Image.open(io.BytesIO(result)) as image:
        assert image.mode == "RGB"


def test_palette_png_converts_without_error():
    image = Image.new("P", (200, 150))
    image.putpalette([0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    result = optimize_for_display(buffer.getvalue())
    assert jpeg_signature(result)


def test_noisy_image_fits_within_max_bytes():
    noise = Image.effect_noise((2400, 1800), 100).convert("RGB")
    buffer = io.BytesIO()
    noise.save(buffer, format="JPEG", quality=95)
    original = buffer.getvalue()

    result = optimize_for_display(original)
    assert jpeg_signature(result)
    assert len(result) <= get_limits().max_stored_image_bytes


def test_invalid_bytes_raise_controlled_error():
    with pytest.raises(ImageOptimizationError):
        optimize_for_display(b"not-a-real-image")
