"""Unit-тесты для crud/supplier_exclusions.py (без БД — чистые функции через mock)."""
from unittest.mock import MagicMock


def _make_db(rows=None):
    """Минимальный мок SQLAlchemy Session."""
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.all.return_value = rows or []
    return db


class TestGetExcludedSupplierIds:
    def test_returns_empty_set_when_no_exclusions(self):
        from crud.supplier_exclusions import get_excluded_supplier_ids

        db = _make_db(rows=[])
        result = get_excluded_supplier_ids(db, project_id=1)
        assert result == set()

    def test_returns_set_of_supplier_ids(self):
        from crud.supplier_exclusions import get_excluded_supplier_ids

        row1 = MagicMock()
        row1.supplier_id = 5
        row2 = MagicMock()
        row2.supplier_id = 12
        db = _make_db(rows=[row1, row2])
        result = get_excluded_supplier_ids(db, project_id=1)
        assert result == {5, 12}


class TestSetSupplierExcluded:
    def test_adds_exclusion_when_excluded_true(self):
        from crud.supplier_exclusions import set_supplier_excluded
        from models import ProjectSupplierExclusion

        db = MagicMock()
        existing_q = MagicMock()
        db.query.return_value = existing_q
        existing_q.filter.return_value = existing_q
        existing_q.first.return_value = None  # не существует

        set_supplier_excluded(db, project_id=1, supplier_id=7, excluded=True, reason="Аварийная закупка")

        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert isinstance(added, ProjectSupplierExclusion)
        assert added.project_id == 1
        assert added.supplier_id == 7
        assert added.reason == "Аварийная закупка"
        db.commit.assert_called_once()

    def test_noop_when_adding_already_existing_exclusion(self):
        from crud.supplier_exclusions import set_supplier_excluded

        db = MagicMock()
        existing_q = MagicMock()
        db.query.return_value = existing_q
        existing_q.filter.return_value = existing_q
        existing_q.first.return_value = MagicMock()  # уже существует

        set_supplier_excluded(db, project_id=1, supplier_id=7, excluded=True)

        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_deletes_exclusion_when_excluded_false(self):
        from crud.supplier_exclusions import set_supplier_excluded

        existing = MagicMock()
        db = MagicMock()
        existing_q = MagicMock()
        db.query.return_value = existing_q
        existing_q.filter.return_value = existing_q
        existing_q.first.return_value = existing

        set_supplier_excluded(db, project_id=1, supplier_id=7, excluded=False)

        db.delete.assert_called_once_with(existing)
        db.commit.assert_called_once()

    def test_noop_when_removing_nonexistent_exclusion(self):
        from crud.supplier_exclusions import set_supplier_excluded

        db = MagicMock()
        existing_q = MagicMock()
        db.query.return_value = existing_q
        existing_q.filter.return_value = existing_q
        existing_q.first.return_value = None  # нет записи

        set_supplier_excluded(db, project_id=1, supplier_id=7, excluded=False)

        db.delete.assert_not_called()
        db.commit.assert_not_called()
