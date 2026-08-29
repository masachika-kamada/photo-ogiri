from typing import Protocol

from azure.identity.aio import DefaultAzureCredential
from azure.storage.queue.aio import QueueClient

from photo_ogiri.config import Settings


class ScoringQueue(Protocol):
    async def enqueue(self, submission_id: str) -> None: ...


class AzureScoringQueue:
    def __init__(self, settings: Settings) -> None:
        if settings.azure_storage_connection_string:
            self.client = QueueClient.from_connection_string(
                settings.azure_storage_connection_string,
                settings.azure_queue_name,
            )
        elif settings.azure_queue_account_url:
            self.client = QueueClient(
                account_url=settings.azure_queue_account_url,
                queue_name=settings.azure_queue_name,
                credential=DefaultAzureCredential(),
            )
        else:
            raise ValueError("Azure Queue endpoint is required")
        if settings.azure_storage_connection_string:
            self.poison_client = QueueClient.from_connection_string(
                settings.azure_storage_connection_string,
                settings.azure_poison_queue_name,
            )
        else:
            self.poison_client = QueueClient(
                account_url=settings.azure_queue_account_url,
                queue_name=settings.azure_poison_queue_name,
                credential=DefaultAzureCredential(),
            )

    async def enqueue(self, submission_id: str) -> None:
        await self.client.send_message(submission_id)

    async def move_to_poison(self, submission_id: str) -> None:
        await self.poison_client.send_message(submission_id)


def create_scoring_queue(settings: Settings) -> ScoringQueue | None:
    if settings.scoring_backend == "queue":
        return AzureScoringQueue(settings)
    return None