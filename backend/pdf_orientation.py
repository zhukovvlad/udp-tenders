"""On-demand коррекция ориентации страниц PDF: vision-детект + селективный raster.

Используется эндпоинтом deskew-reparse. См. спеку
docs/superpowers/specs/2026-06-15-pdf-orientation-deskew-design.md.
"""
import io
import logging

import pikepdf
import pypdfium2 as pdfium
from PIL import Image

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
