import io
import json

import httpx
import pikepdf
import pypdfium2 as pdfium
import pytest
import respx
from PIL import Image

import pdf_orientation as po

# Захватываем настоящий AsyncClient.send на импорте модуля (до autouse-гарда
# block_real_openrouter из conftest, который рубит любые вызовы к openrouter.ai на
# уровне send). respx работает на transport-уровне — через настоящий send проходит,
# поэтому в respx-тестах восстанавливаем его (тот же приём, что в фикстуре mock_openrouter).
_REAL_SEND = httpx.AsyncClient.send


@pytest.fixture
def _allow_respx(monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "send", _REAL_SEND)


def _image_pdf(px_w: int, px_h: int, dpi: float = 150.0, color=(255, 255, 255)) -> bytes:
    """PDF из одной картинки px_w×px_h (имитация полностраничного скана), сохранённой при `dpi`.

    Pillow при resolution=R делает страницу px/R дюймов, поэтому native-DPI страницы ≈ R —
    это и есть управляемый рычаг для проверки _target_dpi (пол/кап/совпадение)."""
    img = Image.new("RGB", (px_w, px_h), color)
    out = io.BytesIO()
    img.save(out, format="PDF", resolution=dpi)
    return out.getvalue()


def test_target_dpi_matches_native_within_cap():
    # Скан при 150 DPI (A4-подобный лист) → native ≈ 150, внутри [пол 150, кап 300].
    pdf = pikepdf.open(io.BytesIO(_image_pdf(1240, 1754, dpi=150.0)))
    dpi = po._target_dpi(pdf.pages[0])
    assert 150 <= dpi <= 300


def test_target_dpi_caps_at_300():
    # Скан при 400 DPI → native ≈ 400 → кап 300.
    pdf = pikepdf.open(io.BytesIO(_image_pdf(2000, 2800, dpi=400.0)))
    assert po._target_dpi(pdf.pages[0]) == 300


def test_target_dpi_floors_at_150():
    # Скан при 100 DPI → native ≈ 100 → пол 150.
    pdf = pikepdf.open(io.BytesIO(_image_pdf(800, 1100, dpi=100.0)))
    assert po._target_dpi(pdf.pages[0]) == 150


def _sideways_scan_pdf() -> bytes:
    """Картинка с маркер-полосой сверху, повёрнутая на 90° CW (полоса справа)."""
    img = Image.new("RGB", (800, 1000), (255, 255, 255))
    for y in range(100):           # верхняя полоса = маркер «верх»
        for x in range(800):
            img.putpixel((x, y), (0, 0, 0))
    sideways = img.rotate(-90, expand=True)  # PIL: отрицательный угол = по часовой
    out = io.BytesIO()
    sideways.save(out, format="PDF", resolution=150.0)
    return out.getvalue()


