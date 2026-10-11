# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from io import BytesIO

import xlsxwriter

from odoo import api, models

from odoo.addons.collection.report.collection_sheet_xlsx import (
    _BANNER_FILL,
    MONEY,
    NAVY,
    NAVY_DARK,
    WORKBOOK_OPTIONS,
    _a1,
    _abs_range,
    _date_cell,
    _formats,
    _formula,
    _merge,
    _sum_or_zero,
    _text,
    _write,
    _write_headers,
)

from ..models.collection_allocation import DOCUMENT_KINDS
from ..models.collection_assignment_report import (
    DOCUMENT_KEYS,
    KIND_TITLES,
    SUMMARY_KEYS,
)

SUMMARY_SHEET = "Resumen"
CUSTOMER_SHEET = "Clientes"
SUMMARY_TITLE = "Asignaciones de Cobranza"
CUSTOMER_TITLE = "Asignaciones - Clientes"
SUMMARY_LAST_COL = 9
CUSTOMER_LAST_COL = 8
SUMMARY_WIDTHS = (13, 32, 15, 16, 16, 15, 15, 15, 18, 34)
CUSTOMER_WIDTHS = (20, 18, 16, 20, 18, 16, 18, 17, 17)
SUMMARY_HEADERS = (
    ("Código", 0, 0),
    ("Cliente", 1, 1),
    ("Circuito", 2, 2),
    ("Cobrado", 3, 3),
    ("Aplicado", 4, 4),
    ("A Cuenta", 5, 5),
    ("Deuda Total", 6, 6),
    ("Pendiente", 7, 7),
    ("Estado Circuito", 8, 8),
    ("Nota de Cierre", 9, 9),
)
DOCUMENT_HEADERS = (
    ("Documento", 0, 0),
    ("ID Externo", 1, 1),
    ("Emisión", 2, 2),
    ("Vencimiento", 3, 3),
    ("Saldo", 4, 4),
    ("Aplicado", 5, 5),
    ("Comisión", 6, 6),
    ("Estado ERP", 7, CUSTOMER_LAST_COL),
)
CASH_HEADERS = (
    ("Valor Efectivo", 0, 0),
    ("Valor Depósito", 1, 1),
    ("Movimiento", 2, 2),
    ("Importe", 3, 3),
    ("Registrado Por", 4, 5),
    ("Registrado En", 6, 7),
    ("", CUSTOMER_LAST_COL, CUSTOMER_LAST_COL),
)
# Each voucher type prints the fields it actually has, in the four middle
# columns, the way the Planilla's own `_VOUCHER_BLOCK_COLUMNS` reshapes its
# cheque block. No type carries a column that is always blank for it.
_DEFAULT_VOUCHER_SHAPE = {
    "date": ("Fecha", "date"),
    "middle": (
        ("Nº Comprobante", "number", "text"),
        ("ID Documento", "document_id", "text"),
        ("Estado", "state_label", "text"),
        ("Revisado Por", "reviewed_by", "text"),
        ("Revisado En", "reviewed_at", "datetime"),
    ),
}
_ACCOUNT_VOUCHER_SHAPE = {
    "date": ("Fecha", "date"),
    "middle": (
        ("Nº Comprobante", "number", "text"),
        ("Cuenta Origen", "from_account", "text"),
        ("Cuenta Destino", "to_account", "text"),
        ("Estado", "state_label", "text"),
        ("Revisado Por", "reviewed_by", "text"),
    ),
}
_VOUCHER_SHAPES = {
    "check": {
        "date": ("Emisión", "check_issue_date"),
        "middle": (
            ("Nº Cheque", "number", "text"),
            ("Banco", "check_bank", "text"),
            ("Tipo", "check_type_label", "text"),
            ("Pago", "check_payment_date", "date"),
            ("Estado", "state_label", "text"),
        ),
    },
    "bank_transfer": _ACCOUNT_VOUCHER_SHAPE,
    "echeck": _ACCOUNT_VOUCHER_SHAPE,
    "retention_certificate": {
        "date": ("Fecha", "date"),
        "middle": (
            ("Nº Comprobante", "number", "text"),
            ("Tipo de Retención", "retention_label", "text"),
            ("ID Documento", "document_id", "text"),
            ("Estado", "state_label", "text"),
            ("Revisado Por", "reviewed_by", "text"),
        ),
    },
}
# Fills mark structure; rules and typography mark tables and totals. Three
# structural levels step dark -> medium -> light in one blue family, each at
# least 1.4x apart in luminance, so nesting is legible at a glance. Subtotals
# are deliberately quiet — a navy top rule closes a table better than a fill
# that competes with the headings around it.
LVL1_FILL = "#1F3864"  # customer, and the two closing sections
LVL2_FILL = "#2E75B6"  # circuit, i.e. one receipt
LVL3_FILL = "#9DC3E6"  # a block inside a receipt
SUB_FILL = "#F2F2F2"  # block subtotal, closed by a navy rule
ZEBRA_FILL = "#EFF4FA"  # every other data row, ~1.1x — a hint, not a stripe
BALANCE_FILL = "#1F4E79"  # the per-receipt answer earns a dark band of its own
FLAG_FILL = "#FFEB9C"  # split voucher: the one warm accent on the sheet
FLAG_FONT = "#7F5100"
HAIRLINE = "#D0D0D0"
_SUMMARY_KIND_COL = 2
_SUMMARY_FIRST_MONEY_COL = 3
# On the Clientes sheet the money that counts sits in column F for a document
# block and in column I for a voucher block, exactly as the Planilla splits
# `Aplicado` (col 5) from a voucher `Importe` (col 7). Nothing sums across a
# block boundary; every balance line references named subtotal cells instead.
_DOCUMENT_FIRST_MONEY_COL = 4
_DOCUMENT_APPLIED_COL = 5
_VOUCHER_AMOUNT_COL = 7
_VOUCHER_APPLIED_COL = CUSTOMER_LAST_COL
_CASH_AMOUNT_COL = 3
_BALANCE_FIRST_COL = 6
_KIND_ORDER = tuple((kind, KIND_TITLES[kind]) for kind in DOCUMENT_KINDS)
_RECON_COMPONENTS = ("assigned_total", "unassigned_total", "replaced_total")


