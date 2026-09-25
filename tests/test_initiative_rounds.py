import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("API_KEY", "devkey")

from routes.campaign_websocket import next_round_number


@pytest.mark.parametrize(
    "current_round, old_index, new_index, expected",
    [
        # Mid-order: the turn just moves down the list, same round
        (1, 0, 1, 1),
        (1, 1, 2, 1),
        (3, 4, 5, 3),
        # Wrapping back to the top starts the next round, with no upper limit
        (1, 2, 0, 2),
        (2, 5, 0, 3),
        (40, 3, 0, 41),
        # A lone combatant: every turn is a new round
        (1, 0, 0, 2),
        # The first combatant is skipped (holding for a combo): the wrap still counts
        (1, 3, 1, 2),
        # Older rows or an unset value read as round 1
        (None, 0, 1, 1),
        (None, 2, 0, 2),
        (0, 1, 2, 1),
    ],
)
def test_next_round_number(current_round, old_index, new_index, expected):
    assert next_round_number(current_round, old_index, new_index) == expected


def test_full_lap_counts_one_round_per_wrap():
    """Walk a 4-person order around three laps: the round goes up exactly once per lap."""
    size = 4
    index, round_number = 0, 1
    rounds_seen = [round_number]
    for _ in range(size * 3):
        new_index = (index + 1) % size
        round_number = next_round_number(round_number, index, new_index)
        index = new_index
        rounds_seen.append(round_number)
    assert round_number == 4
    # First turn of each lap (index back at 0) is where the round changes
    assert rounds_seen == [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4]
