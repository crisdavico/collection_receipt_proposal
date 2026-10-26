# Receipt Assignment Report Specification

## Purpose

Export the validated proposal of a `collection.sheet` as a two-worksheet XLSX so the
imputacion per customer and circuit can be reviewed, handed over and archived outside
Odoo. `Clientes` reads in the Planilla de Cobranza's own visual language, nested by
customer: each customer's circuits are their `collection.receipt` records, and each shows
the documents it imputed and the payment vouchers that funded it, with all their
information. The report is read-only: it recomputes nothing the board does not already
own.

## ADDED Requirements

### Requirement: Sheet state gate

`_receipt_assignment_report_data` MUST raise `UserError` unless the sheet is saved and
its `state` is `proposal` or `closed`. It MUST raise `UserError` when its allocations
span more than one currency.

#### Scenario: Refused before the proposal exists

- GIVEN a collection sheet in `open`, and the same sheet in `submitted`
- WHEN the payload is requested
- THEN `UserError` MUST be raised in both states

#### Scenario: Available after the close

- GIVEN a sheet whose proposal was closed (`state` = `closed`)
- WHEN the payload is requested
- THEN it MUST be returned, with `state_label` "Cerrada"

#### Scenario: Mixed currencies refused

- GIVEN a sheet with two allocations in different currencies
- WHEN the payload is requested
- THEN `UserError` MUST be raised

### Requirement: One summary row per customer and circuit

The payload MUST carry one `summary_rows` entry per `(allocation, document_kind)` whose
circuit holds collected money or documents, and MUST omit a circuit that holds neither.
Every amount MUST equal `_proposal_kind_figures` for that pair: `collected`, `applied`,
`on_account` = `available`, `debt_total` = `total`, `pending`. Rows MUST be ordered by
`_collection_report_code_sort` and then `invoice` before `quotation`.

#### Scenario: Figures mirror the board

- GIVEN a customer whose invoice circuit collected 150 against 200 of debt
- WHEN the payload is built
- THEN that row's five amounts MUST equal `_proposal_kind_figures("invoice")`

#### Scenario: Empty circuit omitted, funded circuit kept

- GIVEN a customer with no quotation documents and no quotation money
- AND another customer with quotation money but no quotation documents
- WHEN the payload is built
- THEN the first customer MUST have no quotation row
- AND the second MUST have one, with `applied` 0 and `on_account` equal to `collected`

#### Scenario: Totals add up

- GIVEN any payload
- WHEN `summary_totals` and `kind_totals` are read
- THEN each key MUST equal the sum of the matching `summary_rows` values

### Requirement: Per-circuit status

`_proposal_kind_status` MUST return `_proposal_status_value`'s ladder restricted to one
circuit, using that circuit's own `pending` as its debt: `cerrado` when the customer is
closed on the board, then `sin_iniciar`, `cruce`, `a_favor`, `deuda`, `conciliado`,
`parcial`. Comparisons MUST use `_proposal_compare`.

#### Scenario: Ladder branches

- GIVEN one circuit with 200 of debt
- WHEN nothing is applied, THEN the status MUST be `sin_iniciar`
- WHEN 150 is applied and 50 remains, THEN it MUST be `deuda`
- WHEN 200 is applied and nothing remains, THEN it MUST be `conciliado`
- WHEN 250 is collected and 200 applied, THEN it MUST be `a_favor`
- WHEN more is applied than collected, THEN it MUST be `cruce`
- WHEN money and debt both remain, THEN it MUST be `parcial`

#### Scenario: Closed customer overrides the figures

- GIVEN a customer closed on the board with a difference and a note
- WHEN the payload is built
- THEN the row's circuit status MUST read "Cerrado"
- AND the row MUST carry the closing note

### Requirement: Customers nest their circuits

`customer_blocks` MUST carry one block per allocation that has at least one circuit to
simulate, ordered by `_collection_report_code_sort`, each with `code`, `name`,
`closed`, `note` and a `circuits` list in `invoice` then `quotation`
order. Reading `(customer, circuit)` pairs off `customer_blocks` MUST yield a subsequence
of the same pairs read off `summary_rows`, so the two worksheets can never disagree on
order.

A `circuits` entry MUST exist only where the `collection.receipt` exists and holds either
values or imputed documents; a pair with no receipt MUST have a summary row and no
circuit. Each entry MUST carry `receipt_reference` (`external_receipt_id`, else the id as
a string), `receipt_state`, `receipt_state_label`, and the receipt's own `total_values`,
`total_applied` and `amount_on_account`.

A customer's `total_collected`, `total_applied` and `total_on_account` MUST be the sum of
their circuits' three figures, and `customer_totals` the sum over every customer block, so
no total can disagree with the rows beneath it.

#### Scenario: Band mirrors the receipt