def _receipt_formats(workbook):
    """The Clientes palette: a structural ladder plus the accents it needs.

    Deliberately additive — no key the shared `_formats` already owns is
    overridden, so the Resumen worksheet and the Planilla keep the house look
    byte for byte. Every fill/text pair here clears WCAG AA, and every pair of
    fills that touch vertically in the document is at least 1.25x apart unless a
    border, a warm hue or a blank row separates them instead.
    """

    def fmt(**kwargs):
        return workbook.add_format(kwargs)

    thin = {"border": 1, "border_color": HAIRLINE}
    money = {"num_format": MONEY, "align": "right"}

    def level(fill, color, size):
        return fmt(
            bold=True,
            bg_color=fill,
            font_color=color,
            font_size=size,
            valign="vcenter",
            border=1,
            border_color=fill,
        )

    def total(fill, size, rule):
        common = {
            "bold": True,
            "bg_color": fill,
            "font_color": "#FFFFFF",
            "font_size": size,
            "border": 1,
            "border_color": fill,
            "top": rule,
            "top_color": NAVY_DARK,
        }
        return fmt(**common), fmt(**common, **money)

    balance, balance_money = total(BALANCE_FILL, 11, 2)
    customer_total, customer_total_money = total(LVL1_FILL, 11, 5)
    grand_total, grand_total_money = total(LVL1_FILL, 13, 5)
    styles = {
        "lvl1": level(LVL1_FILL, "#FFFFFF", 12),
        "lvl2": level(LVL2_FILL, "#FFFFFF", 11),
        "lvl3": level(LVL3_FILL, NAVY_DARK, 10),
        "zebra": fmt(bg_color=ZEBRA_FILL, **thin),
        "zebra_money": fmt(bg_color=ZEBRA_FILL, **money, **thin),
        "zebra_date": fmt(
            bg_color=ZEBRA_FILL, num_format="DD/MM/YYYY", align="center", **thin
        ),
        "zebra_datetime": fmt(
            bg_color=ZEBRA_FILL,
            num_format="DD/MM/YYYY HH:MM",
            align="center",
            **thin,
        ),
        "data_datetime": fmt(num_format="DD/MM/YYYY HH:MM", align="center", **thin),
        "data_money_flag": fmt(
            bold=True,
            bg_color=FLAG_FILL,
            font_color=FLAG_FONT,
            **money,
            **thin,
        ),
        "sub_rule": fmt(
            bold=True,
            bg_color=SUB_FILL,
            font_color=NAVY_DARK,
            align="right",
            border=1,
            border_color=HAIRLINE,
            top=2,
            top_color=NAVY,
        ),
        "sub_rule_money": fmt(
            bold=True,
            bg_color=SUB_FILL,
            font_color=NAVY_DARK,
            num_format=MONEY,
            align="right",
            border=1,
            border_color=HAIRLINE,
            top=2,
            top_color=NAVY,
        ),
        "recon_row": fmt(bold=True, font_color=NAVY_DARK, align="right", **thin),
        "recon_row_money": fmt(bold=True, font_color=NAVY_DARK, **money, **thin),
        "balance": balance,
        "balance_money": balance_money,
        "customer_total": customer_total,
        "customer_total_money": customer_total_money,
        "grand_total": grand_total,
        "grand_total_money": grand_total_money,
    }
    # The Diferencia row borrows the Planilla's own banner palette, so a sheet
    # that does not reconcile says so in the colour the operator already knows.
    for status, (fill, color) in _BANNER_FILL.items():
        styles[f"diff_{status}"] = fmt(
            bold=True, bg_color=fill, font_color=color, border=1, border_color=NAVY
        )
        styles[f"diff_{status}_money"] = fmt(
            bold=True,
            bg_color=fill,
            font_color=color,
            border=1,
            border_color=NAVY,
            **money,
        )
    return styles


