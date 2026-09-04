# Proposal: Collection Receipt Proposal

## Proposal question round

Skipped (automatic).

- Addon: sibling `collection_receipt_proposal`; depends `collection`; `19.0.1.0.0`;
  AGPL-3; not an application.
- Data: write existing `collection.*`; no parallel schema. Board: sheet=`proposal`;
  column=allocation; FAC/PRE=`invoice`/`quotation`; card=`receipt.value`;
  container=`receipt`; documento=`allocation.line`; Imputado=`amount_applied`; sin
  imputar=`amount_on_account`; pool=free voucher amount.
- Splits: same-sheet cross-customer while installed; sheet-wide
  `currency.compare_amounts` cap; `allocation_id`=largest share.
- FIFO: `(due_date or date.max, invoice_number or "")`; ceiling `invoice_balance`;
  recompute discards Imputar; closed frozen.
- Audit/UI: immutable `collection.receipt.proposal.event`; gated create; no sudo/new
  groups; company `ir.rule`. OWL mirrors document_review; views English; OWL Spanish; no
  `i18n/`.
- Honor: ERP issues; Odoo groups; voucher MAY split via `receipt.value`;
  `total_values >= total_applied`; no junction/paid-doc/sequence/PDF/fiscal.
- Out: reports/XLSX/PDF; accounting; `action_close` ERP push; `document_numbers`
  stale-order; retention OCR; cash-declared.

## Intent

Operators lack a proposal-state board to distribute a confirmed sheet’s money across
customers and FAC/PRE. This addon writes the validated imputación into existing
`collection.*` rows before Close (sheet view, same-sheet splits, FIFO, audit).

## Scope

### In Scope

- Inherit receipt.value, voucher, allocation, sheet; new proposal.event; OWL board + RPC
- FIFO preview/recompute, close/reopen, status; same-sheet splits + cap + owner re-point
- ACL/`ir.rule`; TransactionCase (`strict_tdd`); header button before
  `action_print_xlsx`

### Out of Scope

Locks Out, plus parallel schema, `i18n/`, new groups, `sudo()`, Nebula-agent, and
editing `collection/` except via `_inherit`.

## Capabilities

### New Capabilities

- `receipt-proposal-board`: proposal-sheet entry, RPC, OWL board, payload, pool cards
- `receipt-proposal-fifo`: FIFO engine, preview/recompute, close/reopen, status computes
- `receipt-proposal-events`: immutable audit events
- `receipt-proposal-splits`: same-sheet cross-customer splits, sheet-wide cap,
  `allocation_id` re-point

### Modified Capabilities

None

## Approach

Inherit collection models. While installed, relax `_check_same_allocation` to same-sheet
and widen `_check_voucher_split_cap` sheet-wide. FIFO is Python-only (`@api.private`)
and MUST match `collection.receipt._compute_line_ids`. Each mutation validates, mutates,
re-points, recomputes, logs, and returns the board. OWL mirrors `document_review`.

## Affected Areas

New inherit: `models/collection_receipt_value.py`, `collection_voucher.py`,
`collection_allocation.py`, `collection_sheet.py`. New:
`collection_receipt_proposal_event.py`, `static/src/receipt_proposal/`, `views/`,
`security/`, `tests/`.

## Risks

- High: same-sheet split weakens collection receipts invariant — sheet-scope + cap
  tests; re-run `collection` suite.
- Med: `allocation.total_vouchers` approximate after split — re-point largest share;
  report follow-up later.
- Med: stored `document_numbers` write amplification — accept; query-count later if
  boards grow.

## Rollback Plan

Uninstall `collection_receipt_proposal`. Inherited constraints revert; event table
drops; `collection.*` money rows remain. Do not revert `collection`.

## Dependencies

- `collection` (receipts/values/kinds shipped)
- Doodba `private/` addons path (no `addons.yaml` change)

## Success Criteria

- [ ] Board opens on proposal sheets; mapping matches locks
- [ ] FIFO matches `_compute_line_ids`; ceiling `invoice_balance`; recompute idempotent,
      overwrites Imputar; closed frozen
- [ ] Same-sheet split persists; cross-sheet and over-cap refuse; `allocation_id`
      follows largest share
- [ ] Events immutable (gated create; write/unlink refuse); no `sudo()`; no new groups;
      company `ir.rule`
- [ ] Both addons pass update-mode tests; XLSX button stays last
