from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from PIL import Image

import photo_ogiri.api as api_module
from photo_ogiri.models import Base
from photo_ogiri.storage import LocalImageStorage


def test_complete_single_round_game(tmp_path: Path) -> None:
    async def reset_database() -> None:
        async with api_module.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    api_module.storage = LocalImageStorage(tmp_path / "uploads")
    api_module.judge.score = AsyncMock(return_value=0.75)

    with TestClient(api_module.app) as client:
        import asyncio

        asyncio.run(reset_database())
        created = client.post(
            "/api/games",
            json={
                "title": "テスト大会",
                "prompts": ["月曜日っぽいもの"],
                "round_seconds": 90,
                "max_players": 100,
            },
        )
        assert created.status_code == 201
        game = created.json()

        joined = client.post(
            f"/api/games/{game['code']}/players", json={"name": "Alice"}
        )
        assert joined.status_code == 201
        player = joined.json()

        advanced = client.post(
            f"/api/games/{game['code']}/advance",
            headers={"Authorization": f"Bearer {game['host_token']}"},
        )
        assert advanced.status_code == 204

        active_state = client.get(f"/api/games/{game['code']}").json()
        deadline = datetime.fromisoformat(active_state["round"]["deadline"])
        assert deadline.utcoffset() == timedelta(0)

        image_buffer = BytesIO()
        Image.new("RGB", (32, 32), "skyblue").save(image_buffer, format="JPEG")
        image = image_buffer.getvalue()
        submitted = client.post(
            f"/api/games/{game['code']}/submissions",
            headers={"Authorization": f"Bearer {player['player_token']}"},
            files={"image": ("beach.jpg", image, "image/jpeg")},
        )
        assert submitted.status_code == 202

        finished = client.post(
            f"/api/games/{game['code']}/advance",
            headers={"Authorization": f"Bearer {game['host_token']}"},
        )
        assert finished.status_code == 204

        state = client.get(f"/api/games/{game['code']}").json()
        assert state["status"] == "finished"
        assert state["players"][0]["total_points"] == 1000
        assert state["round"]["submissions"][0]["ai_score"] == 0.75
        assert state["round"]["submissions"][0]["rank"] == 1