- GIVEN a funded invoice circuit
- WHEN the payload is built
- THEN the circuit's three totals MUST equal the `collection.receipt` fields of the same
  name
- AND `receipt_state_label` MUST read "Borrador" for a draft receipt

#### Scenario: Both circuits under one customer

- GIVEN a customer funded on both circuits
- WHEN the payload is built
- THEN one customer block MUST carry two circuits, `invoice` first
- AND the customer's totals MUST equal the sum of the two

#### Scenario: Order follows the summary

- GIVEN a sheet with three funded circuits across two customers
- WHEN the payload is built
- THEN the `(customer, circuit)` pairs MUST be a subsequence of the `summary_rows` pairs

#### Scenario: No receipt, no circuit

- GIVEN a sheet whose circuits are all unfunded
- WHEN the payload is built
- THEN `customer_blocks` MUST be empty and `customer_totals` MUST be zero

### Requirement: Document rows follow the money

`document_rows` MUST carry the lines of that circuit whose `amount_applied` is greater
than zero, in the order `_proposal_kind_lines` returns them, never re-sorted. Each row
MUST carry a `commission` rounded per row from the sheet's `commission_percent`, the way
`_collection_report_document_blocks` does it: on the untaxed share of what was applied
(`collection.sheet._collection_line_commission`), never on the gross applied amount. The keys `subtotal_invoice_balance`,
`subtotal_amount_applied` and `subtotal_commission` MUST always be present, `0.0` when
there are no rows, so the workbook's balance line can reference the subtotal row
unconditionally.

#### Scenario: FIFO order preserved and unapplied documents dropped

- GIVEN a circuit funded with 150 across documents of 100 and 100
- WHEN the payload is built
- THEN the document rows MUST be `[("FA-0001", 100), ("FA-0002", 50)]`
- AND the row order MUST equal `_proposal_kind_lines("invoice")` filtered on
  `amount_applied`

### Requirement: Vouchers grouped by type, carrying the whole voucher

A circuit's `voucher_blocks` MUST carry one block per `document_type` present on its
`collection.receipt.value` rows, in `_collection_report_voucher_blocks`' order: the
catalog order first, then whatever else the sheet carries, alphabetically. Rows keep
`collection.receipt.value._order` (`id`) and MUST NOT be re-sorted by the grouping. Each
block MUST carry `code`, `label` (resolved `_VOUCHER_BLOCK_LABELS` → catalog → selection
→ raw code), `rows`, `subtotal_applied`, `subtotal_voucher_amount` and `split_count`.

Every row MUST be built by `collection.voucher._receipt_assignment_value_row` and carry
`reference`, `document_id`, `partner_name`, `type_label`, `date`, `number`,
`voucher_amount`, `applied_amount`, `state_label`, `check_bank`, `check_type_label`,
`check_issue_date`, `check_payment_date`, `from_account`, `to_account`,
`retention_label`, `reviewed_by`, `reviewed_at` and `is_partial`, so any block shape can
be rendered from the one row. Cheque columns MUST be empty unless `document_type` is
`check`. `number` MUST fall back `voucher_number` then `check_number`; `date` MUST fall
back `voucher_date` then `create_date`. Datetimes MUST be naive in the reader's timezone.

`subtotal_applied` MUST sum `applied_amount`, never `voucher_amount`: a voucher split
across two receipts would otherwise be counted twice. A circuit's
`subtotal_values_applied` MUST equal `receipt.total_values`. `is_partial` MUST be a
currency-aware comparison of `applied_amount` against `voucher_amount`, and `split_count`
the number of such rows.

#### Scenario: A transfer and a cheque land in separate blocks

- GIVEN a receipt funded by a `bank_transfer` and by a `check`
- WHEN the payload is built
- THEN there MUST be two blocks, `bank_transfer` before `check`
- AND the transfer row's cheque columns MUST all be empty
- AND the cheque row MUST carry its bank, `check_type_label` "Diferido" and both dates
- AND the transfer block's `label` MUST read "Transferencia bancaria"

#### Scenario: Split voucher flagged on both sides

- GIVEN a voucher of 300 split 200 into the invoice circuit and 50 into the quotation
  circuit
- WHEN the payload is built
- THEN `is_partial` MUST be true in both circuits, each with `split_count` 1
- AND each `subtotal_values_applied` MUST equal that receipt's `total_values` and MUST
  NOT equal the sum of its `voucher_amount` values

#### Scenario: Voucher consumed whole

- GIVEN a voucher of 100 fully applied to one receipt
- WHEN the payload is built
- THEN `is_partial` MUST be false

### Requirement: Cash replacement ledger

