"""Сжатие PDF, не влезающего в лимит размера запроса к LLM.

Провайдеры за OpenRouter режут запрос на 30–32 МБ (Google 30, Azure 32, Anthropic —
413), а PDF уходит в base64 (+33 %). Несжатые сканы (~15 МБ на страницу) этот лимит
пробивают, поэтому такой PDF растрируется в grayscale-JPEG постранично. Оригинал в S3
не меняется — сжатая копия живёт только на время запроса.
"""
import io
import logging

import pikepdf
import pypdfium2 as pdfium

from pdfium_sync import open_pdfium, render_page_to

logger = logging.getLogger(__name__)

# Предел «сырого» PDF: base64 ×4/3 → ~26.7 МБ + промпт, с запасом до 30 МБ.
LLM_MAX_PDF_BYTES = 20_000_000
# Ступени (dpi, JPEG quality): от бережной к жёсткой; 150 dpi — нижняя граница
# читаемости мелких цифр в таблицах УПД.
SHRINK_STEPS: tuple[tuple[int, int], ...] = ((200, 80), (150, 70))


class PdfTooLargeError(Exception):
    """PDF не уложился в LLM_MAX_PDF_BYTES ни на одной ступени сжатия."""

    def __init__(self, size: int):
        """Запомнить наименьший достигнутый размер (байт) для сообщения пользователю."""
        super().__init__(f"PDF {size} байт > {LLM_MAX_PDF_BYTES} после сжатия")
        self.size = size


def _page_to_jpeg_pdf(src: pdfium.PdfDocument, index: int, dpi: int, quality: int) -> bytes:
    """Отрендерить страницу в grayscale и обернуть в 1-страничный PDF с JPEG (DCTDecode).

    dpi задаёт и scale рендера, и resolution записи — иначе Pillow пишет 72 DPI/пиксель
    и mediabox раздувается (тот же приём, что в pdf_orientation._page_to_image_pdf).
    Вызывать только внутри open_pdfium.
    """
    out = io.BytesIO()
    render_page_to(src, index,
                   lambda img: img.save(out, format="PDF", resolution=float(dpi), quality=quality),
                   scale=dpi / 72.0, grayscale=True)
    return out.getvalue()


def shrink_pdf(pdf_bytes: bytes, dpi: int, quality: int) -> bytes:
    """Пересобрать PDF из постраничных grayscale-JPEG; в памяти — только сжатые страницы.

    PDFium — под глобальным локом (растр страниц), сборка pikepdf — уже вне его.
    """
    with open_pdfium(pdf_bytes) as src:
        page_pdfs = [_page_to_jpeg_pdf(src, i, dpi, quality) for i in range(len(src))]
    result = pikepdf.new()
    keepalive = []  # foreign-PDF должны жить до result.save()
    try:
        for page_bytes in page_pdfs:
            page_pdf = pikepdf.open(io.BytesIO(page_bytes))
            keepalive.append(page_pdf)
            result.pages.append(page_pdf.pages[0])
        buf = io.BytesIO()
        result.save(buf, deterministic_id=True)  # /ID от содержимого, а не от времени — вывод воспроизводим
        return buf.getvalue()
    finally:
        for page_pdf in keepalive:
            page_pdf.close()
        result.close()


def fit_for_llm(pdf_bytes: bytes) -> bytes:
    """Вернуть PDF, укладывающийся в LLM_MAX_PDF_BYTES: как есть или сжатый.

    CPU-bound — вызывать через anyio.to_thread. Битый PDF → исключение pdfium/pikepdf
    (классифицирует вызывающий); не уложились ни на одной ступени → PdfTooLargeError.
    """
    if len(pdf_bytes) <= LLM_MAX_PDF_BYTES:
        return pdf_bytes
    smallest = len(pdf_bytes)
    for dpi, quality in SHRINK_STEPS:
        shrunk = shrink_pdf(pdf_bytes, dpi, quality)
        logger.info(f"PDF сжат для LLM: {len(pdf_bytes)} → {len(shrunk)} байт ({dpi} dpi, q{quality})")
        if len(shrunk) <= LLM_MAX_PDF_BYTES:
            return shrunk
        smallest = min(smallest, len(shrunk))
    raise PdfTooLargeError(smallest)
