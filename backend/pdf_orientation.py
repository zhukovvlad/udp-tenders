"""On-demand коррекция ориентации страниц PDF: vision-детект + селективный raster.

Используется эндпоинтом deskew-reparse. См. спеку
docs/superpowers/specs/2026-06-15-pdf-orientation-deskew-design.md.
"""
import base64
import io
import json
import logging
import re

import httpx
import pikepdf
import pypdfium2 as pdfium
from fastapi import HTTPException
from PIL import Image

from config import settings
from pdf_parser import OPENROUTER_URL

logger = logging.getLogger(__name__)

MAX_DESKEW_PAGES = 20
DPI_CAP = 300
DPI_FLOOR = 150
DPI_DEFAULT = 200  # born-digital без вшитого растра


def _target_dpi(page: pikepdf.Page) -> int:
    """Native-aware целевой DPI для полностраничного скана.

    target_dpi ≈ image_px_width / (page_width_pt / 72), с полом DPI_FLOOR и капом DPI_CAP.
    Допущение: картинка занимает весь лист (наш кейс). Если вшитого растра нет —
    DPI_DEFAULT (born-digital, lossy-ограничение зафиксировано в спеке).
    """
    width_pt = float(page.mediabox[2]) - float(page.mediabox[0])
    if width_pt <= 0:
        return DPI_DEFAULT
    px_widths = []
    for obj in page.images.values():
        try:
            px_widths.append(pikepdf.PdfImage(obj).width)
        except Exception:  # noqa: BLE001 — нестандартный XObject не должен ронять deskew
            continue
    if not px_widths:
        return DPI_DEFAULT
    dpi = max(px_widths) / (width_pt / 72.0)
    return max(DPI_FLOOR, min(DPI_CAP, round(dpi)))


def _page_to_image_pdf(src_pdf: pdfium.PdfDocument, index: int, delta: int, target_dpi: int) -> bytes:
    """Отрендерить страницу в исправленной ориентации (grayscale) и обернуть в 1-страничный PDF.

    target_dpi используется ДВАЖДЫ: как scale рендера и как resolution записи image→PDF,
    иначе Pillow пишет 72 DPI/пиксель и mediabox раздувается.
    """
    page = src_pdf[index]
    img = page.render(scale=target_dpi / 72.0, rotation=delta, grayscale=True).to_pil()
    out = io.BytesIO()
    img.save(out, format="PDF", resolution=float(target_dpi))
    return out.getvalue()


def apply_rotations(pdf_bytes: bytes, rotations: list[int]) -> bytes:
    """Селективная raster-коррекция: перерисовываем только страницы с ненулевым поворотом,
    прямые переносим как есть. Пересобираем смешанный документ через pikepdf."""
    src_pikepdf = pikepdf.open(io.BytesIO(pdf_bytes))
    src_pdfium = pdfium.PdfDocument(pdf_bytes)
    result = pikepdf.new()
    keepalive = []  # foreign-PDF должны жить до result.save() (иначе copy_foreign может оборваться)
    for i, page in enumerate(src_pikepdf.pages):
        delta = rotations[i] % 360 if i < len(rotations) else 0
        if delta == 0:
            result.pages.append(page)  # как есть, без перерисовки
            continue
        target_dpi = _target_dpi(page)
        img_pdf = pikepdf.open(io.BytesIO(_page_to_image_pdf(src_pdfium, i, delta, target_dpi)))
        keepalive.append(img_pdf)
        result.pages.append(img_pdf.pages[0])
        last = result.pages[-1]
        if "/Rotate" in last:          # пиксели уже прямые — флаг не нужен
            del last["/Rotate"]        # словарный интерфейс (надёжнее атрибутного)
    buf = io.BytesIO()
    result.save(buf)
    return buf.getvalue()


DETECT_TIMEOUT = 30.0
_DETECT_PROMPT = (
    "На вход — страницы PDF по порядку. Для КАЖДОЙ страницы определи поворот по часовой "
    "стрелке (0, 90, 180 или 270 градусов), который сделает её вертикально читаемой. "
    "Верни ТОЛЬКО JSON-массив целых чисел длиной по числу страниц, например [0,90,0]."
)


def render_pages_for_detect(pdf_bytes: bytes, long_side: int = 768) -> list[bytes]:
    """Уменьшенные JPEG-страницы для vision-детекта (ориентации хватает низкого разрешения)."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    images: list[bytes] = []
    for page in pdf:
        w, h = page.get_size()
        scale = long_side / max(w, h)
        img = page.render(scale=scale, grayscale=True).to_pil()
        out = io.BytesIO()
        img.convert("L").save(out, format="JPEG", quality=70)
        images.append(out.getvalue())
    return images


async def detect_rotations(images: list[bytes]) -> list[int]:
    """Один vision-запрос: per-page поворот 0/90/180/270. Любой сбой парсинга → нули."""
    n = len(images)
    if n > MAX_DESKEW_PAGES:
        raise HTTPException(status_code=413, detail=f"Слишком много страниц для коррекции (> {MAX_DESKEW_PAGES})")
    content = [{"type": "text", "text": _DETECT_PROMPT}]
    for img in images:
        b64 = base64.b64encode(img).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    payload = {
        "model": settings.AI_MODEL,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(DETECT_TIMEOUT, connect=5.0)  # быстрый фейл на коннекте, долгий read
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        # транспортный сбой / таймаут / не-2xx → НЕ деградируем в нули (иначе переразберём
        # оригинал под видом «исправлено»), а сигналим 502; эндпоинт не тронет S3 и не переразберёт
        logger.warning(f"detect_rotations: vision-запрос упал: {e}")
        raise HTTPException(status_code=502, detail="Сервис распознавания ориентации недоступен")
    # успешный 200: непарсящееся СОДЕРЖИМОЕ → нули (безопасная деградация на уровне контента)
    try:
        text = resp.json()["choices"][0]["message"]["content"]
        m = re.search(r"\[[\d,\s]*\]", text)          # берём именно JSON-массив, не любые числа
        nums = json.loads(m.group(0)) if m else []
        allowed = {0, 90, 180, 270}
        rots = [v % 360 if (v % 360) in allowed else 0 for v in nums[:n]]
    except Exception:  # noqa: BLE001 — кривое содержимое не должно ронять эндпоинт
        rots = []
    rots += [0] * (n - len(rots))   # добиваем до длины n
    return rots
