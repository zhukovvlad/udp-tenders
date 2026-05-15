"""Unit tests for supplier deduplication logic (без БД)."""
from types import SimpleNamespace

import crud


def _make(id_: int, name: str):
    s = SimpleNamespace()
    s.id = id_
    s.name = name
    return s


def test_find_duplicate_pairs_empty():
    assert crud._find_duplicate_pairs([]) == []


def test_find_duplicate_pairs_single():
    assert crud._find_duplicate_pairs([_make(1, "ООО Бетон")]) == []


def test_find_duplicate_pairs_identical_names():
    a = _make(1, "ООО СтройБетон")
    b = _make(2, "ООО СтройБетон")
    pairs = crud._find_duplicate_pairs([a, b])
    assert len(pairs) == 1
    assert pairs[0][0].id == 1
    assert pairs[0][1].id == 2
    assert pairs[0][2] == 100.0


def test_find_duplicate_pairs_finds_similar():
    a = _make(1, "ООО СтройБетон")
    b = _make(2, "ООО Строй Бетон")          # токены те же, пробел лишний
    c = _make(3, "ЗАО Металл Трейд")         # совсем другое
    pairs = crud._find_duplicate_pairs([a, b, c])
    assert len(pairs) == 1
    pair_ids = {pairs[0][0].id, pairs[0][1].id}
    assert pair_ids == {1, 2}


def test_find_duplicate_pairs_below_threshold():
    a = _make(1, "ООО СтройКомплект")
    b = _make(2, "ЗАО РосМеталл")
    pairs = crud._find_duplicate_pairs([a, b], threshold=85.0)
    assert pairs == []


def test_find_duplicate_pairs_custom_threshold():
    a = _make(1, "ООО Бетон")
    b = _make(2, "ООО Бетоны")
    # При пороге 50 должны найтись, при 100 — нет
    pairs_50 = crud._find_duplicate_pairs([a, b], threshold=50.0)
    pairs_100 = crud._find_duplicate_pairs([a, b], threshold=100.0)
    assert len(pairs_50) == 1
    assert len(pairs_100) == 0


def test_find_duplicate_pairs_n_pairs():
    """При 3 схожих строках должно быть 3 пары."""
    suppliers = [_make(i, f"ООО Бетон {i}") for i in range(3)]
    pairs = crud._find_duplicate_pairs(suppliers, threshold=50.0)
    assert len(pairs) == 3
