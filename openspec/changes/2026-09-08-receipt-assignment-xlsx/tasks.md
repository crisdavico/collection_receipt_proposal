# Tasks: Receipt Assignment XLSX

<!-- prettier-ignore-start -->

## Review Workload Forecast

Lines: 900-1000 (about 350 source, about 550 tests). Split: one PR to addon `master`.

Decision needed before apply: No
Chained PRs recommended: No
400-line budget risk: Medium (tests carry most of the diff)

### Suggested Work Units

No `collection/` edits. Docstrings `"""RED/GREEN: <what>."""`. Test:
`invoke test -m collection_receipt_proposal --mode=update`. Runtime: Doodba
TransactionCase.

| Unit | Goal | Focused test command | Rollback boundary |
|---|---|---|---|
|1|Payload + per-circuit status|`:TestReceiptAssignmentReport`|`models/collection_assignment_report.py`, `_proposal_kind_status`|
|2|Workbook builder|`:TestReceiptAssignmentXlsxBuilder`, `:TestReceiptAssignmentXlsxRender`|`report/`|
|3|Button + docs|`:TestReceiptProposalUi`|view, AGENTS, readme|

## Phase 1: Payload

- [x] 1.1 RED `tests/test_receipt_assignment_report.py` — figures mirror
      `_proposal_kind_figures`; row order; empty circuit skipped; funded circuit kept;
      totals; header context.
- [x] 1.2 RED same file — `_proposal_kind_status` ladder branches and `cerrado`.
- [x] 1.3 RED same file — gating (`open`, `submitted`, `cancelled`, unsaved, mixed
      currencies) and `closed` availability.
- [x] 1.4 RED same file — detail blocks keep FIFO, drop `amount_applied` 0, subtotals.
- [x] 1.5 RED same file — action `act_url`, attachment name/mimetype, idempotence,
      Planilla attachment untouched.
- [x] 1.6 GREEN `models/collection_allocation.py` — `_proposal_kind_status`.
- [x] 1.7 GREEN `models/collection_assignment_report.py` — allocation entry/detail plus
      sheet payload, gate, totals and `action_print_receipt_assignment_xlsx`;
      `models/__init__.py`.

## Phase 2: Workbook

- [x] 2.1 RED `tests/test_receipt_assignment_xlsx.py` — sheet names, headers, first data
      row, footer formulas and cached values, dates/money formats, freeze/page setup,
      membrete, empty payload, `_render_xlsx`, no `sudo(`.
- [x] 2.2 GREEN `report/collection_receipt_assignment_xlsx.py` + `report/__init__.py` +
      root `__init__.py`; reuse `collection`'s `_formats` and cell helpers.

## Phase 3: Button and docs

- [x] 3.1 RED `tests/test_receipt_proposal_ui.py` — button gated on `proposal`/`closed`,
      injected after `action_open_receipt_proposal`, before `action_print_xlsx`.
- [x] 3.2 GREEN `views/collection_receipt_proposal_views.xml`.
- [x] 3.3 `__manifest__.py` to `19.0.1.1.0`; `AGENTS.md` map + domain rules;
      `readme/DESCRIPTION.md` (regenerate `README.rst` via pre-commit).

## Phase 4: Recibos (revision, 2026-09-09)

Replaces `Detalle` with the receipt-centric `Recibos` sheet. Same rollback boundaries as
phases 1 and 2; still no `collection/` edits.

- [x] 4.1 GREEN `models/collection_voucher.py` — `_receipt_assignment_value_row` and the
      `_local_datetime` helper; RED first in `:TestReceiptAssignmentReport`.
- [x] 4.2 GREEN `models/collection_assignment_report.py` — `_receipt_assignment_labels`,
      `_receipt_assignment_receipt_map`, `_receipt_assignment_cash_map` (one search each
      for the whole sheet).
- [x] 4.3 GREEN same file — `_receipt_assignment_documents` (renamed from
      `_receipt_assignment_detail`, always-present subtotals), `_receipt_assignment_values`,
      `_receipt_assignment_cash`, `_receipt_assignment_receipt_block`; `receipt_blocks`
      and `receipt_totals` replace `detail_blocks` / `detail_totals`.
- [x] 4.4 GREEN same file — `_receipt_assignment_unassigned` and
      `_receipt_assignment_recon`; customer codes now over the allocation/voucher partner
      union so an unassigned voucher still sorts by code.
- [x] 4.5 GREEN `report/collection_receipt_assignment_xlsx.py` — drop the module-global
      `LAST_COL`, thread `last_col`, generalize `_page_setup`, add `_receipt_formats` and
      `_minor`. `Resumen` unchanged.
- [x] 4.6 GREEN same file — band, documents, values, cash, closing, grand total,
      unassigned, recon; no autofilter on `Recibos`.
- [x] 4.7 RED/GREEN `tests/test_receipt_assignment_report.py` and
      `tests/test_receipt_assignment_xlsx.py` — 27 new tests; the four `detail_*` tests
      move to `receipt_blocks` / `document_rows` / `receipt_totals`.
- [x] 4.8 FIX `tests/common.py` — `_confirm` called `action_declare_cash(0.0, 0.0)`
      against a one-argument signature, erroring six pre-existing tests as well as the
      new replacement scenarios.
- [x] 4.9 `__manifest__.py` to `19.0.1.2.0`; `AGENTS.md` map, repository row and four new
      domain rules; `readme/DESCRIPTION.md` (regenerate `README.rst` via pre-commit).

## Phase 5: Clientes (revision, 2026-09-09)

Replaces the flat `Recibos` grid with the Planilla-shaped `Clientes` sheet, nested by
customer. Same rollback boundaries as phases 1 and 2; still no `collection/` edits.

