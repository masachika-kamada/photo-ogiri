import argparse
import concurrent.futures
from io import BytesIO
import time
from pathlib import Path

import httpx
from PIL import Image


def request(
    client: httpx.Client, method: str, path: str, **kwargs: object
) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exercise one Photo Ogiri room with concurrent players."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--players", type=int, default=100)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--skip-uploads", action="store_true")
    args = parser.parse_args()
    if not 2 <= args.players <= 100:
        raise SystemExit("--players must be between 2 and 100")

    started_at = time.perf_counter()
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=60) as client:
        game = request(
            client,
            "POST",
            "/api/games",
            json={
                "title": "100-player PoC load test",
                "prompts": ["未来から来たように見える物"],
                "round_seconds": 300,
                "max_players": args.players,
            },
        ).json()

        def join(index: int) -> dict[str, str]:
            with httpx.Client(base_url=args.url.rstrip("/"), timeout=60) as worker:
                return request(
                    worker,
                    "POST",
                    f"/api/games/{game['code']}/players",
                    json={"name": f"load-{index:03d}"},
                ).json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            players = list(executor.map(join, range(args.players)))
        joined_at = time.perf_counter()
        host_headers = {"Authorization": f"Bearer {game['host_token']}"}
        request(
            client, "POST", f"/api/games/{game['code']}/advance", headers=host_headers
        )

        if not args.skip_uploads:
            if args.image:
                content = args.image.read_bytes()
                image_name = args.image.name
            else:
                image_buffer = BytesIO()
                Image.new("RGB", (224, 224), "skyblue").save(
                    image_buffer, format="JPEG"
                )
                content = image_buffer.getvalue()
                image_name = "generated-sample.jpg"

            def submit(player: dict[str, str]) -> None:
                with httpx.Client(base_url=args.url.rstrip("/"), timeout=120) as worker:
                    request(
                        worker,
                        "POST",
                        f"/api/games/{game['code']}/submissions",
                        headers={"Authorization": f"Bearer {player['player_token']}"},
                        files={"image": (image_name, content, "image/jpeg")},
                    )

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                list(executor.map(submit, players))
            submitted_at = time.perf_counter()

            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                state = request(client, "GET", f"/api/games/{game['code']}").json()
                if not any(
                    item["status"] == "queued" for item in state["round"]["submissions"]
                ):
                    break
                time.sleep(2)
            else:
                raise TimeoutError("AI scoring did not finish within 15 minutes")
            request(
                client,
                "POST",
                f"/api/games/{game['code']}/advance",
                headers=host_headers,
            )
            finished_at = time.perf_counter()
            print(
                f"players={args.players} join={joined_at - started_at:.2f}s "
                f"upload={submitted_at - joined_at:.2f}s score={finished_at - submitted_at:.2f}s"
            )
        else:
            print(f"players={args.players} join={joined_at - started_at:.2f}s")


if __name__ == "__main__":
    main()
