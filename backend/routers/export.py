from datetime import date
from io import BytesIO
from itertools import groupby
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

import crud
from database import get_db
from models import Project

router = APIRouter()

# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold: bool = False, color: str = "000000", size: int = 10) -> Font:
    return Font(bold=bold, color=color, name="Calibri", size=size)


def _align(h: str = "left", v: str = "center", wrap: bool = False) -> Alignment:
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


_THIN = Side(style="thin", color="BFBFBF")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_BORDER_BOTTOM = Border(bottom=Side(style="medium", color="2E75B6"))

# Color palette
_C_HEADER_BG       = "1F4E79"   # dark navy — project header block
_C_CLASS_BG        = "2E75B6"   # medium blue — material-class section title
_C_COL_BG          = "4472C4"   # lighter blue — column header row
_C_MONTH_BG        = "DEEAF1"   # very light blue — month sub-header
_C_MONTH_TOTAL_BG  = "BDD7EE"   # light blue — month subtotal row
_C_CLASS_TOTAL_BG  = "9DC3E6"   # medium light blue — class grand total row
_C_TOTAL_BG        = "D6E4F0"   # kept for reference (not used in sections)
_C_ODD             = "FFFFFF"   # white — odd data rows
_C_EVEN            = "EBF3FB"   # pale blue — even data rows
_C_RED_TEXT        = "C00000"   # red — overpayment
_C_GREEN_TEXT      = "375623"   # green — savings

_MONTH_NAMES_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

_FMT_MONEY    = '#,##0.00 "₽"'
_FMT_DATE     = "DD.MM.YYYY"
_FMT_PCT      = '+0.0%;-0.0%;0.0%'
_FMT_PCT_RATE = "0%"           # for vat_rate stored as decimal (0.20 → 20%)
_FMT_QTY      = "#,##0.000"

# Column definitions: (header label, width, number_format, alignment)
# Col  1=A Дата,  2=B Номер,  3=C Поставщик,  4=D Объём,  5=E Плановая цена
# Col  6=F Ставка НДС
# Col  7=G Бетон без НДС,  8=H Доставка без НДС,  9=I Прочее без НДС,  10=J Итого без НДС (=G+H+I)
# Col 11=K Бетон с НДС (=G*(1+F)), 12=L Доставка с НДС (=H*(1+F)), 13=M Прочее с НДС (=I*(1+F))
# Col 14=N Итого с НДС (=K+L+M), 15=O Откл.% (formula), 16=P Откл.₽ (formula)
_COLUMNS = [
    ("Дата УПД",                     13, _FMT_DATE,      "center"),  # A  1
    ("Номер УПД",                    14, "@",             "left"),    # B  2
    ("Поставщик",                    30, "@",             "left"),    # C  3
    ("Объём, м³",                    11, _FMT_QTY,        "right"),   # D  4
    ("Плановая цена, ₽/м³",         18, _FMT_MONEY,      "right"),   # E  5
    ("Ставка НДС, %",                10, _FMT_PCT_RATE,  "center"),  # F  6  static
    ("Бетон без НДС, ₽/м³",         18, _FMT_MONEY,      "right"),   # G  7  static
    ("Доставка без НДС, ₽/м³",      18, _FMT_MONEY,      "right"),   # H  8  static
    ("Прочее без НДС, ₽/м³",        18, _FMT_MONEY,      "right"),   # I  9  static
    ("Итого без НДС, ₽/м³",         18, _FMT_MONEY,      "right"),   # J 10  formula =G+H+I
    ("Бетон с НДС, ₽/м³",           18, _FMT_MONEY,      "right"),   # K 11  formula =G*(1+F)
    ("Доставка с НДС, ₽/м³",        18, _FMT_MONEY,      "right"),   # L 12  formula =H*(1+F)
    ("Прочее с НДС, ₽/м³",          18, _FMT_MONEY,      "right"),   # M 13  formula =I*(1+F)
    ("Итого с НДС, ₽/м³",           18, _FMT_MONEY,      "right"),   # N 14  formula =K+L+M
    ("Откл. от плана, %",            16, _FMT_PCT,        "right"),   # O 15  formula
    ("Откл. от плана, ₽",           18, _FMT_MONEY,      "right"),   # P 16  formula
]
_N_COLS = len(_COLUMNS)


