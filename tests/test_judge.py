from io import BytesIO

import pytest
from PIL import Image

from photo_ogiri.judge import Judge


class DotVector:
    def __init__(self, result: float) -> None:
        self.result = result

    def __matmul__(self, other: object) -> float:
        return self.result


class FakeEmbedder:
    def __init__(self) -> None:
        self.image_modes: list[str] = []
        self.texts: list[str] = []

    def embed_image(self, image: Image.Image) -> DotVector:
        self.image_modes.append(image.mode)
        return DotVector(0.75)

    def embed_text(self, text: str) -> object:
        self.texts.append(text)
        return object()


@pytest.mark.asyncio
async def test_scoring_uses_embedder_and_caches_prompt() -> None:
    output = BytesIO()
    Image.new("L", (8, 6), 128).save(output, format="PNG")

    embedder = FakeEmbedder()
    judge = Judge(embedder=embedder)

    assert await judge.score("prompt", output.getvalue()) == 0.75
    assert await judge.score("prompt", output.getvalue()) == 0.75
    assert embedder.image_modes == ["L", "L"]
    assert embedder.texts == ["prompt"]
