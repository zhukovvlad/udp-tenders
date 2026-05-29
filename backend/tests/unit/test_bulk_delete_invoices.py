"""Unit-тесты для bulk_delete_invoices (DELETE /api/invoices/bulk)."""
from unittest.mock import MagicMock, call

from routers.invoices import BulkDeleteRequest, bulk_delete_invoices


def _make_invoice(id_: int, verified: bool) -> MagicMock:
    inv = MagicMock()
    inv.id = id_
    inv.verified = verified
    return inv


def _make_db(invoices: list) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = invoices
    return db


class TestBulkDeleteInvoices:
    def test_empty_ids_returns_zero(self):
        db = _make_db([])
        result = bulk_delete_invoices(BulkDeleteRequest(ids=[]), db)
        assert result == {"deleted": 0, "skipped": []}
        db.delete.assert_not_called()
        db.commit.assert_not_called()

    def test_deletes_unverified(self):
        inv = _make_invoice(1, verified=False)
        db = _make_db([inv])
        result = bulk_delete_invoices(BulkDeleteRequest(ids=[1]), db)
        assert result == {"deleted": 1, "skipped": []}
        db.delete.assert_called_once_with(inv)
        db.commit.assert_called_once()

    def test_skips_verified(self):
        inv = _make_invoice(2, verified=True)
        db = _make_db([inv])
        result = bulk_delete_invoices(BulkDeleteRequest(ids=[2]), db)
        assert result == {"deleted": 0, "skipped": [2]}
        db.delete.assert_not_called()
        db.commit.assert_called_once()

    def test_mixed_deletes_unverified_skips_verified(self):
        inv1 = _make_invoice(1, verified=False)
        inv2 = _make_invoice(2, verified=True)
        inv3 = _make_invoice(3, verified=False)
        db = _make_db([inv1, inv2, inv3])
        result = bulk_delete_invoices(BulkDeleteRequest(ids=[1, 2, 3]), db)
        assert result["deleted"] == 2
        assert result["skipped"] == [2]
        assert db.delete.call_count == 2
        db.delete.assert_has_calls([call(inv1), call(inv3)], any_order=False)

    def test_all_verified_deletes_nothing(self):
        invoices = [_make_invoice(i, verified=True) for i in range(1, 4)]
        db = _make_db(invoices)
        result = bulk_delete_invoices(BulkDeleteRequest(ids=[1, 2, 3]), db)
        assert result["deleted"] == 0
        assert set(result["skipped"]) == {1, 2, 3}
        db.delete.assert_not_called()