def _dev_font(value, bold: bool = False, size: int = 10) -> Font:
    """Font with red/green colour based on deviation sign."""
    if value is None or value == 0:
        return _font(bold=bold, size=size)
    color = _C_RED_TEXT if value > 0 else _C_GREEN_TEXT
    return _font(bold=bold, color=color, size=size)


def _write_grand_total_row(
    ws,
    row_num: int,
    label: str,
    fill: PatternFill,
    label_font: Font,
    data_font: Font,
    data_ranges: list[tuple[int, int]],
    dev_total_py: float,
    w_dev_py: float,
) -> None:
    """Write the class-level grand total row across multiple non-contiguous month data ranges."""
    r = row_num

    def _c(col_idx, value, font=None, fmt=None, h="right"):
        cell = ws.cell(row=r, column=col_idx, value=value)
        cell.fill = fill
        cell.font = font or data_font
        cell.border = _BORDER
        cell.alignment = _align(h=h)
        if fmt:
            cell.number_format = fmt
        return cell

    _c(1, label, font=label_font, h="left")
    for ci in (2, 3):
        _c(ci, None)

    sum_d = ",".join(f"D{s}:D{e}" for s, e in data_ranges)
    _c(4, f"=SUM({sum_d})", fmt=_FMT_QTY)
    _c(5, None)   # Плановая — not averaged
    _c(6, None)   # Ставка НДС — not averaged

    # G, H, I, K, L, M: weighted average = (Σ SUMPRODUCT(col, D)) / SUM(all D)
    for ci, cl in ((7, "G"), (8, "H"), (9, "I"), (11, "K"), (12, "L"), (13, "M")):
        sp = "+".join(f"SUMPRODUCT({cl}{s}:{cl}{e},D{s}:D{e})" for s, e in data_ranges)
        _c(ci, f'=IFERROR(({sp})/SUM({sum_d}),"")', fmt=_FMT_MONEY)

    _c(10, f"=G{r}+H{r}+I{r}", fmt=_FMT_MONEY)   # Итого без НДС
    _c(14, f"=K{r}+L{r}+M{r}", fmt=_FMT_MONEY)   # Итого с НДС

    sum_p = ",".join(f"P{s}:P{e}" for s, e in data_ranges)
    _c(16, f'=IFERROR(SUM({sum_p}),"")', font=_dev_font(dev_total_py, bold=True, size=12), fmt=_FMT_MONEY)

    denom = "+".join(f"SUMPRODUCT((E{s}:E{e}>0)*E{s}:E{e}*D{s}:D{e})" for s, e in data_ranges)
    _c(15, f'=IFERROR(P{r}/({denom}),"")', font=_dev_font(w_dev_py, bold=True, size=12), fmt=_FMT_PCT)

    ws.row_dimensions[r].height = 24


