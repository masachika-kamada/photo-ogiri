from __future__ import annotations

import asyncio
from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    import numpy as np

    from photo_ogiri.embedder import SiglipEmbedder


class Judge:
    def __init__(self) -> None:
        self._embedder: SiglipEmbedder | None = None
        self._prompt_vectors: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()

    def _model(self) -> SiglipEmbedder:
        if self._embedder is None:
            from photo_ogiri.embedder import SiglipEmbedder

            self._embedder = SiglipEmbedder()
        return self._embedder

    async def score(self, prompt: str, image: bytes) -> float:
        async with self._lock:
            return await asyncio.to_thread(self._score_sync, prompt, image)

    async def warmup(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._model)

    def _score_sync(self, prompt: str, content: bytes) -> float:
        import numpy as np

        model = self._model()
        with Image.open(BytesIO(content)) as image:
            image_input = image.convert("RGB")
            inputs = model.processor(images=[image_input], return_tensors="pt").to(
                model.device
            )
            features = model.model.get_image_features(**inputs).pooler_output
            image_vector = features.detach().cpu().numpy()[0].astype(np.float32)
        image_vector /= np.linalg.norm(image_vector)
        prompt_vector = self._prompt_vectors.get(prompt)
        if prompt_vector is None:
            prompt_vector = model.embed_text(prompt)
            self._prompt_vectors[prompt] = prompt_vector
        return float(image_vector @ prompt_vector)
