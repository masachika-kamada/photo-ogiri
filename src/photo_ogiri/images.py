import warnings
from io import BytesIO

from PIL import Image, ImageOps

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 20_000_000


def normalize_image(content: bytes, max_pixels: int = 20_000_000) -> bytes:
    if not content:
        raise ValueError("image is empty")

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(content)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise ValueError("unsupported image format")
            if source.width * source.height > max_pixels:
                raise ValueError("image dimensions are too large")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1600, 1600))
            output = BytesIO()
            image.save(output, "JPEG", quality=88, optimize=True)
            return output.getvalue()