def _write_class_section(
    ws,
    class_name: str,
    rows: list[dict],
    start_row: int,
) -> int:
    """Write one material-class section with per-month breakdown.

    Layout per class:
      [Class header]
      [Column headers]
      [Month sub-header — Январь 2025]
        row … row (data)
      [Итого Январь 2025]
      [Month sub-header — Февраль 2025]
        …
      [ИТОГО по <class>]
      (spacer)

    Columns 1–8: static DB values.
    Columns 9–11: Excel formulas (Итого = F+G+H; Откл.% = (I-E)/E; Откл.₽ = (I-E)*D).
    Subtotal and grand-total rows also use SUMPRODUCT/SUM formulas.
    """
    cur = start_row

    # ── Class section header ─────────────────────────────────────────────────
    ws.merge_cells(start_row=cur, start_column=1, end_row=cur, end_column=_N_COLS)
    h = ws.cell(row=cur, column=1, value=class_name)
    h.fill = _fill(_C_CLASS_BG)
    h.font = _font(bold=True, color="FFFFFF", size=11)
    h.alignment = _align(h="left", v="center")
    ws.row_dimensions[cur].height = 20
    cur += 1

    # ── Column headers ───────────────────────────────────────────────────────
    for col_idx, (label, _, _, h_align) in enumerate(_COLUMNS, start=1):
        cell = ws.cell(row=cur, column=col_idx, value=label)
        cell.fill = _fill(_C_COL_BG)
        cell.font = _font(bold=True, color="FFFFFF", size=9)
        cell.border = _BORDER
        cell.alignment = _align(h=h_align, wrap=True)
    ws.row_dimensions[cur].height = 30
    cur += 1

    # ── Month groups ─────────────────────────────────────────────────────────
    # rows are pre-sorted by date → groupby month is safe
    data_ranges: list[tuple[int, int]] = []  # (data_start, data_end) per month

    month_groups = [
        ((year, month), list(month_iter))
        for (year, month), month_iter in groupby(
            rows, key=lambda r: (r["invoice_date"].year, r["invoice_date"].month)
        )
    ]
    for group_idx, ((year, month), month_rows) in enumerate(month_groups):
        is_last_month = group_idx == len(month_groups) - 1
        month_label = f"{_MONTH_NAMES_RU[month]} {year}"

        # ── Month header row: label (A–C merged) + weighted-avg data (D–P) ─
        month_data_start = cur + 1
        month_data_end   = cur + len(month_rows)
        s, e = month_data_start, month_data_end
        rh = cur  # header row number

        # Python-side values for deviation font coloring (computed ahead of writing)
        month_dev = sum(
            row["deviation_amount"] for row in month_rows
            if row["deviation_amount"] is not None
        )
        month_rows_ref = [row for row in month_rows if row["deviation_pct"] is not None]
        qty_ref_m = sum(row["qty"] for row in month_rows_ref)
        w_dev_m = (
            sum(row["deviation_pct"] * row["qty"] for row in month_rows_ref) / qty_ref_m
            if qty_ref_m else 0
        )

        hdr_fill = _fill(_C_MONTH_BG)
        hdr_font = _font(bold=True, color="1F4E79", size=11)

        ws.merge_cells(start_row=rh, start_column=1, end_row=rh, end_column=3)
        _mh = ws.cell(row=rh, column=1, value=month_label)
        _mh.fill = hdr_fill
        _mh.font = hdr_font
        _mh.border = _BORDER
        _mh.alignment = _align(h="left", v="center")
        for _ci in (2, 3):
            _mc = ws.cell(row=rh, column=_ci)
            _mc.fill = hdr_fill
            _mc.border = _BORDER

        def _hc(col_idx, value, font=None, fmt=None, h="right",
                _row=rh, _fill=hdr_fill, _font=hdr_font):
            cell = ws.cell(row=_row, column=col_idx, value=value)
            cell.fill = _fill
            cell.font = font or _font
            cell.border = _BORDER
            cell.alignment = _align(h=h)
            if fmt:
                cell.number_format = fmt

        _hc(4,  f"=SUM(D{s}:D{e})", fmt=_FMT_QTY)
        _hc(5,  None)   # Плановая — not averaged
        _hc(6,  None)   # Ставка НДС — not averaged
        _hc(7,  f'=IFERROR(SUMPRODUCT(G{s}:G{e},D{s}:D{e})/SUM(D{s}:D{e}),"")', fmt=_FMT_MONEY)
        _hc(8,  f'=IFERROR(SUMPRODUCT(H{s}:H{e},D{s}:D{e})/SUM(D{s}:D{e}),"")', fmt=_FMT_MONEY)
        _hc(9,  f'=IFERROR(SUMPRODUCT(I{s}:I{e},D{s}:D{e})/SUM(D{s}:D{e}),"")', fmt=_FMT_MONEY)
        _hc(10, f"=G{rh}+H{rh}+I{rh}", fmt=_FMT_MONEY)   # Итого без НДС
        _hc(11, f'=IFERROR(SUMPRODUCT(K{s}:K{e},D{s}:D{e})/SUM(D{s}:D{e}),"")', fmt=_FMT_MONEY)
        _hc(12, f'=IFERROR(SUMPRODUCT(L{s}:L{e},D{s}:D{e})/SUM(D{s}:D{e}),"")', fmt=_FMT_MONEY)
        _hc(13, f'=IFERROR(SUMPRODUCT(M{s}:M{e},D{s}:D{e})/SUM(D{s}:D{e}),"")', fmt=_FMT_MONEY)
        _hc(14, f"=K{rh}+L{rh}+M{rh}", fmt=_FMT_MONEY)   # Итого с НДС
        _hc(16, f'=IFERROR(SUM(P{s}:P{e}),"")', font=_dev_font(month_dev, bold=True), fmt=_FMT_MONEY)
        _hc(15, f'=IFERROR(P{rh}/SUMPRODUCT((E{s}:E{e}>0)*E{s}:E{e}*D{s}:D{e}),"")',
            font=_dev_font(w_dev_m, bold=True), fmt=_FMT_PCT)
        ws.row_dimensions[rh].height = 18
        cur += 1

        # Data rows
        for i, r in enumerate(month_rows):
            row_fill = _fill(_C_ODD if i % 2 == 0 else _C_EVEN)
            row_font = _font(color="000000")

            # Cols 1–9: static DB values (A–I)
            for col_idx, val in enumerate([
                r["invoice_date"],              # A 1
                r["invoice_number"],            # B 2
                r["supplier_name"],             # C 3
                r["qty"],                       # D 4
                r["ref_price"],                 # E 5
                r["vat_rate"],                  # F 6  Ставка НДС (decimal 0.20)
                r["mat_per_m3_excl_vat"],       # G 7  Бетон без НДС
                r["delivery_per_m3_excl_vat"],  # H 8  Доставка без НДС
                r["other_per_m3_excl_vat"],     # I 9  Прочее без НДС
            ], start=1):
                _, _, num_fmt, h_align = _COLUMNS[col_idx - 1]
                cell = ws.cell(row=cur, column=col_idx, value=val)
                cell.fill = row_fill
                cell.font = row_font
                cell.border = _BORDER
                cell.alignment = _align(h=h_align)
                if num_fmt:
                    cell.number_format = num_fmt

            n = cur

            def _dc(col_idx, value, font=None, fmt=_FMT_MONEY,
                    _fill=row_fill, _font=row_font, _row=n):
                cell = ws.cell(row=_row, column=col_idx, value=value)
                cell.fill = _fill
                cell.font = font or _font
                cell.border = _BORDER
                cell.alignment = _align(h="right")
                if fmt:
                    cell.number_format = fmt

            # Col 10 (J): Итого без НДС = G+H+I
            _dc(10, f"=G{n}+H{n}+I{n}")
            # Col 11 (K): Бетон с НДС = G*(1+F)
            _dc(11, f"=G{n}*(1+F{n})")
            # Col 12 (L): Доставка с НДС = H*(1+F)
            _dc(12, f"=H{n}*(1+F{n})")
            # Col 13 (M): Прочее с НДС = I*(1+F)
            _dc(13, f"=I{n}*(1+F{n})")
            # Col 14 (N): Итого с НДС = K+L+M
            _dc(14, f"=K{n}+L{n}+M{n}")
            # Col 15 (O): Откл. %
            _dc(15, f'=IFERROR((N{n}-E{n})/E{n},"")',
                font=_dev_font(r["deviation_pct"]), fmt=_FMT_PCT)
            # Col 16 (P): Откл. ₽
            _dc(16, f'=IFERROR((N{n}-E{n})*D{n},"")',
                font=_dev_font(r["deviation_amount"]))

            ws.row_dimensions[cur].height = 16
            cur += 1

        data_ranges.append((month_data_start, month_data_end))

        # Thin separator row between months (not after the last one)
        if not is_last_month:
            for _ci in range(1, _N_COLS + 1):
                _sc = ws.cell(row=cur, column=_ci)
                _sc.fill = _fill(_C_MONTH_TOTAL_BG)
            ws.row_dimensions[cur].height = 6
            cur += 1

    # ── Class grand total ────────────────────────────────────────────────────
    grand_dev = sum(r["deviation_amount"] for r in rows if r["deviation_amount"] is not None)
    rows_ref = [r for r in rows if r["deviation_pct"] is not None]
    qty_ref_all = sum(r["qty"] for r in rows_ref)
    w_dev_all = (
        sum(r["deviation_pct"] * r["qty"] for r in rows_ref) / qty_ref_all
        if qty_ref_all else 0
    )
    _write_grand_total_row(
        ws, cur,
        label=f"ИТОГО по {class_name}",
        fill=_fill(_C_CLASS_TOTAL_BG),
        label_font=_font(bold=True, color="1F4E79", size=12),
        data_font=_font(bold=True, color="1F4E79", size=12),
        data_ranges=data_ranges,
        dev_total_py=grand_dev,
        w_dev_py=w_dev_all,
    )
    cur += 1

    # Spacer
    cur += 1
    return cur


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/excel")
def export_excel(
    project_id: int,
    period_start: date | None = None,
    period_end: date | None = None,
    material_class_id: int | None = None,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "Проект не найден"}

    rows = crud.compute_export_rows(db, project_id, period_start, period_end, material_class_id)

    # Actual displayed period from data
    if rows:
        display_start = period_start or min(r["invoice_date"] for r in rows)
        display_end = period_end or max(r["invoice_date"] for r in rows)
    else:
        display_start = period_start or date.today().replace(day=1)
        display_end = period_end or date.today()

    # ── Build workbook ────────────────────────────────────────────────────────
    wb = Workbook()
    ws = wb.active
    ws.title = "Отчёт"
    ws.sheet_view.showGridLines = False

    # Set column widths
    for col_idx, (_, width, _, _) in enumerate(_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    cur = 1  # current row pointer

    # ── Project info block ────────────────────────────────────────────────────
    info_fill = _fill(_C_HEADER_BG)
    info_lines = [
        project.name,
        project.contract_number or "",
        f"Период: {display_start.strftime('%d.%m.%Y')} — {display_end.strftime('%d.%m.%Y')}",
        f"Сформировано: {date.today().strftime('%d.%m.%Y')}",
    ]
    info_fonts = [
        _font(bold=True, color="FFFFFF", size=14),
        _font(color="BDD7EE", size=10),
        _font(color="FFFFFF", size=10),
        _font(color="9DC3E6", size=9),
    ]
    info_heights = [24, 16, 16, 14]

    for text, font, height in zip(info_lines, info_fonts, info_heights, strict=True):
        ws.merge_cells(
            start_row=cur, start_column=1,
            end_row=cur, end_column=_N_COLS,
        )
        cell = ws.cell(row=cur, column=1, value=text)
        cell.fill = info_fill
        cell.font = font
        cell.alignment = _align(h="left", v="center")
        ws.row_dimensions[cur].height = height
        cur += 1

    cur += 1  # blank spacer after header

    # ── Material class sections ───────────────────────────────────────────────
    if not rows:
        ws.merge_cells(
            start_row=cur, start_column=1, end_row=cur, end_column=_N_COLS
        )
        ws.cell(row=cur, column=1, value="Нет данных за выбранный период").font = _font(
            color="888888", size=10
        )
    else:
        for class_name, group in groupby(rows, key=lambda r: r["material_class_name"]):
            cur = _write_class_section(ws, class_name, list(group), cur)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_cell = ws.cell(
        row=cur + 1,
        column=1,
        value="* Стоимость доставки и прочих включений распределена пропорционально объёму м³ каждого класса материала в рамках каждой СФ.",
    )
    footer_cell.font = _font(color="888888", size=8)
    footer_cell.alignment = _align(h="left", wrap=True)
    ws.merge_cells(
        start_row=cur + 1, start_column=1, end_row=cur + 1, end_column=_N_COLS
    )
    ws.row_dimensions[cur + 1].height = 24

    # ── Freeze panes ─────────────────────────────────────────────────────────
    # (no freeze — sections have their own headers)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    safe_name = project.name.replace("/", "-").replace("\\", "-")
    filename = f"отчёт_{safe_name}_{display_start}_{display_end}.xlsx"
    encoded = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
