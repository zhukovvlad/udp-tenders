import base64
import json
import logging
import os
from datetime import date

import httpx
from sqlalchemy.orm import Session

import crud

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — парсер счетов-фактур и УПД (универсальных передаточных документов) для строительных материалов.

ШАГ 1: Определи тип документа.
- Если это счёт-фактура (СФ) или УПД — doc_type = "invoice"
- Если это что-то другое (акт, накладная, письмо, мусор) — doc_type = "unknown"

ШАГ 2: Если doc_type = "invoice", извлеки данные. В одном PDF может быть НЕСКОЛЬКО счетов-фактур.

Верни ТОЛЬКО валидный JSON (без markdown-обёртки):

{
  "doc_type": "invoice",
  "invoices": [
    {
      "number": "номер СФ",
      "date": "YYYY-MM-DD",
      "supplier_name": "название поставщика",
      "supplier_inn": "ИНН или null",
      "vat_rate": 20,
      "confidence": 0.92,
      "confidence_reason": "почему именно такая уверенность (1-2 коротких предложения)",
      "items": [
        {
          "raw_name": "полное наименование из документа как есть",
          "item_type": "material",
          "calc_role": "base",
          "material_class": "В40",
          "material_type": "concrete",
          "quantity": 7.0,
          "unit": "м3",
          "unit_price": 8500.00,
          "amount": 59500.00,
          "vat_amount": 9916.67,
          "confidence": 0.95
        }
      ]
    }
  ]
}

Если doc_type = "unknown":
{
  "doc_type": "unknown"
}

Правила:
- Дату в формат YYYY-MM-DD
- item_type: "material" — все материальные позиции: бетон, арматура, присадки, цементное молоко, проволока и др.; "delivery" — доставка, перевозка, автобетоносмеситель; "other" — только скидки, возвраты и корректировки
- calc_role: роль позиции в расчёте стоимости (только для item_type="material"):
  - "base" — первичный отслеживаемый материал: бетон (В15..В50), арматура (А500С, А240, А300), а также любой другой самостоятельный строительный материал (раствор, кирпич, металлопрокат и т.п.) с material_type="other"
  - "additive" — добавка, пропорционально входящая в стоимость основного материала (не самостоятельный товар, а улучшитель смеси): пластификатор, гидрофобизатор, противоморозная добавка, ускоритель твердения; на практике встречается только в бетонных СФ
  - "exclude" — сопутствующие позиции и услуги, которые не формируют стоимость материала и не распределяются пропорционально: цементное молоко, простой миксера, мойка миксера, проволока вязальная, разовые услуги и любые позиции, не являющиеся частью самого материала
  - null — для item_type="delivery" и item_type="other"
- material_class: для бетона и арматуры (calc_role="base") — ТОЛЬКО короткое обозначение класса: "В40", "В30", "А500С" — НЕ полная спецификация "В40 П4 F200 W12"; для добавок (calc_role="additive") — короткое торговое название: "Пластификатор", "Гидрофобизатор", "Противоморозная добавка"; для exclude — используй СТРОГО эти канонические имена: бетонная тематика→ "Цементное молоко", "Простой миксера", "Мойка миксера"; арматурная тематика→ "Проволока вязальная"; для доставки и прочего — null
- material_type: "concrete" для бетонной тематики (включая присадки и цементное молоко), "rebar" для арматурной тематики (включая проволоку), "other" для прочих материалов; null для доставки
- quantity, unit_price, amount — числа с плавающей точкой

КРИТИЧЕСКИ ВАЖНО про цены и суммы — БЕРИ ИХ ИЗ ДОКУМЕНТА КАК ЕСТЬ, НИЧЕГО НЕ ПЕРЕСЧИТЫВАЙ:
В стандартной форме счёта-фактуры РФ есть фиксированные графы. Сопоставление:
- quantity      ← графа 3 «Количество (объём)»
- unit          ← графа 2а «Условное обозначение (национальное)»
- unit_price    ← графа 4 «Цена (тариф) за единицу измерения» (БЕЗ НДС)
- amount        ← графа 5 «Стоимость товаров (работ, услуг) без налога — всего» (БЕЗ НДС)
- vat_amount    ← графа 8 «Сумма налога, предъявляемая покупателю»

