"""Unit tests for supplier deduplication logic (без БД)."""
from rapidfuzz import fuzz

from tests.factories import SupplierFactory


def _find_duplicate_pairs(suppliers: list, threshold: float = 85.0) -> list[tuple]:
    """Чистая функция: сравнивает имена поставщиков по WRatio и возвращает пары."""
    pairs = []
    for i in range(len(suppliers)):
        for j in range(i + 1, len(suppliers)):
            a = suppliers[i]
            b = suppliers[j]
            score = fuzz.WRatio(a.name, b.name)
            if score >= threshold:
                pairs.append((a, b, float(score)))
    return pairs


def test_find_duplicate_pairs_empty():
    assert _find_duplicate_pairs([]) == []


def test_find_duplicate_pairs_single():
    assert _find_duplicate_pairs([SupplierFactory.build(id=1, name="ООО Бетон")]) == []


def test_find_duplicate_pairs_identical_names():
    a = SupplierFactory.build(id=1, name="ООО СтройБетон")
    b = SupplierFactory.build(id=2, name="ООО СтройБетон")
    pairs = _find_duplicate_pairs([a, b])
    assert len(pairs) == 1
    assert pairs[0][0].id == 1
    assert pairs[0][1].id == 2
    assert pairs[0][2] == 100.0


def test_find_duplicate_pairs_finds_similar():
    a = SupplierFactory.build(id=1, name="ООО СтройБетон")
    b = SupplierFactory.build(id=2, name="ООО Строй Бетон")          # токены те же, пробел лишний
    c = SupplierFactory.build(id=3, name="ЗАО Металл Трейд")         # совсем другое
    pairs = _find_duplicate_pairs([a, b, c])
    assert len(pairs) == 1
    pair_ids = {pairs[0][0].id, pairs[0][1].id}
    assert pair_ids == {1, 2}


def test_find_duplicate_pairs_below_threshold():
    a = SupplierFactory.build(id=1, name="ООО СтройКомплект")
    b = SupplierFactory.build(id=2, name="ЗАО РосМеталл")
    pairs = _find_duplicate_pairs([a, b], threshold=85.0)
    assert pairs == []


def test_find_duplicate_pairs_custom_threshold():
    a = SupplierFactory.build(id=1, name="ООО Бетон")
    b = SupplierFactory.build(id=2, name="ООО Бетоны")
    # При пороге 50 должны найтись, при 100 — нет
    pairs_50 = _find_duplicate_pairs([a, b], threshold=50.0)
    pairs_100 = _find_duplicate_pairs([a, b], threshold=100.0)
    assert len(pairs_50) == 1
    assert len(pairs_100) == 0


def test_find_duplicate_pairs_n_pairs():
    """При 3 схожих строках должно быть 3 пары."""
    suppliers = [SupplierFactory.build(id=i, name=f"ООО Бетон {i}") for i in range(3)]
    pairs = _find_duplicate_pairs(suppliers, threshold=50.0)
    assert len(pairs) == 3
