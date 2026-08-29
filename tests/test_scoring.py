from photo_ogiri.scoring import rank_points


def test_rank_points_spreads_scores_from_1000_to_200() -> None:
    assert rank_points([("second", 0.5), ("first", 0.8), ("third", 0.2)]) == [
        ("first", 1, 1000),
        ("second", 2, 600),
        ("third", 3, 200),
    ]


def test_rank_points_handles_one_or_no_submission() -> None:
    assert rank_points([]) == []
    assert rank_points([("only", 0.1)]) == [("only", 1, 1000)]


def test_rank_points_breaks_ties_stably() -> None:
    assert rank_points([("b", 0.5), ("a", 0.5)]) == [
        ("a", 1, 1000),
        ("b", 2, 200),
    ]