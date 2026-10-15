"""Сжатие PDF, превышающего лимит размера запроса к LLM (pdf_compress)."""
import base64
import io
import random

import pikepdf
import pytest
from PIL import Image

import pdf_compress
from pdf_parser import parse_pdf
from processing import PermanentError


def _scan_pdf(pages: int = 2, px: tuple[int, int] = (1500, 1100), dpi: int = 300) -> bytes:
    """Тяжёлый «скан»: цветной шум с JPEG quality=100 — плохо сжимаемый, как несжатые сканы."""
    rnd = random.Random(42)
    images = [Image.frombytes("RGB", px, rnd.randbytes(px[0] * px[1] * 3)) for _ in range(pages)]
    out = io.BytesIO()
    images[0].save(out, format="PDF", resolution=float(dpi), quality=100,
                   save_all=True, append_images=images[1:])
    return out.getvalue()


@pytest.fixture(scope="module")
def scan_pdf() -> bytes:
    """Общий на модуль тяжёлый PDF (генерация шума небесплатна)."""
    return _scan_pdf()


def _mediaboxes(pdf_bytes: bytes) -> list[tuple[float, float]]:
    """Ширина/высота каждой страницы в pt."""
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        return [(float(p.mediabox[2]) - float(p.mediabox[0]), float(p.mediabox[3]) - float(p.mediabox[1]))
                for p in pdf.pages]


def test_shrink_pdf_reduces_size_and_keeps_pages(scan_pdf):
    """Сжатие уменьшает файл, сохраняет число страниц и их физический размер."""
    shrunk = pdf_compress.shrink_pdf(scan_pdf, dpi=150, quality=70)

    assert len(shrunk) < len(scan_pdf) / 3
    before, after = _mediaboxes(scan_pdf), _mediaboxes(shrunk)
    assert len(after) == len(before) == 2
    for (w0, h0), (w1, h1) in zip(before, after, strict=True):
        assert abs(w0 - w1) < 1 and abs(h0 - h1) < 1


def test_fit_for_llm_returns_small_pdf_unchanged(scan_pdf, monkeypatch):
    """PDF в пределах лимита возвращается как есть — без перекодирования."""
    monkeypatch.setattr(pdf_compress, "LLM_MAX_PDF_BYTES", len(scan_pdf))
    assert pdf_compress.fit_for_llm(scan_pdf) is scan_pdf


def test_fit_for_llm_falls_back_to_lower_quality(scan_pdf, monkeypatch):
    """Если первая ступень не уложилась в лимит — пробуется следующая, более жёсткая."""
    first = pdf_compress.shrink_pdf(scan_pdf, *pdf_compress.SHRINK_STEPS[0])
    monkeypatch.setattr(pdf_compress, "LLM_MAX_PDF_BYTES", len(first) - 1)

    result = pdf_compress.fit_for_llm(scan_pdf)

    assert len(result) < len(first)


def test_fit_for_llm_raises_when_still_too_large(scan_pdf, monkeypatch):
    """Не уложились ни на одной ступени → PdfTooLargeError с итоговым размером."""
    monkeypatch.setattr(pdf_compress, "LLM_MAX_PDF_BYTES", 1000)
    with pytest.raises(pdf_compress.PdfTooLargeError):
        pdf_compress.fit_for_llm(scan_pdf)


async def test_parse_pdf_sends_shrunk_pdf_when_oversized(scan_pdf, mock_openrouter, monkeypatch):
    """Фаза A: тяжёлый PDF уходит в LLM уже сжатым и в пределах лимита."""
    monkeypatch.setattr(pdf_compress, "LLM_MAX_PDF_BYTES", len(scan_pdf) // 3)

    outcome = await parse_pdf(scan_pdf, document_id=1)

    assert outcome.paid_calls == 1
    file_data = mock_openrouter.last_request_json()["messages"][1]["content"][0]["file"]["file_data"]
    sent = base64.b64decode(file_data.split(",", 1)[1])
    assert sent.startswith(b"%PDF") and len(sent) <= len(scan_pdf) // 3


async def test_parse_pdf_too_large_fails_without_llm_call(scan_pdf, mock_openrouter, monkeypatch):
    """Не сжимается до лимита → PermanentError с понятным текстом, платного вызова нет."""
    monkeypatch.setattr(pdf_compress, "LLM_MAX_PDF_BYTES", 1000)

    with pytest.raises(PermanentError, match="слишком большой") as ei:
        await parse_pdf(scan_pdf, document_id=1)

    assert ei.value.paid_calls == 0
    assert mock_openrouter.calls == []


async def test_parse_pdf_unreadable_oversized_fails_without_llm_call(mock_openrouter, monkeypatch):
    """Битый PDF сверх лимита → PermanentError «не удалось подготовить», без вызова LLM."""
    monkeypatch.setattr(pdf_compress, "LLM_MAX_PDF_BYTES", 10)

    with pytest.raises(PermanentError, match="подготовить"):
        await parse_pdf(b"not a pdf at all", document_id=1)

    assert mock_openrouter.calls == []
