from collections.abc import Sequence


def rank_points(scores: Sequence[tuple[str, float]]) -> list[tuple[str, int, int]]:
    ordered = sorted(scores, key=lambda item: (-item[1], item[0]))
    count = len(ordered)
    if count == 0:
        return []
    if count == 1:
        return [(ordered[0][0], 1, 1000)]

    return [
        (submission_id, rank, round(1000 - 800 * (rank - 1) / (count - 1)))
        for rank, (submission_id, _) in enumerate(ordered, start=1)
    ]