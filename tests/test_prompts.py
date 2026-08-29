import pytest

from photo_ogiri.prompts import PROMPT_PACKS, choose_prompts


def test_choose_prompts_returns_unique_items_from_pack() -> None:
    prompts = choose_prompts("daily", 3)

    assert len(prompts) == 3
    assert len(set(prompts)) == 3
    assert set(prompts) <= set(PROMPT_PACKS["daily"])


def test_choose_prompts_rejects_too_many_rounds() -> None:
    with pytest.raises(ValueError, match="Not enough prompts"):
        choose_prompts("daily", len(PROMPT_PACKS["daily"]) + 1)
