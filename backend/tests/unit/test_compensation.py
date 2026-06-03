import pytest

from crud.calculations import compute_compensation_per_unit


@pytest.mark.parametrize(
    "avg_price, ref_price, corridor_pct, expected",
    [
        (110.0, 100.0, 5.0, 5.0),    # overrun beyond corridor → +5
        (90.0, 100.0, 5.0, -5.0),    # saving beyond corridor → -5
        (103.0, 100.0, 5.0, 0.0),    # inside [95;105] → 0
        (105.0, 100.0, 5.0, 0.0),    # exactly on upper boundary → 0
        (95.0, 100.0, 5.0, 0.0),     # exactly on lower boundary → 0
        (110.0, 100.0, 0.0, 10.0),   # corridor 0% → compensation == deviation
        (90.0, 100.0, 0.0, -10.0),   # corridor 0% both ways
    ],
)
def test_compensation_per_unit(avg_price, ref_price, corridor_pct, expected):
    assert compute_compensation_per_unit(avg_price, ref_price, corridor_pct) == expected


def test_compensation_none_when_no_ref_price():
    assert compute_compensation_per_unit(110.0, None, 5.0) is None
    assert compute_compensation_per_unit(110.0, 0.0, 5.0) is None


def test_compensation_none_when_corridor_not_set():
    assert compute_compensation_per_unit(110.0, 100.0, None) is None
