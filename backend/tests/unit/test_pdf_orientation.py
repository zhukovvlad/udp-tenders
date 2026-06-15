import io

import pikepdf
import pypdfium2 as pdfium
from PIL import Image

import pdf_orientation as po


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
