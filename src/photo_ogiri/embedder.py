import numpy as np
import torch
import torch.nn.functional as functional
from transformers import AutoModel, AutoProcessor

DEFAULT_MODEL = "google/siglip2-base-patch16-224"


class SiglipEmbedder:
    def __init__(
        self, model_name: str = DEFAULT_MODEL, device: str | None = None
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device).eval()

    @torch.inference_mode()
    def embed_text(self, text: str) -> np.ndarray:
        inputs = self.processor(
            text=[text],
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).to(self.device)
        features = self.model.get_text_features(**inputs).pooler_output
        return (
            functional.normalize(features, dim=-1).cpu().numpy()[0].astype(np.float32)
        )
