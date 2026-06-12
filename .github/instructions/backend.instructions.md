---
applyTo: "backend/**"
---
# Backend

- Только `just`-команды, не `cd backend && ...`.
- Финансы — `Decimal` end-to-end, не `float`. Колонки БД — `Numeric`. Округление — `money_round` из `finance.py` (ROUND_HALF_UP). Вход LLM→DB нормализуй через `Decimal(str(value))`.
- `Invoice.vat_rate` не NOT NULL → всегда `COALESCE(vat_rate, literal(Decimal("20.0")))` в SQL-выражениях.
- `DateTime` хранится как naive UTC. При ручной сериализации в dict-ответах добавляй `"Z"`: `dt.isoformat() + "Z"`. Pydantic-схемы делают это сами.
- CRUD разнесён по `crud/`: `projects`, `materials`, `units`, `documents`, `calculations`, `compensation_corridors`, `suppliers`, `supplier_exclusions`, `admin`. Логику БД — туда, не в роутеры.
- Единицы измерения: позиции счетов нормализуются при записи (`crud/units.py`); агрегация — по `normalized_quantity`. `material_type` в HTTP API — строковый код (`concrete`/`rebar`/`other`), в БД — FK `material_type_id`.
- Направления: параметр `direction` в HTTP API = код `material_types`; резолв и 422 — только через `routers/common.resolve_direction_type`. Фильтр направления в расчётах — строго на выходе (знаменатели разноски по полному счёту), см. `docs/agent/calculations.md`.
- Pydantic-модели запросов/ответов — в файлах роутеров. Логирование — `logging.getLogger(__name__)`.
- ruff line-length 120, target py3.12, правила E/F/I/B/UP/SIM. `Depends()` в аргументах — ок (B008 игнорится).
- Все эндпоинты требуют `get_current_user`. Org-level изоляция данных ещё не включена — см. `docs/TECH_DEBT.md`.

Глубже: методология расчётов — `docs/agent/calculations.md`; модели БД — `docs/agent/database.md`; auth — `docs/agent/auth.md`.
