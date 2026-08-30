from __future__ import annotations

import asyncio
from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    import numpy as np

    from photo_ogiri.embedder import SiglipEmbedder


class Judge:
    def __init__(self, embedder: SiglipEmbedder | None = None) -> None:
        self._embedder = embedder
        self._prompt_vectors: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()

    def _get_embedder(self) -> SiglipEmbedder:
        if self._embedder is None:
            from photo_ogiri.embedder import SiglipEmbedder

            self._embedder = SiglipEmbedder()
        return self._embedder

    async def score(self, prompt: str, image: bytes) -> float:
        async with self._lock:
            return await asyncio.to_thread(self._score_sync, prompt, image)

    async def load_model(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._get_embedder)

    def _score_sync(self, prompt: str, content: bytes) -> float:
        embedder = self._get_embedder()
        with Image.open(BytesIO(content)) as image:
            image_vector = embedder.embed_image(image)
        prompt_vector = self._prompt_vectors.get(prompt)
        if prompt_vector is None:
            prompt_vector = embedder.embed_text(prompt)
            self._prompt_vectors[prompt] = prompt_vector
        return float(image_vector @ prompt_vector)
