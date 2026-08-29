from unittest.mock import Mock, call

import photo_ogiri.jobs as jobs_module
from photo_ogiri.config import Settings
from photo_ogiri.jobs import AzureScoringQueue, create_scoring_queue


def test_inline_scoring_does_not_create_an_external_queue() -> None:
    assert create_scoring_queue(Settings(scoring_backend="inline")) is None


def test_managed_identity_queue_clients_use_separate_account_and_queue_names(monkeypatch) -> None:
    queue_client = Mock()
    credential = Mock()
    monkeypatch.setattr(jobs_module, "QueueClient", queue_client)
    monkeypatch.setattr(jobs_module, "DefaultAzureCredential", lambda: credential)

    AzureScoringQueue(
        Settings(
            azure_queue_account_url="https://example.queue.core.windows.net/",
            azure_queue_name="jobs",
            azure_poison_queue_name="poison",
        )
    )

    assert queue_client.call_args_list == [
        call(
            account_url="https://example.queue.core.windows.net/",
            queue_name="jobs",
            credential=credential,
        ),
        call(
            account_url="https://example.queue.core.windows.net/",
            queue_name="poison",
            credential=credential,
        ),
    ]