def _formats_with_extras(workbook):
    fmt = _formats(workbook)
    fmt.update(_receipt_formats(workbook))
    return fmt


# ----------------------------------------------------------------------
# Layout helpers
# ----------------------------------------------------------------------


def _span(ws, row, c1, c2, value, fmt):
    """Write across a column span; xlsxwriter refuses to merge a single cell."""
    if c1 == c2:
        _write(ws, row, c1, value, fmt)
    else:
        _merge(ws, row, c1, c2, value, fmt)


def _section(ws, fmt, row, title, last_col):
    _merge(ws, row, 0, last_col, title, fmt["section"])
    ws.set_row(row - 1, 20)


def _level1(ws, fmt, row, title):
    """Top level: a customer, or one of the two closing sections."""
    _merge(ws, row, 0, CUSTOMER_LAST_COL, title, fmt["lvl1"])
    ws.set_row(row - 1, 22)


def _level2(ws, fmt, row, title):
    """Second level: one circuit of one customer, which is one receipt."""
    _merge(ws, row, 0, CUSTOMER_LAST_COL, title, fmt["lvl2"])
    ws.set_row(row - 1, 20)


def _level3(ws, fmt, row, title):
    """Third level: a block inside one receipt."""
    _merge(ws, row, 0, CUSTOMER_LAST_COL, title, fmt["lvl3"])
    ws.set_row(row - 1, 16)


def _cell(fmt, kind, index):
    """The zebra variant of a data format for row ``index`` inside a block.

    Nine columns are hard to track across by eye; a ~1.1x stripe is enough to
    hold the row without competing with any heading.
    """
    prefix = "zebra" if index % 2 else "data"
    return fmt[prefix] if kind == "text" else fmt[f"{prefix}_{kind}"]


def _write_typed(ws, fmt, row, col, data, key, kind, index):
    """Write one payload key with the number format its type needs."""
    value = data.get(key)
    if kind in ("date", "datetime"):
        _write(ws, row, col, _date_cell(value), _cell(fmt, kind, index))
    else:
        _write(ws, row, col, value or "", _cell(fmt, "text", index))


def _period(payload):
    date_from = _text(payload.get("date_from"))
    date_to = _text(payload.get("date_to"))
    if date_from and date_to:
        return f"{date_from} - {date_to}"
    return date_from or date_to or ""


def _write_band(ws, fmt, payload, title, last_col):
    """Membrete: report name and sheet reference, like the Planilla's own.

    Mirrors `collection`'s `_write_membrete`: no company header and no print
    date, while the payload still carries both. The rows keep their geometry,
    so everything below the membrete stays where it was.
    """
    _merge(ws, 1, 0, last_col, title, fmt["title"])
    ws.set_row(0, 26)
    _merge(ws, 2, 0, last_col, payload.get("reference") or "", fmt["muted"])
    ws.set_row(1, 14)
    _merge(ws, 3, 0, last_col, "", fmt["bar"])
    ws.set_row(2, 4)
    _merge(ws, 4, 0, last_col, "", fmt["muted"])
    ws.set_row(3, 14)
    ws.set_row(4, 8)


