"""Unit-тесты helper-функций pdf_parser."""
from pdf_parser import _calculate_completeness, _final_confidence


class TestCalculateCompleteness:
    def test_full_invoice_returns_one(self):
        inv_data = {
            "number": "СФ-1",
            "date": "2026-05-01",
            "supplier_name": "ООО Ромашка",
            "items": [
                {"raw_name": "Бетон В25", "quantity": 5, "unit_price": 8000, "amount": 40000},
            ],
        }
        assert _calculate_completeness(inv_data) == 1.0

    def test_empty_invoice_returns_low(self):
        inv_data = {"number": "", "date": "", "supplier_name": "", "items": []}
        # 4 поля по 1 баллу, все пустые → 0/4 = 0.0
        assert _calculate_completeness(inv_data) == 0.0

    def test_invalid_date_does_not_count(self):
        inv_data = {
            "number": "X",
            "date": "not-a-date",
            "supplier_name": "Y",
            "items": [],
        }
        # number=1, date=0 (невалидная), supplier=1, items=0 → 2/4 = 0.5
        assert _calculate_completeness(inv_data) == 0.5

    def test_item_with_zero_quantity_partial_credit(self):
        inv_data = {
            "number": "X",
            "date": "2026-05-01",
            "supplier_name": "Y",
            "items": [
                {"raw_name": "Что-то", "quantity": 0, "unit_price": 100, "amount": 100},
            ],
        }
        # 4 invoice-fields full + 4 item-fields, qty=0 → 1 балл потерян → 7/8 = 0.88
        assert _calculate_completeness(inv_data) == 0.88


class TestFinalConfidence:
    def test_takes_min_of_model_and_completeness(self):
        assert _final_confidence(0.95, 0.5) == 0.5
        assert _final_confidence(0.5, 0.95) == 0.5

    def test_handles_none_model_conf(self):
        assert _final_confidence(None, 0.7) == 0.7

    def test_normalizes_percent_scale(self):
        # Модель вернула 95 вместо 0.95 → должно нормализоваться
        assert _final_confidence(95, 1.0) == 0.95

    def test_clamps_above_one(self):
        assert _final_confidence(150, 1.0) == 1.0

    def test_clamps_below_zero(self):
        assert _final_confidence(-0.5, 1.0) == 0.0

    def test_invalid_model_conf_falls_back_to_completeness(self):
        assert _final_confidence("invalid", 0.7) == 0.7
