# 2026-10-15 — Исчерпание пула БД при массовой загрузке, сжатие тяжёлых PDF

**Ветка:** `fix/db-pool-exhaustion-bulk-upload`
**PR:** [#49](https://github.com/zhukovvlad/udp-tenders/pull/49) (5 коммитов, merge `c6ea4c7`)
**Метод:** разбор `backend/logs/errors.log` → systematic debugging → TDD; внешнее ревью — Codex и владелец

## Задача

14.10 массовая загрузка ~130 УПД положила бэкенд: `QueuePool limit of size 5 overflow 10 reached`,
запросы висели по 60+ с и отдавали 500, 7 документов ушли в `error` с «Внутренняя ошибка обработки»,
ещё 7 зависших в `processing` перевёл в `error` startup-sweep после рестарта. Параллельно один скан
(doc=19, 44 МБ) пять раз подряд получил `OpenRouter API ошибка: 400` — причина в логах не читалась.

## Что сделано

1. **Соединение запроса не живёт во время фоновой обработки** (`8c58e43`). FastAPI 0.139 закрывает
   зависимость `get_db` только **после** `BackgroundTasks` (`fastapi/routing.py`: request-стек
   выходит после `await response(...)`, а Starlette исполняет фоновые таски внутри него). Каждый
   `upload`/`reparse`/`deskew-reparse` держал соединение весь LLM-вызов; 15 загрузок — пул пуст.
   Хуже того, синхронный `pool.connect()` из async-кода (`persist_parse_result`) блокировал event
   loop на 30 с, а держатели соединений сами ждали loop — взаимоблокировка до таймаута, цикл ~70 с.
   Фикс: `_serialize_and_release` → `db.rollback()` перед возвратом 202.
2. **Лимит параллелизма обработки** (`8c58e43`): `process_document` под `asyncio.Semaphore`
   (`PROCESSING_CONCURRENCY`, дефолт 4, на процесс; семафор — на event loop, `WeakKeyDictionary`).
   Ожидание слота внутри `try`: отмена в очереди → терминальный error, как и в обработке.
3. **Тело ошибки OpenRouter в логе** (`8757973`): warning с кодом, размером payload и телом ответа
   (до 1000 символов). Сразу показал причину 400: запрос 58.8 МБ, а провайдеры режут на 30–32 МБ
   (Google 30, Azure 32, Anthropic — `413 request_too_large`).
4. **Сжатие PDF сверх лимита** (`f7eec5e`, новый `pdf_compress.py`). PDF > 20 МБ постранично
   растрируется в grayscale-JPEG (200 dpi/q80 → 150 dpi/q70) в фазе A; оригинал в S3 и `file_hash`
   не меняются. Не влез / битый → `PermanentError` без платного вызова. doc=19: три страницы-скана
   по ~15 МБ без сжатия → 44.1 → 0.85 МБ за 1.1 с, разбор успешен (confidence 0.93, $0.028).
5. **Ревью-раунд** (`f266b89`, `eae8fcf`):
   - **PDFium не потокобезопасен даже для разных документов**, а сжатие и deskew-растр шли в
     worker-потоках параллельно. Новый `pdfium_sync.py`: `open_pdfium` держит глобальный
     `PDFIUM_LOCK` всё время жизни документа, `render_page_to` кодирует картинку до
     `bitmap.close()` (`to_pil()` разделяет буфер) и явно закрывает bitmap/страницу под локом,
     чтобы финализатор pypdfium2 не дёрнул PDFium из другого потока. Переведены `pdf_compress` и
     `pdf_orientation` (гонка в deskew была и до PR).
   - `upload_pdf` коммитит читающую транзакцию перед `await upload_file_async` и перед удалением
     S3-сироты в дедуп-гонке — соединение не висит на сетевом await.
   - `pdf_bytes` больше не передаётся в фоновую таску: ждущая слота таска держала бы весь PDF;
     оригинал скачивается из S3 уже внутри слота.

## Верификация

- Регресс-тест `test_request_session_released_before_background_processing` (×3 эндпоинта) падал
  до фикса (`in_transaction() == True` в момент фона).
- `test_processing_concurrency.py` (пик параллелизма, отмена в очереди), `test_pdf_compress.py`,
  `test_pdfium_sync.py` (открытие/рендер ассертят `PDFIUM_LOCK.locked()` во всех трёх путях +
  параллельное сжатие 8 PDF в 4 потоках совпадает с последовательным),
  `test_upload_releases_db_connection_before_s3_upload`.
- Ручной прогон doc=19 через настоящий OpenRouter (без записи в БД).
- `just lint`, `just test`: backend 735 passed, frontend 222 passed; CI зелёный.

## Решения и нюансы

- `Depends(get_db, scope="function")` не подходит: scope входит в cache key зависимости, и
  `get_current_user` держал бы свою request-scoped сессию до конца фона.
- `rollback`, а не `close` в `_serialize_and_release`: `close` отвязывает ORM-объекты (в тестах —
  объекты фабрик, `DetachedInstanceError`). Перед S3 в `upload_pdf` — `commit`: транзакция только
  читала, а `rollback` откатывал бы flush'нутые фабрикой данные в тестах.
- Сжатый PDF сохраняется с `deterministic_id=True`: иначе qpdf пишет `/ID` от времени, и
  параллельный тест ложно видел расхождение.
- `alembic/env.py` → `fileConfig(disable_existing_loggers=True)` в тестах с миграциями гасит уже
  созданные логгеры — тест на warning включает `llm_openrouter` обратно через monkeypatch.
- По ходу диагностики скрипт открыл БД по `DATABASE_URL` из `.env` (Neon) вместо `udp_dev` —
  только чтение, упало по таймауту. Для разовых скриптов строку брать как `just`
  (`postgresql+psycopg://postgres@localhost:5459/udp_dev`).

## Что осталось

- Синхронная БД в async-коде всё ещё блокирует loop, если пул всё-таки исчерпается
  (TECH_DEBT: переход на async SQLAlchemy).
- Нет лимита размера upload (TECH_DEBT): файл на время запроса целиком в памяти.
- Упавшие 14.10 документы и doc=19 — переразобрать вручную после рестарта бэкенда.