def _write_info(ws, fmt, payload, start, last_col):
    """Two label/value rows describing the sheet. Returns the next free row."""
    _section(ws, fmt, start, "Planilla", last_col)
    pairs = (
        (
            ("Planilla", payload.get("reference") or "", fmt["value"]),
            ("Estado", payload.get("state_label") or "", fmt["value"]),
            ("Moneda", payload.get("currency_name") or "", fmt["value"]),
        ),
        (
            ("Vendedor", payload.get("seller_name") or "", fmt["value"]),
            ("Período", _period(payload), fmt["value"]),
            ("Clientes", payload.get("customer_count") or 0, fmt["value_int"]),
        ),
    )
    spans = (((0, 1), (2, 3)), ((4, 5), (6, 7)), ((8, 8), (9, last_col)))
    for index, cells in enumerate(pairs):
        row = start + 1 + index
        for (label, value, value_fmt), (label_span, value_span) in zip(
            cells, spans, strict=True
        ):
            _span(ws, row, label_span[0], label_span[1], label, fmt["label"])
            _span(ws, row, value_span[0], value_span[1], value, value_fmt)
    return start + len(pairs) + 2


def _kind_sumif(first, last, col, kind_label):
    """SUMIF the summary rows by the Circuito column."""
    return (
        f"=SUMIF({_abs_range(first, last, _SUMMARY_KIND_COL)},"
        f'"{kind_label}",{_abs_range(first, last, col)})'
    )


# ----------------------------------------------------------------------
# Resumen
# ----------------------------------------------------------------------


def _write_summary(ws, fmt, payload, start, last_col):
    rows = payload.get("summary_rows") or []
    _section(ws, fmt, start, "Resumen por Cliente y Circuito", last_col)
    _write_headers(ws, fmt, start + 1, SUMMARY_HEADERS)
    first = start + 2
    for index, row in enumerate(rows):
        current = first + index
        _write(ws, current, 0, row.get("code") or "", fmt["data"])
        _write(ws, current, 1, row.get("name") or "", fmt["data"])
        _write(ws, current, 2, row.get("kind_label") or "", fmt["data"])
        for offset, key in enumerate(SUMMARY_KEYS):
            _write(
                ws,
                current,
                _SUMMARY_FIRST_MONEY_COL + offset,
                row.get(key) or 0.0,
                fmt["data_money"],
            )
        _write(ws, current, 8, row.get("kind_status_label") or "", fmt["data"])
        _write(ws, current, 9, row.get("note") or "", fmt["data"])
    data_first = first if rows else None
    last = first + len(rows) - 1 if rows else None
    cursor = first + len(rows)
    kind_totals = payload.get("kind_totals") or {}
    for kind, kind_label in _KIND_ORDER:
        totals = kind_totals.get(kind) or {}
        _merge(ws, cursor, 0, 2, f"Subtotal {kind_label}", fmt["sub"])
        for offset, key in enumerate(SUMMARY_KEYS):
            col = _SUMMARY_FIRST_MONEY_COL + offset
            cached = totals.get(key) or 0.0
            if last is None:
                _write(ws, cursor, col, 0, fmt["sub_money"])
            else:
                _formula(
                    ws,
                    cursor,
                    col,
                    _kind_sumif(first, last, col, kind_label),
                    fmt["sub_money"],
                    cached,
                )
        _merge(ws, cursor, 8, last_col, "", fmt["sub"])
        cursor += 1
    totals = payload.get("summary_totals") or {}
    _merge(ws, cursor, 0, 2, "Total", fmt["total"])
    for offset, key in enumerate(SUMMARY_KEYS):
        col = _SUMMARY_FIRST_MONEY_COL + offset
        _sum_or_zero(
            ws,
            cursor,
            col,
            data_first,
            last,
            fmt["total_money"],
            totals.get(key) or 0.0,
        )
    _merge(ws, cursor, 8, last_col, "", fmt["total"])
    if last is not None:
        ws.autofilter(start, 0, last - 1, last_col)
    return cursor


# ----------------------------------------------------------------------
# Clientes: documents, vouchers, replacements, balances
# ----------------------------------------------------------------------


