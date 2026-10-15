"""Глобальная сериализация вызовов PDFium.

PDFium не допускает одновременных вызовов из разных потоков даже для разных документов
(https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading),
а растеризация уходит в worker-потоки (anyio.to_thread) и идёт параллельно для нескольких
документов. Поэтому любая работа с pypdfium2 — только внутри `open_pdfium`: документ
открывается и закрывается под одним локом, страницы/bitmap'ы закрываются явно до выхода,
чтобы финализаторы pypdfium2 не дёрнули PDFium из другого потока при сборке мусора.
"""
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pypdfium2 as pdfium

PDFIUM_LOCK = threading.Lock()


@contextmanager
def open_pdfium(pdf_bytes: bytes) -> Iterator[pdfium.PdfDocument]:
    """Открыть PdfDocument под глобальным локом PDFium; закрыть до снятия лока."""
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            yield doc
        finally:
            doc.close()


def render_page_to(doc: pdfium.PdfDocument, index: int, write, **render_kwargs) -> None:
    """Отрендерить страницу и отдать PIL-картинку в write(img) ДО закрытия bitmap.

    to_pil() разделяет буфер с bitmap, поэтому кодирование (JPEG/PDF) должно
    произойти до bitmap.close(); вызывать только внутри `open_pdfium`.
    """
    page = doc[index]
    try:
        bitmap = page.render(**render_kwargs)
        try:
            write(bitmap.to_pil())
        finally:
            bitmap.close()
    finally:
        page.close()
