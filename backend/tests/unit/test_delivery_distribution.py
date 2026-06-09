"""Unit tests for dimension-aware delivery allocation — no DB."""
from decimal import Decimal
from types import SimpleNamespace

from crud.calculations import compute_shared_shares

D = Decimal


def _row(class_id, dimension, qty, amount):
    return SimpleNamespace(
        material_class_id=class_id, dimension=dimension,
        qty=D(qty), mat_total=D(amount),
    )


class TestComputeSharedShares:
    def test_mono_dimension_splits_by_quantity(self):
        rows = [_row(1, "volume", "30", "300"), _row(2, "volume", "10", "900")]
        shares = compute_shared_shares(rows)
        assert shares[1] == D("30") / D("40")
        assert shares[2] == D("10") / D("40")

    def test_mixed_dimension_splits_by_amount(self):
        rows = [_row(1, "volume", "50", "1000"), _row(2, "mass", "2", "3000")]
        shares = compute_shared_shares(rows)
        assert shares[1] == D("1000") / D("4000")
        assert shares[2] == D("3000") / D("4000")

    def test_mixed_dimension_zero_amount_no_split(self):
        rows = [_row(1, "volume", "50", "0"), _row(2, "mass", "2", "0")]
        shares = compute_shared_shares(rows)
        assert shares[1] == D("0")
        assert shares[2] == D("0")

    def test_partial_zero_amount_in_mixed(self):
        rows = [_row(1, "volume", "50", "0"), _row(2, "mass", "2", "4000")]
        shares = compute_shared_shares(rows)
        assert shares[1] == D("0")
        assert shares[2] == D("1")

    def test_mono_zero_qty_no_split(self):
        rows = [_row(1, "volume", "0", "0")]
        shares = compute_shared_shares(rows)
        assert shares[1] == D("0")

    def test_duplicate_class_id_accumulates_not_last_wins(self):
        # Same class appears twice (e.g. two normalized-unit rows) — basis must sum,
        # not drop one. Mixed dims here → amount basis; 1000 + 3000 share vs 4000 total.
        rows = [
            _row(1, "volume", "50", "1000"),
            _row(1, "mass", "2", "3000"),
            _row(2, "mass", "1", "4000"),
        ]
        shares = compute_shared_shares(rows)
        assert shares[1] == D("4000") / D("8000")  # 1000+3000 summed, not last-wins 3000
        assert shares[2] == D("4000") / D("8000")
