import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image
from transformers import AutoModel, AutoProcessor

DEFAULT_MODEL = "google/siglip2-base-patch16-224"
DEFAULT_MODEL_REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"


class SiglipEmbedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        revision: str | None = None,
        device: str | None = None,
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        resolved_revision = (
            DEFAULT_MODEL_REVISION if model_name == DEFAULT_MODEL else revision
        )
        self.processor = AutoProcessor.from_pretrained(
            model_name, revision=resolved_revision
        )
        self.model = (
            AutoModel.from_pretrained(model_name, revision=resolved_revision)
            .to(self.device)
            .eval()
        )

    @torch.inference_mode()
    def embed_text(self, text: str) -> np.ndarray:
        inputs = self.processor(
            text=[text],
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).to(self.device)
        features = self.model.get_text_features(**inputs).pooler_output
        return self._normalize(features)

    @torch.inference_mode()
    def embed_image(self, image: Image.Image) -> np.ndarray:
        inputs = self.processor(
            images=[image.convert("RGB")], return_tensors="pt"
        ).to(self.device)
        features = self.model.get_image_features(**inputs).pooler_output
        return self._normalize(features)

    @staticmethod
    def _normalize(features: torch.Tensor) -> np.ndarray:
        return (
            functional.normalize(features, dim=-1).cpu().numpy()[0].astype(np.float32)
        )