def _write_document_block(ws, fmt, circuit, start):
    """The receipt's imputed documents. Returns `(subtotal row, next free row)`.

    Always emitted, even empty, so the balance line below can reference the
    subtotal row unconditionally.
    """
    rows = circuit.get("document_rows") or []
    _level3(ws, fmt, start, "Documentos imputados")
    _write_headers(ws, fmt, start + 1, DOCUMENT_HEADERS)
    first = start + 2
    for index, row in enumerate(rows):
        current = first + index
        text = _cell(fmt, "text", index)
        money = _cell(fmt, "money", index)
        _write(ws, current, 0, row.get("number") or "", text)
        _write(ws, current, 1, row.get("external_id") or "", text)
        _write_typed(ws, fmt, current, 2, row, "issue_date", "date", index)
        _write_typed(ws, fmt, current, 3, row, "due_date", "date", index)
        for offset, key in enumerate(DOCUMENT_KEYS):
            _write(
                ws,
                current,
                _DOCUMENT_FIRST_MONEY_COL + offset,
                row.get(key) or 0.0,
                money,
            )
        _merge(
            ws,
            current,
            7,
            CUSTOMER_LAST_COL,
            row.get("invoice_state_label") or "",
            text,
        )
    subtotal = first + len(rows)
    data_first = first if rows else None
    data_last = subtotal - 1 if rows else None
    _merge(ws, subtotal, 0, 3, "Subtotal", fmt["sub_rule"])
    for offset, key in enumerate(DOCUMENT_KEYS):
        _sum_or_zero(
            ws,
            subtotal,
            _DOCUMENT_FIRST_MONEY_COL + offset,
            data_first,
            data_last,
            fmt["sub_rule_money"],
            circuit.get(f"subtotal_{key}") or 0.0,
        )
    _merge(ws, subtotal, 7, CUSTOMER_LAST_COL, "", fmt["sub_rule"])
    return subtotal, subtotal + 1


def _write_voucher_block(ws, fmt, block, start, applied_header="Aplicado"):
    """One `Comprobantes — <tipo>` block. Returns `(subtotal row, next row)`.

    Only the applied column is subtotalled, and the subtotal label merge
    deliberately swallows `Importe del Valor`: summing a voucher's own amount
    would double-count one split across two receipts.
    """
    rows = block.get("rows") or []
    shape = _VOUCHER_SHAPES.get(block.get("code") or "", _DEFAULT_VOUCHER_SHAPE)
    label = block.get("label") or block.get("code") or ""
    title = f"Comprobantes — {label}"
    split = block.get("split_count") or 0
    if split:
        title = f"{title} — {split} parcial(es), resaltado(s)"
    _level3(ws, fmt, start, title)
    date_header, date_key = shape["date"]
    _write_headers(
        ws,
        fmt,
        start + 1,
        (
            ("Referencia", 0, 0),
            (date_header, 1, 1),
            *((cell[0], col, col) for col, cell in enumerate(shape["middle"], start=2)),
            ("Importe del Valor", _VOUCHER_AMOUNT_COL, _VOUCHER_AMOUNT_COL),
            (applied_header, _VOUCHER_APPLIED_COL, _VOUCHER_APPLIED_COL),
        ),
    )
    first = start + 2
    for index, row in enumerate(rows):
        current = first + index
        money = (
            fmt["data_money_flag"]
            if row.get("is_partial")
            else _cell(fmt, "money", index)
        )
        _write(ws, current, 0, row.get("reference") or "", _cell(fmt, "text", index))
        _write_typed(ws, fmt, current, 1, row, date_key, "date", index)
        for col, (_title, key, kind) in enumerate(shape["middle"], start=2):
            _write_typed(ws, fmt, current, col, row, key, kind, index)
        _write(
            ws, current, _VOUCHER_AMOUNT_COL, row.get("voucher_amount") or 0.0, money
        )
        _write(
            ws, current, _VOUCHER_APPLIED_COL, row.get("applied_amount") or 0.0, money
        )
    subtotal = first + len(rows)
    _merge(ws, subtotal, 0, _VOUCHER_AMOUNT_COL, "Subtotal", fmt["sub_rule"])
    _sum_or_zero(
        ws,
        subtotal,
        _VOUCHER_APPLIED_COL,
        first if rows else None,
        subtotal - 1 if rows else None,
        fmt["sub_rule_money"],
        block.get("subtotal_applied") or 0.0,
    )
    return subtotal, subtotal + 1