def _top_strip_is_dark(page_png: bytes) -> bool:
    img = Image.open(io.BytesIO(page_png)).convert("L")
    w, h = img.size
    band = img.crop((0, 0, w, h // 12))
    return sum(band.getdata()) / (band.size[0] * band.size[1]) < 64  # тёмная полоса сверху


def _render_first_page_png(pdf_bytes: bytes) -> bytes:
    pdf = pdfium.PdfDocument(pdf_bytes)
    img = pdf[0].render(scale=1.0).to_pil()
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_apply_rotations_sign_makes_upright():
    """Боковой скан (маркер справа) + корректирующий поворот → маркер снова сверху."""
    sideways = _sideways_scan_pdf()
    assert not _top_strip_is_dark(_render_first_page_png(sideways))  # до: не сверху
    corrected = po.apply_rotations(sideways, [270])  # 270° CW возвращает наверх
    assert _top_strip_is_dark(_render_first_page_png(corrected))     # после: сверху


def test_apply_rotations_resets_rotate_flag():
    """У пересобранной image-страницы /Rotate == 0 (не наследуется)."""
    src = pikepdf.open(io.BytesIO(_sideways_scan_pdf()))
    src.pages[0].Rotate = 90  # искусственный ненулевой флаг на исходнике
    buf = io.BytesIO(); src.save(buf)
    corrected = po.apply_rotations(buf.getvalue(), [270])
    out = pikepdf.open(io.BytesIO(corrected))
    assert int(out.pages[0].get("/Rotate", 0)) == 0


def test_apply_rotations_zero_delta_keeps_page_untouched():
    """Страница с delta==0 переносится как есть (не перерисовывается)."""
    two_pages = pikepdf.new()
    src = pikepdf.open(io.BytesIO(_sideways_scan_pdf()))
    two_pages.pages.append(src.pages[0])
    two_pages.pages.append(src.pages[0])
    buf = io.BytesIO(); two_pages.save(buf)
    corrected = po.apply_rotations(buf.getvalue(), [270, 0])
    out = pikepdf.open(io.BytesIO(corrected))
    # стр.1 перерисована (маркер сверху), стр.2 — исходная боковая (маркер не сверху)
    assert _top_strip_is_dark(_render_first_page_png(corrected))
    pdf = pdfium.PdfDocument(corrected)
    p2 = pdf[1].render(scale=1.0).to_pil(); b = io.BytesIO(); p2.save(b, format="PNG")
    assert not _top_strip_is_dark(b.getvalue())


def test_apply_rotations_two_rotated_pages():
    """≥2 повёрнутых страниц: обе выпрямлены, foreign-ссылки не оборвались до save."""
    src = pikepdf.open(io.BytesIO(_sideways_scan_pdf()))
    two = pikepdf.new()
    two.pages.append(src.pages[0]); two.pages.append(src.pages[0])
    buf = io.BytesIO(); two.save(buf)
    corrected = po.apply_rotations(buf.getvalue(), [270, 270])
    out = pikepdf.open(io.BytesIO(corrected))
    assert len(out.pages) == 2
    pdf = pdfium.PdfDocument(corrected)
    for idx in range(2):
        img = pdf[idx].render(scale=1.0).to_pil(); b = io.BytesIO(); img.save(b, format="PNG")
        assert _top_strip_is_dark(b.getvalue())  # обе выпрямлены


def _openrouter_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@pytest.mark.asyncio
@respx.mock
async def test_detect_rotations_parses_list(monkeypatch, _allow_respx):
    monkeypatch.setattr(po.settings, "OPENROUTER_API_KEY", "test-key")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=_openrouter_reply("Вот повороты: [0, 90, 270]")
    )
    out = await po.detect_rotations([b"img0", b"img1", b"img2"])
    assert out == [0, 90, 270]


@pytest.mark.asyncio
@respx.mock
async def test_detect_rotations_garbage_to_zeros(monkeypatch, _allow_respx):
    monkeypatch.setattr(po.settings, "OPENROUTER_API_KEY", "test-key")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=_openrouter_reply("не смог")
    )
    out = await po.detect_rotations([b"img0", b"img1"])
    assert out == [0, 0]  # длина = числу страниц, всё в 0


@pytest.mark.asyncio
async def test_detect_rotations_too_many_pages():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        await po.detect_rotations([b"x"] * (po.MAX_DESKEW_PAGES + 1))
    assert ei.value.status_code == 413


@pytest.mark.asyncio
@respx.mock
async def test_detect_rotations_upstream_500_raises_502(monkeypatch, _allow_respx):
    monkeypatch.setattr(po.settings, "OPENROUTER_API_KEY", "test-key")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(return_value=httpx.Response(500))
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        await po.detect_rotations([b"x"])
    assert ei.value.status_code == 502


@pytest.mark.asyncio
@respx.mock
async def test_detect_rotations_prose_around_array(monkeypatch, _allow_respx):
    monkeypatch.setattr(po.settings, "OPENROUTER_API_KEY", "test-key")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=_openrouter_reply("Страница 1 и 2: ответ [90, 0]")
    )
    assert await po.detect_rotations([b"a", b"b"]) == [90, 0]  # «1»,«2» из прозы не попали


@pytest.mark.asyncio
async def test_deskew_pdf_all_zeros_returns_original(monkeypatch):
    """Все нули → исходные байты без перерисовки (идентичность)."""
    original = _sideways_scan_pdf()

    async def fake_detect(images):
        return [0] * len(images)
    monkeypatch.setattr(po, "detect_rotations", fake_detect)

    out_bytes, rots = await po.deskew_pdf(original)
    assert rots == [0]
    assert out_bytes == original  # тот же объект байтов, без перерисовки


@pytest.mark.asyncio
async def test_deskew_pdf_applies_rotation(monkeypatch):
    original = _sideways_scan_pdf()

    async def fake_detect(images):
        return [270] * len(images)
    monkeypatch.setattr(po, "detect_rotations", fake_detect)

    out_bytes, rots = await po.deskew_pdf(original)
    assert rots == [270]
    assert out_bytes != original
    assert _top_strip_is_dark(_render_first_page_png(out_bytes))  # выпрямлено