`cash_rows` MUST carry the `collection.cash.replacement` rows of that receipt in `_order`
(`id`), each with `cash_reference`, `deposit_reference`, `amount`, `direction`,
`direction_label`, `created_by` and `created_at`, plus `subtotal_cash_amount`. Both keys
MUST always be present. They MUST be read through one sheet-wide
`_receipt_assignment_cash_map` search grouped by receipt: `collection.receipt` has no
inverse to that model, so reading them per receipt would be a search per receipt.

#### Scenario: A remittance replaces collected cash

- GIVEN a sheet whose cash voucher was replaced by a `seller_deposit`
- WHEN the payload is built
- THEN the receipt's `cash_rows` MUST hold one row with `direction_label` "Reemplazo",
  its two voucher references, its author and its timestamp

#### Scenario: One search for the whole sheet

- GIVEN two receipts on one allocation, each with a replacement
- WHEN `_receipt_assignment_cash_map` is called once
- THEN it MUST return both receipts keyed by id

### Requirement: Unassigned money and reconciliation

`unassigned["blocks"]` MUST carry every sheet voucher whose `proposal_free_amount` is
greater than zero, as a value row whose `applied_amount` is that free amount, grouped by
`document_type` into the same block shape a circuit uses. Rows MUST be sorted by
`_collection_report_code_sort` then voucher reference *before* grouping, so each block
keeps the report's one sort order. The section MUST carry `subtotal_voucher_amount` and
`subtotal_free_amount`. Unlike the board pool it MUST keep `seller_deposit`: the section
exists to close the reconciliation, so a remittance holding free money has to appear.

`recon` MUST carry `assigned_total` (`customer_totals["total_collected"]`),
`unassigned_total`, `replaced_total` (`sum(voucher.replaced_amount)`), their
`computed_total`, the `sheet_total` (`sum(voucher.amount)`) and the `difference`, every
figure rounded to the report currency. Because each voucher satisfies
`amount == assigned + free + replaced`, `difference` MUST be zero unless some voucher is
assigned beyond its own amount.

#### Scenario: Fully assigned voucher leaves the section

- GIVEN one voucher of 300 with 200 assigned and one of 100 fully assigned
- WHEN the payload is built
- THEN only the first MUST be listed, with `applied_amount` 100

#### Scenario: The sheet reconciles

- GIVEN any exportable sheet, with and without a cash replacement
- WHEN `recon` is read
- THEN `computed_total` MUST equal `assigned_total + unassigned_total + replaced_total`
- AND MUST equal `sheet_total`, leaving `difference` zero

### Requirement: Workbook

`collection.receipt.assignment.xlsx._render_xlsx(payload)` MUST return `.xlsx` bytes
built by a module-level `_build_xlsx` that touches no ORM. The workbook MUST hold exactly
the worksheets `Resumen` then `Clientes`, MUST reuse `collection`'s xlsxwriter formats,
MUST render dates as `DD/MM/YYYY`, datetimes as `DD/MM/YYYY HH:MM` and money as
`#,##0.00`, and MUST render an empty payload without raising. The two worksheets MUST
carry independent column geometries (`SUMMARY_LAST_COL` 10, `CUSTOMER_LAST_COL` 8)
threaded explicitly; no formula may reach past column Z, because `collection`'s `_a1` and
`_abs_range` are letter-based.

`Resumen` MUST keep its current layout: a `SUMIF` subtotal row per circuit and a `SUM`
total row, each carrying a cached value equal to the payload total, a frozen header row
and an autofilter.

`Clientes` MUST render three visually distinct heading levels — navy `section` for the
customer, a lighter `band` for the circuit, grey `minor` for a block within it. Per
customer, per circuit it MUST render a `Documentos imputados` block, then one
`Comprobantes — <tipo>` block per voucher type whose heading names the split count when
non-zero and whose partial rows are highlighted, then a `Reemplazos de efectivo` block
when the ledger is non-empty, then the circuit balance. It MUST then render the customer
total, and after every customer a sheet grand total, the `Valores sin asignar` section
and the `Conciliación con la planilla` block.

Each voucher type MUST declare its own column shape: a `date` column plus exactly
`_VOUCHER_AMOUNT_COL - 2` middle columns, each typed `text`, `date` or `datetime`. A
cheque MUST show `Nº Cheque`, `Banco`, `Tipo`, `Pago` and its issue date under `Emisión`;
a transfer or echeck MUST show both accounts; a retention certificate MUST show
`Tipo de Retención`. No type may carry a column that is always blank for it.

