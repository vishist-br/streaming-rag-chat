import pytest

from app.retrieval.fusion import reciprocal_rank_fusion


def test_item_in_both_lists_beats_items_in_one() -> None:
    fused = reciprocal_rank_fusion([[1, 2, 3], [3, 4, 5]])
    assert fused[0][0] == 3


def test_scores_follow_the_rrf_formula() -> None:
    fused = dict(reciprocal_rank_fusion([[10, 20], [20]], k=60))
    assert fused[20] == pytest.approx(1 / 62 + 1 / 61)
    assert fused[10] == pytest.approx(1 / 61)


def test_single_list_keeps_its_order() -> None:
    assert [item for item, _ in reciprocal_rank_fusion([[7, 3, 9], []])] == [7, 3, 9]


def test_ties_are_broken_by_id_so_output_is_deterministic() -> None:
    # 1 and 2 are each ranked first in one list: identical scores.
    assert [item for item, _ in reciprocal_rank_fusion([[2], [1]])] == [1, 2]


def test_smaller_k_rewards_top_ranks_more() -> None:
    # Item 1: ranks 1 and 10. Item 2: ranks 3 and 3.
    lists = [[1, 9, 2, *range(100, 107)], [8, 7, 2, *range(200, 206), 1]]
    assert reciprocal_rank_fusion(lists, k=1)[0][0] == 1
    assert reciprocal_rank_fusion(lists, k=60)[0][0] == 2


def test_empty_input() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