def _write_cash_block(ws, fmt, circuit, start):
    """Cash a remittance replaced on this receipt, or reversed back.

    The amount sits in its own column, never in an applied column: the move is
    already reflected in the voucher rows above, so summing it there again would
    read as double-counted money. Nothing below depends on this block, so an
    empty ledger emits nothing at all.
    """
    rows = circuit.get("cash_rows") or []
    if not rows:
        return start
    _level3(ws, fmt, start, "Reemplazos de efectivo")
    _write_headers(ws, fmt, start + 1, CASH_HEADERS)
    first = start + 2
    for index, row in enumerate(rows):
        current = first + index
        text = _cell(fmt, "text", index)
        _write(ws, current, 0, row.get("cash_reference") or "", text)
        _write(ws, current, 1, row.get("deposit_reference") or "", text)
        _write(ws, current, 2, row.get("direction_label") or "", text)
        _write(
            ws,
            current,
            _CASH_AMOUNT_COL,
            row.get("amount") or 0.0,
            _cell(fmt, "money", index),
        )
        _merge(ws, current, 4, 5, row.get("created_by") or "", text)
        _merge(
            ws,
            current,
            6,
            7,
            _date_cell(row.get("created_at")),
            _cell(fmt, "datetime", index),
        )
        _write(ws, current, CUSTOMER_LAST_COL, "", text)
    subtotal = first + len(rows)
    _merge(ws, subtotal, 0, 2, "Subtotal", fmt["sub_rule"])
    _sum_or_zero(
        ws,
        subtotal,
        _CASH_AMOUNT_COL,
        first,
        subtotal - 1,
        fmt["sub_rule_money"],
        circuit.get("subtotal_cash_amount") or 0.0,
    )
    _merge(ws, subtotal, 4, CUSTOMER_LAST_COL, "", fmt["sub_rule"])
    return subtotal + 1


def _write_money_line(ws, fmt, row, label, refs, cached, styles):
    """A `Cobrado / Aplicado / A Cuenta` line built from named subtotal cells.

    ``refs`` is `(collected cells, applied cell)`; the third figure is always
    the difference of the two written just above it, so the line needs no
    arithmetic the sheet cannot show.
    """
    label_fmt, money_fmt = styles
    collected_refs, applied_ref = refs
    _merge(ws, row, 0, _BALANCE_FIRST_COL - 1, label, label_fmt)
    if collected_refs:
        parts = "+".join(collected_refs)
        _formula(ws, row, _BALANCE_FIRST_COL, f"={parts}", money_fmt, cached[0])
    else:
        _write(ws, row, _BALANCE_FIRST_COL, 0, money_fmt)
    if applied_ref:
        _formula(
            ws, row, _BALANCE_FIRST_COL + 1, f"={applied_ref}", money_fmt, cached[1]
        )
    else:
        _write(ws, row, _BALANCE_FIRST_COL + 1, 0, money_fmt)
    _formula(
        ws,
        row,
        _BALANCE_FIRST_COL + 2,
        f"={_a1(row, _BALANCE_FIRST_COL)}-{_a1(row, _BALANCE_FIRST_COL + 1)}",
        money_fmt,
        cached[2],
    )


def _write_circuit(ws, fmt, circuit, start):
    """One receipt of one customer. Returns `(balance row, next free row)`."""
    _level2(
        ws,
        fmt,
        start,
        "{} — Recibo {} ({})".format(
            circuit.get("kind_label") or "",
            circuit.get("receipt_reference") or "",
            circuit.get("receipt_state_label") or "",
        ),
    )
    cursor = start + 1
    document_subtotal, cursor = _write_document_block(ws, fmt, circuit, cursor)
    collected_refs = []
    for block in circuit.get("voucher_blocks") or ():
        subtotal, cursor = _write_voucher_block(ws, fmt, block, cursor)
        collected_refs.append(_a1(subtotal, _VOUCHER_APPLIED_COL))
    cursor = _write_cash_block(ws, fmt, circuit, cursor)
    balance = cursor
    _write_money_line(
        ws,
        fmt,
        balance,
        "Balance {} — Cobrado / Aplicado / A Cuenta".format(
            circuit.get("kind_label") or ""
        ),
        (collected_refs, _a1(document_subtotal, _DOCUMENT_APPLIED_COL)),
        (
            circuit.get("total_values") or 0.0,
            circuit.get("total_applied") or 0.0,
            circuit.get("amount_on_account") or 0.0,
        ),
        (fmt["balance"], fmt["balance_money"]),
    )
    # A blank row before the next circuit, so two receipts never abut.
    return balance, balance + 2


