# Proposal: Receipt Assignment XLSX

## Proposal question round

Settled with the requester before apply:

- Structure: two worksheets — `Resumen` (one row per customer x circuit) and `Clientes`,
  written in the Planilla de Cobranza's own visual language and nested by customer. Each
  customer's circuits are their receipts; each circuit shows its imputed documents, then
  the vouchers that funded it as one `Comprobantes — <tipo>` block per payment method,
  then any cash a remittance replaced, then its balance. Balances chain up into a customer
  total and a sheet total, and the sheet closes with the money no receipt claimed and a
  reconciliation against the sheet's own voucher total.
- Gating: header button visible on sheet `proposal` **and** `closed`.
- Host: this addon (`collection_receipt_proposal`); `collection/` is not edited.
- Document rows: only `amount_applied > 0`, the receipt's own definition of an
  assignment. Unimputed debt stays visible as `Pendiente` on `Resumen`.
- Voucher columns: nine columns, and each payment method reshapes the four middle ones to
  the fields it actually has — a cheque prints bank/type/both dates, a transfer its two
  accounts, a retention its kind. Generalises `collection`'s own
  `_VOUCHER_BLOCK_COLUMNS`. The `ocr_*` and `seller_*` declared sets stay out; Document
  Review owns that comparison.
- Split money: both `voucher.amount` and the share applied to this receipt are shown, but
  only the applied share is ever subtotalled, and a row where the two differ is
  highlighted.

### Revision — 2026-09-09

Two passes on the same gap. The first apply shipped `Resumen` + `Detalle`, which showed
*what* was imputed but never *what paid for it*: no voucher, no cheque detail, no
replacement ledger, and no way to see a voucher split across receipts.

The second pass added all of that as a flat eighteen-column `Recibos` grid — complete,
but nothing like the report it sits next to. On review the requester asked for
`action_print_xlsx`'s shape instead, with the information organised per customer. So the
sheet was rebuilt as `Clientes`: the Planilla's nine-column sectioned layout, three
heading levels, per-type voucher blocks, and totals that reference the cells beneath them
rather than restate them. `Detalle` and `Recibos` are both gone.

The spec was never promoted to `openspec/specs/`, so this change is revised in place
rather than superseded.

## Intent

The board writes the validated imputacion into `collection.*`, but the result never
leaves Odoo: an operator cannot review it offline, hand it to administration or file it
with the close. `collection`'s Planilla de Cobranza answers a different question
(vouchers and cash reconciliation), so the imputacion per customer and circuit has no
export at all.

## Scope

### In Scope

- `collection.sheet._receipt_assignment_report_data()` — payload of primitives built
  from `_proposal_kind_figures` / `_proposal_kind_lines` / `_proposal_kind_status`,
  `collection`'s `_collection_report_customer_codes` and `_collection_report_code_sort`.
- `collection.allocation._receipt_assignment_entry()` / `_receipt_assignment_detail()`.
- `collection.allocation._proposal_kind_status()` — the existing status ladder
  restricted to one circuit.
- `collection.receipt.assignment.xlsx` AbstractModel + ORM-free `_build_xlsx`, reusing
  `collection.report.collection_sheet_xlsx` formats and cell helpers.
- `action_print_receipt_assignment_xlsx` — `ir.attachment` on the sheet plus
  `ir.actions.act_url`, mirroring `action_print_xlsx`.
- Inherited header button, injected after `action_open_receipt_proposal`.
- TransactionCase coverage (`strict_tdd`) for payload, gating, action and workbook.

### Out of Scope

- Any change under `collection/`, including its Planilla and its attachment name.
- A vouchers/values worksheet, a QWeb PDF, an MCP tool, accounting or ERP push.
- New models, fields, groups, ACL rows or record rules.

## User impact

A sheet in `proposal` (and afterwards in `closed`) shows **Exportar Asignaciones** in
the form header; it downloads `<REFERENCE>-asignaciones.xlsx` and stores it as an
attachment on the sheet, replacing its previous copy. Nothing else in the board or the
Planilla changes.

## MCP contract

Unchanged. No `@mcp_tool` is added, renamed or removed, and no `muk_mcp.tool` row is
created. The export is reachable only from the sheet form.

## Risks

- **Header button order.** `collection`'s `test_collection_ui` and this addon's
  `test_receipt_proposal_ui` both assert `action_print_xlsx` is the last
  `type="object"` header button. Mitigated by injecting after
  `action_open_receipt_proposal` and asserting the order in a new test.
- **Cross-addon private imports.** The builder imports `_formats` and the cell helpers
  from `collection.report.collection_sheet_xlsx`, and `_SHEET_STATE_LABELS` from
  `collection.models.collection_sheet_report`. Deliberate: one visual language and one
  Spanish state label. `depends: ["collection"]` already makes this a hard dependency.
- **Figure drift.** Every amount comes from a board helper; the report computes none of
  its own, and the detail never re-sorts `_proposal_kind_lines`.

## Rollback

Read-only and additive: no schema, no data, no security change. Reverting the commit
and upgrading the addon removes the button and the two models' methods; previously
generated `.xlsx` attachments stay on their sheets and can be deleted by hand.
