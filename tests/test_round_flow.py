from datetime import datetime, timezone

from photo_ogiri.api import deadline_passed
from photo_ogiri.scoring import rank_points


def test_two_player_points_span_the_full_range() -> None:
    assert rank_points([("first", 0.9), ("second", 0.1)]) == [
        ("first", 1, 1000),
        ("second", 2, 200),
    ]


def test_timezone_aware_deadline_is_supported() -> None:
    assert deadline_passed(datetime(2020, 1, 1, tzinfo=timezone.utc))