def _write_customer(ws, fmt, customer, start):
    """One customer band, their circuits, their total. Returns `(total, next)`."""
    code = customer.get("code") or ""
    name = customer.get("name") or ""
    heading = "Cliente — " + "  ".join(part for part in (code, name) if part)
    note = customer.get("note") or ""
    if note:
        heading = f"{heading}  — {note}"
    _level1(ws, fmt, start, heading)
    cursor = start + 1
    balances = []
    for circuit in customer.get("circuits") or ():
        balance, cursor = _write_circuit(ws, fmt, circuit, cursor)
        balances.append(balance)
    total = cursor
    _write_money_line(
        ws,
        fmt,
        total,
        "Total {} — Cobrado / Aplicado / A Cuenta".format(
            "  ".join(part for part in (code, name) if part)
        ),
        (
            [_a1(row, _BALANCE_FIRST_COL) for row in balances],
            "+".join(_a1(row, _BALANCE_FIRST_COL + 1) for row in balances),
        ),
        (
            customer.get("total_collected") or 0.0,
            customer.get("total_applied") or 0.0,
            customer.get("total_on_account") or 0.0,
        ),
        (fmt["customer_total"], fmt["customer_total_money"]),
    )
    return total, total + 2


def _write_customers(ws, fmt, payload, start):
    """Every customer, stacked in code order. Returns `(grand total, next)`."""
    blocks = payload.get("customer_blocks") or []
    cursor = start
    totals_rows = []
    for customer in blocks:
        total, cursor = _write_customer(ws, fmt, customer, cursor)
        totals_rows.append(total)
    grand = cursor
    totals = payload.get("customer_totals") or {}
    # One term per customer: ~400 customers before Excel's 8192-char formula
    # limit, the same ceiling the Planilla's own grand totals have.
    _write_money_line(
        ws,
        fmt,
        grand,
        "Total General — Cobrado / Aplicado / A Cuenta",
        (
            [_a1(row, _BALANCE_FIRST_COL) for row in totals_rows],
            "+".join(_a1(row, _BALANCE_FIRST_COL + 1) for row in totals_rows),
        ),
        (
            totals.get("total_collected") or 0.0,
            totals.get("total_applied") or 0.0,
            totals.get("total_on_account") or 0.0,
        ),
        (fmt["grand_total"], fmt["grand_total_money"]),
    )
    return grand, grand + 2


def _write_unassigned(ws, fmt, payload, start):
    """Sheet money no receipt claimed. Returns `(total row, next free row)`."""
    section = payload.get("unassigned") or {}
    blocks = section.get("blocks") or []
    _level1(ws, fmt, start, "Valores sin asignar")
    cursor = start + 1
    refs = []
    for block in blocks:
        subtotal, cursor = _write_voucher_block(
            ws, fmt, block, cursor, applied_header="Libre"
        )
        refs.append(_a1(subtotal, _VOUCHER_APPLIED_COL))
    total = cursor
    _merge(
        ws, total, 0, _VOUCHER_AMOUNT_COL, "Total sin asignar", fmt["customer_total"]
    )
    cached = section.get("subtotal_free_amount") or 0.0
    if refs:
        _formula(
            ws,
            total,
            _VOUCHER_APPLIED_COL,
            "=" + "+".join(refs),
            fmt["customer_total_money"],
            cached,
        )
    else:
        _write(ws, total, _VOUCHER_APPLIED_COL, 0, fmt["customer_total_money"])
    return total, total + 2


