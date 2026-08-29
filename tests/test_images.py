from io import BytesIO

import pytest
from PIL import Image

from photo_ogiri.images import normalize_image


def image_bytes(format_name: str = "PNG", size: tuple[int, int] = (8, 6)) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", size, "red")
    exif = Image.Exif()
    exif[315] = "private metadata"
    image.save(output, format_name, exif=exif)
    return output.getvalue()


def test_normalization_outputs_jpeg_without_exif() -> None:
    normalized = normalize_image(image_bytes())

    with Image.open(BytesIO(normalized)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert not image.getexif()


def test_normalization_rejects_unsupported_formats() -> None:
    with pytest.raises(ValueError, match="unsupported image format"):
        normalize_image(image_bytes("GIF"))


def test_normalization_rejects_excessive_dimensions_before_decode() -> None:
    with pytest.raises(ValueError, match="dimensions are too large"):
        normalize_image(image_bytes(size=(3, 2)), max_pixels=5)
