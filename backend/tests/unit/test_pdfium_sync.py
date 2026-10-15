"""Все вызовы PDFium сериализованы глобальным локом (PDFium не потокобезопасен)."""
import io
import random
from concurrent.futures import ThreadPoolExecutor

import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image

import pdf_compress
import pdf_orientation as po
from pdfium_sync import PDFIUM_LOCK


def _image_pdf(pages: int = 2, px: tuple[int, int] = (600, 400)) -> bytes:
    """Небольшой PDF из картинок-страниц."""
    images = [Image.new("RGB", px, (200, 30 * i, 90)) for i in range(pages)]
    out = io.BytesIO()
    images[0].save(out, format="PDF", resolution=72.0, save_all=True, append_images=images[1:])
    return out.getvalue()


@pytest.fixture
def pdfium_calls(monkeypatch) -> list[str]:
    """Оборачивает открытие документа и рендер: каждый вызов обязан идти под PDFIUM_LOCK."""
    calls: list[str] = []
    real_doc, real_render = pdfium.PdfDocument, pdfium.PdfPage.render

    def guarded_doc(*args, **kwargs):
        """PdfDocument только под локом."""
        assert PDFIUM_LOCK.locked(), "PdfDocument открыт вне PDFIUM_LOCK"
        calls.append("open")
        return real_doc(*args, **kwargs)

    def guarded_render(self, *args, **kwargs):
        """render только под локом."""
        assert PDFIUM_LOCK.locked(), "render вызван вне PDFIUM_LOCK"
        calls.append("render")
        return real_render(self, *args, **kwargs)

    monkeypatch.setattr(pdfium, "PdfDocument", guarded_doc)
    monkeypatch.setattr(pdfium.PdfPage, "render", guarded_render)
    return calls


def test_shrink_pdf_uses_pdfium_under_lock(pdfium_calls):
    """Сжатие: открытие и рендер страниц — под глобальным локом."""
    pdf_compress.shrink_pdf(_image_pdf(), dpi=72, quality=70)
    assert pdfium_calls == ["open", "render", "render"]
    assert not PDFIUM_LOCK.locked()


def test_apply_rotations_uses_pdfium_under_lock(pdfium_calls):
    """Deskew-растр: рендер повёрнутой страницы — под глобальным локом."""
    po.apply_rotations(_image_pdf(pages=1), [90])
    assert pdfium_calls == ["open", "render"]
    assert not PDFIUM_LOCK.locked()


def test_render_pages_for_detect_uses_pdfium_under_lock(pdfium_calls):
    """Deskew-детект: рендер превью — под глобальным локом."""
    images = po.render_pages_for_detect(_image_pdf())
    assert len(images) == 2
    assert pdfium_calls == ["open", "render", "render"]
    assert not PDFIUM_LOCK.locked()


def test_concurrent_shrink_of_heavy_pdfs_is_consistent(monkeypatch):
    """Параллельное сжатие нескольких тяжёлых PDF в потоках даёт тот же результат, что последовательное."""
    rnd = random.Random(7)
    scans = [Image.frombytes("RGB", (1500, 1000), rnd.randbytes(1500 * 1000 * 3)) for _ in range(3)]
    buf = io.BytesIO()
    scans[0].save(buf, format="PDF", resolution=300.0, quality=100, save_all=True, append_images=scans[1:])
    heavy = buf.getvalue()
    monkeypatch.setattr(pdf_compress, "LLM_MAX_PDF_BYTES", len(heavy) - 1)
    expected = pdf_compress.fit_for_llm(heavy)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: pdf_compress.fit_for_llm(heavy), range(8)))

    assert all(r == expected for r in results)
    with pikepdf.open(io.BytesIO(expected)) as pdf:
        assert len(pdf.pages) == 3