ЗАПРЕЩЕНО:
- складывать amount + vat_amount и класть в amount — оставь amount без налога
- умножать unit_price на (1 + vat_rate/100) — отдай как напечатано
- использовать графу 9 «Стоимость с налогом — всего» вместо графы 5

Если документ нестандартный (УПД свободной формы, без явной графы «без налога») и колонки разделить не удаётся — бери ту цену, что напечатана в строке позиции, как есть, и в confidence_reason укажи, что цены могут быть с НДС.

САМОПРОВЕРКА (для повышения качества): после извлечения проверь, что amount ≈ quantity × unit_price (допуск ±2% на округления). Если сильно расходится — снижай confidence этой позиции и опиши причину в confidence_reason родителя.

КРИТИЧЕСКИ ВАЖНО про позиции (items):
- КАЖДАЯ СТРОКА из табличной части документа = ОТДЕЛЬНАЯ позиция в массиве items
- НИКОГДА не сливай две или более строк в одну позицию, даже если у них одинаковое наименование, цена или единица измерения
- НИКОГДА не суммируй количество, сумму или НДС из нескольких строк
- Если в документе 5 строк "Бетонная смесь БСТ В40" — в JSON должно быть РОВНО 5 объектов в items
- Если строки выглядят одинаково, но напечатаны отдельными строками таблицы — они остаются отдельными позициями
- Сохраняй порядок позиций тот же, что и в документе

