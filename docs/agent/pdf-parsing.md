# Парсинг УПД (PDF)

Парсинг через OpenRouter API (`OPENROUTER_API_KEY`) в `pdf_parser.py`.

## Guard полноты разбора

`pdf_parser.parse_invoice_pdf` отклоняет разбор (возвращает `{"error": ...}`, строки не сохраняются) в двух случаях:

1. `finish_reason == "length"` в ответе API — модель упёрлась в лимит токенов, ответ обрезан.
2. `_reconcile_totals` обнаруживает расхождение между `SUM(item.amount)` и извлечённым из документа `doc_total_without_vat` («Всего к оплате» без НДС) сверх допуска `max(1 ₽, 0.1%)`.

Это предотвращает тихое сохранение неполного счёта (например 60 из 66 строк) под высоким confidence. Промпт содержит обязательный шаг самопроверки: модель сверяет `SUM(amount)` с `doc_total_without_vat` и ищет пропущенные строки перед закрытием JSON. `AI_MAX_TOKENS=64000` — верхний предел вывода claude-sonnet-4.6.

## Выбор движка

- **`PDF_ENGINE=native` (дефолт):** Claude смотрит на PDF как на изображения, промпт ~10k токенов — стабильнее на длинных СФ.
- **`mistral-ocr`:** ~24k токенов промпта (повторяющиеся шапки страниц), нестабилен на СФ с 60+ одинаковыми строками — пропускает или дублирует строки даже при `finish_reason=stop`.

Ещё не реализовано: постраничный chunking для СФ на 100+ строк — см. `docs/TECH_DEBT.md`.

## Нормализация единиц при записи

Парсер возвращает сырую строку `unit` и `material_type` code — **без изменений** (не нормализует). Нормализация выполняется в `create_invoice`:

1. `load_alias_map(db)` — загружает `unit_aliases` в память.
2. `normalize_item(item, alias_map)` — для каждой позиции находит `normalized_unit_id` по ключу `normalize_unit_key(raw_unit)`, вычисляет `normalized_quantity` и `normalized_unit_price`.
3. `get_or_create_material_class` резолвит `material_type` code → `material_type_id`; неизвестный code → 422 через API, в PDF-парсере — fallback на `"other"` с записью в лог (hallucinated code не обрывает обработку документа).

`normalize_unit_key` — единственный источник правды в `crud/units.py`: NFKC-нормализация (складывает м³→м3), collapse whitespace, lowercase, strip trailing dots. Используется в рантайме, миграции и тестах.