`Clientes` MUST colour by a ladder, not by decoration. The three heading levels MUST
lighten monotonically through one blue family and each adjacent pair of fills that touch
vertically MUST differ by at least 1.25x in WCAG contrast, with the column header lighter
than the block heading. Every fill/text pair MUST clear 4.5:1. Total levels MUST be ranked
by rule and typography rather than by additional fills: a quiet subtotal closed by a navy
top rule, a dark circuit balance band, and a customer total and grand total that share the
customer fill and differ by font size. Data rows MUST carry a stripe between 1.03x and
1.2x. The Diferencia row MUST take its fill from `collection`'s `_BANNER_FILL`, keyed on
`recon["status"]` — `balanced` when the difference rounds to zero, `outstanding`
otherwise. `_receipt_formats` MUST NOT override any key the shared `_formats` owns, so
`Resumen` and the Planilla are unaffected. A circuit MUST be followed by a blank row so
two receipts never abut.

Only the applied column is ever summed: column F in a document block, column I in a
voucher block. The voucher subtotal's label merge MUST swallow `Importe del Valor`, and
cash-replacement amounts MUST sit in their own column. Every balance and total MUST
reference the cells beneath it — the circuit balance the voucher and document subtotals,
the customer total its circuit balances, the grand total the customer totals, the
reconciliation the grand total and the unassigned total — and MUST carry the ORM's own
figure as its cached value. `Clientes` MUST NOT carry an autofilter — it would hide rows
the `SUM`s still count — and MUST freeze and repeat the membrete instead (`A6`, `1:5`).

#### Scenario: Two worksheets with a chain of cached totals

- GIVEN a payload with one customer, one circuit, two voucher blocks and a replacement
- WHEN the workbook is built
- THEN `sheetnames` MUST be `["Resumen", "Clientes"]`
- AND the circuit balance MUST read `=I<transfer subtotal>+I<check subtotal>` and
  `=F<document subtotal>`, with cached values equal to the circuit's `total_values` and
  `total_applied`
- AND the customer total MUST reference the balance row, and the grand total the customer
  total

#### Scenario: A cheque block reshapes

- GIVEN a receipt funded by a cheque
- WHEN the workbook is built
- THEN that block's headers MUST be Referencia, Emisión, Nº Cheque, Banco, Tipo, Pago,
  Estado, Importe del Valor, Aplicado

#### Scenario: A split voucher cannot be double-counted

- GIVEN a voucher block holding a split row
- WHEN the workbook is built
- THEN the subtotal row MUST hold a `SUM` in the applied column and nothing in
  `Importe del Valor`
- AND the split row's two money cells MUST be highlighted

#### Scenario: The ladder holds

- GIVEN any payload with one customer and one circuit
- WHEN the workbook is built
- THEN the customer, circuit, block and header rows MUST carry four different fills,
  lightening in that order
- AND the subtotal, circuit balance and customer total MUST carry three different fills
- AND the grand total MUST share the customer total's fill at a larger font size

#### Scenario: A sheet that does not close says so

- GIVEN a payload whose `recon["status"]` is `outstanding`
- WHEN the workbook is built
- THEN the Diferencia row MUST be red, and green when the status is `balanced`

#### Scenario: No autofilter on Clientes

- GIVEN any payload
- WHEN the workbook is built
- THEN `Clientes` MUST have no autofilter while `Resumen` MUST have one

#### Scenario: Empty payload

- GIVEN an empty payload
- WHEN the workbook is built
- THEN both worksheets MUST exist, the total rows MUST read zero, and the reconciliation
  block MUST still render

### Requirement: Download action

`action_print_receipt_assignment_xlsx` MUST store the workbook as an `ir.attachment` on
the sheet named `<REFERENCE>-asignaciones.xlsx` (slashes replaced by dashes) with the
spreadsheet mimetype, MUST delete its own previous attachment of that name before
creating the new one, MUST NOT touch the Planilla's `<REFERENCE>.xlsx` attachment, and
MUST return an `ir.actions.act_url` on `/web/content/<id>?download=true` with
`target` `download`. It MUST NOT call `sudo()`.

#### Scenario: Second export replaces the first

- GIVEN a sheet already exported once
- WHEN the action runs again
- THEN exactly one `-asignaciones.xlsx` attachment MUST remain on the sheet

#### Scenario: Both exports coexist

- GIVEN a sheet exported through the Planilla and through Asignaciones
- WHEN its attachments are listed
- THEN both `<REFERENCE>.xlsx` and `<REFERENCE>-asignaciones.xlsx` MUST be present

### Requirement: Header button placement

The sheet form MUST show an `Exportar Asignaciones` object button injected immediately
after `action_open_receipt_proposal`, invisible unless the sheet is saved and its state
is `proposal` or `closed`. `action_print_xlsx` MUST remain the last `type="object"`
button of the header.

#### Scenario: Order preserved

- GIVEN the combined `collection.sheet` form arch
- WHEN its header object buttons are listed
- THEN `action_print_receipt_assignment_xlsx` MUST precede `action_print_xlsx`
- AND `action_print_xlsx` MUST be last
