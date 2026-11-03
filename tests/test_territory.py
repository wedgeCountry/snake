"""Territory (strategy) game tests. The shared contract suite in
tests/contracts/ also runs against it via the registry."""

import random

from games.territory.config import TerritoryConfig
from games.territory.core import TerritoryGame


def _game(seed=1):
    g = TerritoryGame(rng=random.Random(seed))
    g.init(TerritoryConfig())
    return g


def test_init_places_center_territory_and_mines():
    g = _game()
    s = g.state()
    assert s.pos == (4, 4)
    assert s.territory == {(4, 4)}
    assert len(s.mines) == 6
    assert (4, 4) not in s.mines
    assert s.status == "running"


def test_settler_claims_adjacent_free_cell():
    g = _game()
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().pos == (5, 4)
    assert (5, 4) in g.state().territory


def test_settler_cannot_claim_non_adjacent_cell():
    g = _game()
    s = g.state()
    s.pos = (0, 0)  # far away from the center territory
    g.apply_action(0, {"direction": "up"})  # clamped at the border
    g.tick()
    assert g.state().pos == (0, 0)
    assert (0, 0) not in g.state().territory  # not adjacent -> not claimed


def test_opposite_turn_is_rejected_by_shared_queue():
    g = _game()
    g.apply_action(0, {"direction": "left"})  # 180-degree turn vs default right
    g.tick()
    assert g.state().pos == (5, 4)  # still drifting right


def test_territory_grows_and_score_rises():
    g = _game()
    for _ in range(5):
        g.tick()
    s = g.state()
    assert len(s.territory) > 1  # auto-growth frontier expansion
    assert s.gold > 0 and s.score > 0
    assert s.turn == 5


def test_terminal_at_turn_limit_and_stable():
    g = _game()
    for _ in range(80):
        g.tick()
    assert g.is_terminal()
    before = repr(g.state())
    g.tick()
    assert repr(g.state()) == before


def test_single_player_rejects_player_1():
    import pytest
    g = _game()
    with pytest.raises(ValueError):
        g.apply_action(1, {"direction": "left"})
