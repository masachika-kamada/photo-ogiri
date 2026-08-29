import asyncio
import traceback

from azure.core.exceptions import AzureError

from photo_ogiri.api import judge, mark_submission_failed, score_submission
from photo_ogiri.config import get_settings
from photo_ogiri.jobs import AzureScoringQueue


async def run_worker() -> None:
    settings = get_settings()
    if settings.scoring_backend != "queue":
        raise RuntimeError("Set PHOTO_OGIRI_SCORING_BACKEND=queue to run the worker")

    queue = AzureScoringQueue(settings)
    print("Loading the SigLIP judge...", flush=True)
    await judge.warmup()
    print("Scoring worker is ready", flush=True)
    while True:
        found_message = False
        try:
            messages = queue.client.receive_messages(
                messages_per_page=16,
                visibility_timeout=settings.worker_visibility_timeout,
            )
            async for message in messages:
                found_message = True
                try:
                    await score_submission(message.content, terminal_failure=False)
                except Exception:
                    traceback.print_exc()
                    if (message.dequeue_count or 1) >= settings.worker_max_dequeue_count:
                        await mark_submission_failed(message.content)
                        await queue.move_to_poison(message.content)
                        await queue.client.delete_message(message.id, message.pop_receipt)
                else:
                    await queue.client.delete_message(message.id, message.pop_receipt)
        except AzureError:
            traceback.print_exc()
        if not found_message:
            await asyncio.sleep(settings.worker_poll_seconds)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()