ПРО CONFIDENCE (уверенность):
- confidence на уровне СФ — твоя честная оценка от 0.0 до 1.0, насколько ты уверен в правильности всех извлечённых полей этой СФ. Учитывай: качество скана, читаемость табличной части, соответствие сумм, наличие всех ключевых полей, потенциальные ошибки OCR
- confidence на уровне item — уверенность именно в этой позиции (особенно в цифрах: цена, количество, сумма)
- 0.95–1.0 — текст идеально читаем, все поля извлечены, итоговые суммы сходятся
- 0.80–0.94 — мелкие сомнения (нечёткий символ в номере, спорный класс материала, частичное соответствие сумм)
- 0.60–0.79 — заметные пробелы (часть полей пришлось угадывать, плохой скан, неоднозначные значения)
- ниже 0.60 — серьёзные сомнения, данные могут быть неверны
- НЕ завышай confidence ради красивого числа. Если значение угадано или восстановлено по контексту — снижай уверенность
- confidence_reason — кратко и по делу укажи, что именно вызывает неуверенность, либо "все поля читаются чётко"
"""

# Если переменная окружения задана пустой строкой ("OPENROUTER_BASE_URL=" в .env),
# os.getenv вернёт "" — это даст relative URL "/chat/completions" и тихо сломает
# httpx-вызовы. Используем "or", чтобы пустая строка считалась отсутствием значения.
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
OPENROUTER_URL = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"


async def parse_invoice_pdf(file_data: bytes, db: Session, document_id: int) -> dict:
    """Parse PDF via OpenRouter API. Returns structured data and creates DB entities."""
    logger.info(f"[doc={document_id}] Старт парсинга, размер PDF: {len(file_data)} байт ({len(file_data)/1024:.1f} КБ)")

    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.error(f"[doc={document_id}] API-ключ OpenRouter не настроен")
            return {"error": "API-ключ OpenRouter не настроен"}

        model = os.getenv("AI_MODEL", "anthropic/claude-sonnet-4.6")
        logger.info(f"[doc={document_id}] Модель: {model}")

        pdf_base64 = base64.b64encode(file_data).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Engine для парсинга PDF: "native" — модель видит PDF как изображения (для multimodal моделей),
        # "mistral-ocr" — OCR через Mistral ($2/1000 страниц, лучше для сканов и табличных бланков),
        # "pdf-text" — извлечение чистого текста (бесплатно, ломается на табличных формах СФ).
        pdf_engine = os.getenv("PDF_ENGINE", "mistral-ocr")

        payload = {
            "model": model,
            "max_tokens": 8192,
            "plugins": [
                {
                    "id": "file-parser",
                    "pdf": {"engine": pdf_engine},
                }
            ],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "file": {
                                "filename": "document.pdf",
                                "file_data": f"data:application/pdf;base64,{pdf_base64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Определи тип документа и извлеки данные. "
                                "ВАЖНО: каждая строка из табличной части — это отдельная позиция в items. "
                                "Не объединяй и не суммируй строки, даже если они выглядят одинаково."
                            ),
                        },
                    ],
                },
            ],
        }
        logger.info(f"[doc={document_id}] PDF engine: {pdf_engine}")

        logger.info(f"[doc={document_id}] Отправка запроса в OpenRouter...")
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=payload)

        if response.status_code != 200:
            logger.error(f"[doc={document_id}] OpenRouter вернул {response.status_code}: {response.text[:500]}")
            return {"error": f"OpenRouter API ошибка: {response.status_code} — {response.text}"}

        data = response.json()
        usage = data.get("usage", {})
        logger.info(
            f"[doc={document_id}] OpenRouter ответ получен. "
            f"Токены: prompt={usage.get('prompt_tokens', '?')}, "
            f"completion={usage.get('completion_tokens', '?')}, "
            f"total={usage.get('total_tokens', '?')}"
        )

        response_text = data["choices"][0]["message"]["content"]
        logger.debug(f"[doc={document_id}] Сырой ответ модели:\n{response_text}")

        # Strip markdown wrapper
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        try:
            parsed = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"[doc={document_id}] Невалидный JSON от модели: {e}\nТекст: {response_text[:1000]}")
            return {"error": "Не удалось разобрать ответ модели (невалидный JSON)"}

        doc_type = parsed.get("doc_type")
        logger.info(f"[doc={document_id}] doc_type={doc_type}, invoices в ответе: {len(parsed.get('invoices', []))}")

        if doc_type != "invoice":
            logger.warning(f"[doc={document_id}] Документ классифицирован как '{doc_type}', не СФ")
            return {"doc_type": "unknown", "error": "Документ не является счётом-фактурой"}

        # Process each invoice
        invoices_created = []
        for inv_idx, inv_data in enumerate(parsed.get("invoices", [])):
            model_conf = inv_data.get("confidence")
            completeness = _calculate_completeness(inv_data)
            confidence = _final_confidence(model_conf, completeness)
            inv_number = inv_data.get("number", "?")
            items_count = len(inv_data.get("items", []))
            reason = inv_data.get("confidence_reason", "")
            logger.info(
                f"[doc={document_id}] СФ #{inv_idx + 1}: №{inv_number}, "
                f"дата={inv_data.get('date')}, поставщик={inv_data.get('supplier_name')}, "
                f"позиций={items_count}, model_conf={model_conf}, completeness={completeness}, "
                f"final={confidence}, reason='{reason}'"
            )

            items = []
            for item_idx, item in enumerate(inv_data.get("items", [])):
                material_class_id = None
                if item.get("item_type") == "material" and not item.get("material_class"):
                    logger.warning(
                        "[doc=%d] СФ №%s поз.%d '%s': item_type=material, но material_class пустой — "
                        "позиция сохранится без класса материала",
                        document_id, inv_number, item_idx + 1,
                        item.get("raw_name", "")[:40],
                    )
                if item.get("item_type") == "material" and item.get("material_class"):
                    raw_role = str(item.get("calc_role") or "base").strip().lower()
                    if raw_role not in crud.VALID_CALC_ROLES:
                        logger.warning(
                            "[doc=%d] СФ №%s поз.%d '%s': неизвестный calc_role=%r от модели, "
                            "используем 'base'",
                            document_id, inv_number, item_idx + 1,
                            item.get("raw_name", "")[:40], raw_role,
                        )
                        raw_role = "base"
                    mc = crud.get_or_create_material_class(
                        db,
                        name=item["material_class"],
                        material_type=item.get("material_type", "other"),
                        calc_role=raw_role,
                    )
                    material_class_id = mc.id

                qty = float(item.get("quantity") or 0)
                price = float(item.get("unit_price") or 0)
                amount = float(item.get("amount") or 0)

                # Предупреждаем если значения подозрительные
                if qty <= 0 or amount <= 0:
                    logger.warning(
                        f"[doc={document_id}] СФ№{inv_number} поз.{item_idx + 1} '{item.get('raw_name', '')[:50]}': "
                        f"qty={qty}, price={price}, amount={amount} — нулевые значения"
                    )

                items.append({
                    "raw_name": item.get("raw_name") or "",
                    "item_type": item.get("item_type") or "other",
                    "material_class_id": material_class_id,
                    "quantity": qty,
                    "unit": item.get("unit"),
                    "unit_price": price,
                    "amount": amount,
                    "vat_amount": item.get("vat_amount"),
                })

            try:
                invoice_date_str = inv_data.get("date")
                if not invoice_date_str:
                    raise ValueError("Дата СФ отсутствует в ответе модели")
                invoice_date = date.fromisoformat(invoice_date_str)
            except (ValueError, TypeError) as e:
                logger.error(f"[doc={document_id}] СФ №{inv_number}: некорректная дата '{inv_data.get('date')}': {e}")
                continue

            invoice = crud.create_invoice(
                db,
                document_id=document_id,
                number=inv_data.get("number", ""),
                invoice_date=invoice_date,
                supplier_name=inv_data.get("supplier_name", ""),
                supplier_inn=inv_data.get("supplier_inn"),
                vat_rate=inv_data.get("vat_rate", 20),
                confidence=confidence,
                items=items,
            )
            invoices_created.append(invoice.id)
            logger.info(f"[doc={document_id}] СФ №{inv_number} сохранена в БД (id={invoice.id})")

        logger.info(f"[doc={document_id}] Парсинг завершён, создано СФ: {len(invoices_created)}")
        return {"doc_type": "invoice", "invoices_created": invoices_created}

    except httpx.TimeoutException:
        logger.exception(f"[doc={document_id}] Таймаут запроса к OpenRouter")
        return {"error": "Таймаут запроса к OpenRouter (180с)"}
    except Exception as e:
        logger.exception(f"[doc={document_id}] Неожиданная ошибка парсинга")
        return {"error": f"Ошибка парсинга: {str(e)}"}


def _calculate_completeness(inv_data: dict) -> float:
    """Доля заполненности ключевых полей (0.0-1.0). Сигнализирует о пропусках,
    которые модель сама могла не заметить."""
    score = 0
    total = 0

    total += 1
    if inv_data.get("number"):
        score += 1

    total += 1
    if inv_data.get("date"):
        try:
            date.fromisoformat(inv_data["date"])
            score += 1
        except (ValueError, TypeError):
            pass

    total += 1
    if inv_data.get("supplier_name"):
        score += 1

    items = inv_data.get("items", [])
    total += 1
    if items:
        score += 1

    for item in items:
        total += 4
        if item.get("raw_name"):
            score += 1
        if item.get("quantity") and item["quantity"] > 0:
            score += 1
        if item.get("unit_price") and item["unit_price"] > 0:
            score += 1
        if item.get("amount") and item["amount"] > 0:
            score += 1

    return round(score / total, 2) if total > 0 else 0


def _final_confidence(model_conf, completeness: float) -> float:
    """Итоговая уверенность = минимум из (оценка модели) и (полнота данных).
    Если модель не вернула confidence — используем только completeness."""
    try:
        mc = float(model_conf) if model_conf is not None else None
    except (TypeError, ValueError):
        mc = None

    if mc is None:
        return round(completeness, 2)

    # Зажимаем в диапазон [0, 1] на случай, если модель вернёт 95 вместо 0.95 или > 1
    if mc > 1:
        mc = mc / 100 if mc <= 100 else 1.0
    mc = max(0.0, min(1.0, mc))

    # Берём минимум: модель не может быть увереннее, чем заполнено полей
    return round(min(mc, completeness), 2)