def _write_recon(ws, fmt, payload, start, assigned_row, free_row):
    """Assigned + free + replaced against the sheet's own voucher total.

    The first two components reference the totals above rather than repeat them,
    so the reconciliation cannot drift from the rows it summarises. Returns the
    last row written.
    """
    recon = payload.get("recon") or {}
    _level1(ws, fmt, start, "Conciliación con la planilla")
    col = _VOUCHER_APPLIED_COL
    component_rows = {}
    row = start + 1
    for label, key, reference in (
        ("Asignado a recibos", "assigned_total", _a1(assigned_row, _BALANCE_FIRST_COL)),
        ("Sin asignar", "unassigned_total", _a1(free_row, col)),
        ("Efectivo reemplazado", "replaced_total", None),
    ):
        _merge(ws, row, 0, col - 1, label, fmt["recon_row"])
        cached = recon.get(key) or 0.0
        if reference is None:
            _write(ws, row, col, cached, fmt["recon_row_money"])
        else:
            _formula(ws, row, col, f"={reference}", fmt["recon_row_money"], cached)
        component_rows[key] = row
        row += 1
    _merge(ws, row, 0, col - 1, "Total calculado", fmt["sub_rule"])
    _formula(
        ws,
        row,
        col,
        "=" + "+".join(_a1(component_rows[key], col) for key in _RECON_COMPONENTS),
        fmt["sub_rule_money"],
        recon.get("computed_total") or 0.0,
    )
    computed_row = row
    row += 1
    _merge(ws, row, 0, col - 1, "Total de la planilla", fmt["sub_rule"])
    _write(ws, row, col, recon.get("sheet_total") or 0.0, fmt["sub_rule_money"])
    sheet_row = row
    row += 1
    # The punchline wears the Planilla's own banner colour: green when the sheet
    # closes, amber or red when it does not.
    status = recon.get("status") or "balanced"
    if f"diff_{status}" not in fmt:
        status = "balanced"
    _merge(ws, row, 0, col - 1, "Diferencia", fmt[f"diff_{status}"])
    _formula(
        ws,
        row,
        col,
        f"={_a1(computed_row, col)}-{_a1(sheet_row, col)}",
        fmt[f"diff_{status}_money"],
        recon.get("difference") or 0.0,
    )
    ws.set_row(row - 1, 22)
    return row


# ----------------------------------------------------------------------
# Workbook
# ----------------------------------------------------------------------


def _page_setup(
    ws, widths, last_row, last_col, *, freeze_row, repeat_first, repeat_last
):
    for index, width in enumerate(widths):
        ws.set_column(index, index, width)
    ws.freeze_panes(freeze_row, 0)
    ws.set_landscape()
    ws.set_paper(9)
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(repeat_first, repeat_last)
    ws.print_area(0, 0, last_row - 1, last_col)
    ws.set_margins(0.3, 0.3, 0.4, 0.4)


def _build_xlsx(payload):
    """Render the Asignaciones workbook from payload primitives. No ORM access.

    Uses the Planilla's workbook options, so board notes, names and numbers
    are written as text and never become live formulas or hyperlinks.
    """
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True, **WORKBOOK_OPTIONS})
    try:
        fmt = _formats_with_extras(workbook)
        summary = workbook.add_worksheet(SUMMARY_SHEET)
        _write_band(summary, fmt, payload, SUMMARY_TITLE, SUMMARY_LAST_COL)
        summary_start = _write_info(summary, fmt, payload, 6, SUMMARY_LAST_COL)
        summary_last = _write_summary(
            summary, fmt, payload, summary_start, SUMMARY_LAST_COL
        )
        _page_setup(
            summary,
            SUMMARY_WIDTHS,
            summary_last,
            SUMMARY_LAST_COL,
            freeze_row=summary_start + 1,
            repeat_first=summary_start,
            repeat_last=summary_start,
        )
        customers = workbook.add_worksheet(CUSTOMER_SHEET)
        _write_band(customers, fmt, payload, CUSTOMER_TITLE, CUSTOMER_LAST_COL)
        assigned_row, cursor = _write_customers(customers, fmt, payload, 6)
        free_row, cursor = _write_unassigned(customers, fmt, payload, cursor)
        customers_last = _write_recon(
            customers, fmt, payload, cursor, assigned_row, free_row
        )
        # No autofilter here: the sheet stacks customer, circuit, block, subtotal
        # and balance rows, so filtering would hide rows the SUMs still count.
        # The membrete is frozen and repeated instead.
        _page_setup(
            customers,
            CUSTOMER_WIDTHS,
            customers_last,
            CUSTOMER_LAST_COL,
            freeze_row=5,
            repeat_first=0,
            repeat_last=4,
        )
    finally:
        workbook.close()
    return output.getvalue()


class CollectionReceiptAssignmentXlsx(models.AbstractModel):
    _name = "collection.receipt.assignment.xlsx"
    _description = "Collection Receipt Assignment XLSX"

    @api.model
    def _render_xlsx(self, payload):
        """Return .xlsx bytes for an Asignaciones payload (no ORM)."""
        return _build_xlsx(payload)