- [x] 5.1 GREEN `models/collection_assignment_report.py` — module-level `_voucher_blocks`
      grouping helper, in `_collection_report_voucher_blocks`' block order.
- [x] 5.2 GREEN same file — `_receipt_assignment_circuit` (was `_receipt_assignment_receipt_block`),
      `_receipt_assignment_value_blocks` now per type, `_receipt_assignment_documents`
      carrying a per-row `commission`.
- [x] 5.3 GREEN same file — `_receipt_assignment_customer_block`; `customer_blocks` and
      `customer_totals` replace `receipt_blocks` / `receipt_totals`; `recon` reads
      `total_collected`.
- [x] 5.4 GREEN same file — `_receipt_assignment_unassigned` groups by type too, sorting
      before grouping so each block keeps the report's one order.
- [x] 5.5 GREEN `report/collection_receipt_assignment_xlsx.py` — nine columns
      (`CUSTOMER_LAST_COL` 8), three heading levels (`section` / `band` / `minor`),
      `_VOUCHER_SHAPES` per payment method, `_write_typed`, and `_write_money_line` as the
      one writer behind every balance and total. `Resumen` unchanged.
- [x] 5.6 RED/GREEN both test files reworked — 27 builder tests and 40 payload tests,
      including a guard that every voucher shape fills the middle columns exactly and one
      that the three heading levels stay visually distinct.
- [x] 5.7 `__manifest__.py` to `19.0.1.3.0`; `AGENTS.md` map plus six domain rules;
      `readme/DESCRIPTION.md` (regenerate `README.rst` via pre-commit).

## Phase 6: Palette (revision, 2026-09-09)

Measured the shipped fills and found three duplicate pairs: the circuit band and the
column header at 1.02x, the block heading and the subtotal at 1.05x, and the customer band
and both totals identical. Everything sat at either L≈0.85 or L≈0.07, so there was no
hierarchy to read.

- [x] 6.1 GREEN `report/collection_receipt_assignment_xlsx.py` — replace the ad-hoc fills
      with a measured ladder: `LVL1_FILL` / `LVL2_FILL` / `LVL3_FILL` monotonic and ≥1.4x
      apart, `SUB_FILL` quiet with a navy top rule, `BALANCE_FILL` dark, customer and
      grand total ranked by size, `ZEBRA_FILL` at ~1.1x, `FLAG_FONT` darkened to clear AA.
- [x] 6.2 GREEN same file — `_level1` / `_level2` / `_level3` replace `_section` / `_band`
      / `_minor` on Clientes; `_cell` picks the zebra variant; `_write_typed` takes the row
      index; a blank row now follows each circuit.
- [x] 6.3 GREEN same file — reconciliation components get their own quiet row style, and
      the Diferencia row takes `collection`'s `_BANNER_FILL` by status.
- [x] 6.4 GREEN `models/collection_assignment_report.py` — `recon["status"]`, two states
      only, since this report has no benign non-zero difference.
- [x] 6.5 RED/GREEN `tests/test_receipt_assignment_xlsx.py` — six new tests: four distinct
      monotonic heading fills, the palette ladder plus a 1.25x adjacency and 4.5:1 AA floor
      on the constants, zebra subtlety, escalating totals, quiet recon components, the
      banner colour both ways, and the circuit spacer.
- [x] 6.6 `AGENTS.md` palette rule plus the additive-`_receipt_formats` rule;
      `readme/DESCRIPTION.md`; spec requirement and two scenarios.

## Verification

- [x] `invoke test -m collection_receipt_proposal --mode=update` — 36 new tests pass;
      3 failed / 5 errors of 176 equals the pre-change baseline of 3 / 5 of 140
- [x] Revision: `invoke test -m collection_receipt_proposal --mode=update` — all 63
      Asignaciones tests pass; 3 failed / 1 error of 204, down from the 3 / 5 baseline
      because 4.8 unblocked six pre-existing tests. The four survivors are untouched by
      this change: `test_sheet_company_rule_still_guards_the_board`, and the three
      `test_receipt_proposal_order` guards that catch `collection`'s
      `_compute_line_ids` having lost its FIFO sort and `document_numbers` having been
      dropped from `collection.receipt`.
- [x] Revision: `invoke test -m collection --mode=update` — 0 failed / 0 errors of 962.
- [x] Revision: `pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**`
      clean.
- [x] Clientes revision: `invoke test -m collection_receipt_proposal --mode=update` — all
      67 Asignaciones tests pass; 3 failed / 1 error of 209, the same four survivors,
      none of them touched by this change.
- [x] Clientes revision: `pre-commit run` clean over every changed file.
- [x] Palette revision: `invoke test -m collection_receipt_proposal --mode=update` — all
      73 Asignaciones tests pass; 3 failed / 1 error of 215, the same four survivors.
      `invoke test -m collection --mode=update` still 0 / 0 of 965, confirming the
      additive format set left the Planilla untouched. `pre-commit run` clean.
      (`document_numbers`, FIFO vs `line_ids`, company-rule RPC, cash replacement).
- [x] `invoke test -m collection --mode=update` — 3 failures / 8 errors of 962 against a
      baseline of 3 / 9 of 962; the set rotates between runs (pre-existing flakiness in
      declare-cash / migration / replacement tests, plus a manifest expecting 1.45.0).
      `TestCollectionUi` passes in isolation, 67 tests.
- [x] `pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**` —
      clean; the two pylint-odoo warnings (`except-pass`, author `Eynes`) pre-date this
      change.
<!-- prettier-ignore-end -->
