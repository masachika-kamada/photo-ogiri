from pathlib import Path
from typing import Protocol

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from photo_ogiri.config import Settings


class ImageStorage(Protocol):
    async def put(self, name: str, content: bytes) -> None: ...
    async def get(self, name: str) -> bytes: ...


class LocalImageStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, name: str) -> Path:
        path = (self.root / name).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid image path")
        return path

    async def put(self, name: str, content: bytes) -> None:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def get(self, name: str) -> bytes:
        return self._path(name).read_bytes()


class AzureBlobImageStorage:
    def __init__(self, settings: Settings) -> None:
        if settings.azure_storage_connection_string:
            self.client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
        elif settings.azure_storage_account_url:
            self.client = BlobServiceClient(settings.azure_storage_account_url, DefaultAzureCredential())
        else:
            raise ValueError("Azure Storage endpoint is required")
        self.container = self.client.get_container_client(settings.azure_blob_container)

    async def put(self, name: str, content: bytes) -> None:
        await self.container.upload_blob(name, content, overwrite=True, content_type="image/jpeg")

    async def get(self, name: str) -> bytes:
        stream = await self.container.download_blob(name)
        return await stream.readall()


def create_storage(settings: Settings) -> ImageStorage:
    if settings.storage_backend == "azure":
        return AzureBlobImageStorage(settings)
    return LocalImageStorage(settings.local_storage_path)