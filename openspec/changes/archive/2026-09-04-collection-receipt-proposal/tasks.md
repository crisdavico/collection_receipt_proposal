# Tasks: Collection Receipt Proposal

<!-- prettier-ignore-start -->

## Review Workload Forecast

Lines: 1800–2800. Split: PR 1→6 to addon `main`. Delivery: auto-chain.

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

Align files. No `collection/` or nebula-agent. Threat matrix N/A. One apply agent/phase. Docstrings `"""RED/GREEN: <what>."""`. Test: `invoke test -m collection_receipt_proposal --mode=update`. Runtime: Doodba TransactionCase.

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
|1|Event+ACL|1|command above|Doodba TC|event+ACL|
|2|Splits|2|split|same|value/voucher|
|3|FIFO|3|fifo+order|same|allocation/receipt|
|4|Board|4|board|same|sheet RPCs|
|5|OWL|5|ui|same; no HttpCase|static+views|
|6|Mutations|6|addon+collection+pre-commit|same+collection (Phase 2 relaxes a base invariant)|RPCs; uninstall|

## Phase 1: Foundation

- [x] 1.1 Align `tests/common.py` mixin (copy `TestCollectionReceipt` helpers; import collection fixtures; never subclass).
- [x] 1.2 RED `tests/test_receipt_proposal_events.py` — gated create; write/unlink refuse except cascade; newest-first.
- [x] 1.3 GREEN `models/collection_receipt_proposal_event.py`.
- [x] 1.4 RED ACL `1,0,1,0`; company `ir.rule`; no `sudo()`/groups.
- [x] 1.5 GREEN `security/ir.model.access.csv` + `collection_receipt_proposal_security.xml`.
- [x] 1.6 Align `__manifest__.py`, `models/__init__.py` (keep `collection_receipt` import), `AGENTS.md`, `readme/DESCRIPTION.md`.

## Phase 2: Splits + voucher helpers

- [x] 2.1 RED `tests/test_receipt_proposal_split.py` — same-sheet persist; cross-sheet refuse; UNIQUE + amount `> 0`.
- [x] 2.2 GREEN `models/collection_receipt_value.py` `_check_same_allocation`.
- [x] 2.3 RED sheet-wide cap (`currency.compare_amounts`); over-cap refuse; at-cap persist.
- [x] 2.4 GREEN `_check_voucher_split_cap` (sum all values; drop allocation filter).
- [x] 2.5 RED assigned/free/split computes + `_proposal_card_label`.
- [x] 2.6 GREEN `models/collection_voucher.py`.

## Phase 3: FIFO + receipt depends

- [x] 3.1 RED `tests/test_receipt_proposal_fifo.py` — `invoice_balance` ceiling; partial/surplus/no-docs; idempotent overwrite; closed frozen; overdraft self-heal.
- [x] 3.2 GREEN `models/collection_allocation.py` fifo_key/plan/preview/recompute; `proposal_closed`; `cerrado` (not `allocation.state`).
- [x] 3.3 RED `tests/test_receipt_proposal_order.py` — key matches `_compute_line_ids`; undated last; empty `""`.
- [x] 3.4 GREEN keep `models/collection_receipt.py` totals `depends=` (FIFO writes SQL-safe).

## Phase 4: Sheet RPC + board payload

- [x] 4.1 RED `tests/test_receipt_proposal_board.py` — `{sheet,columns,pool,events}`; synthetic pool; `_require_proposal_sheet` refuses bad ids/state/company; open action `params.sheet_id`.
- [x] 4.2 GREEN `models/collection_sheet.py` open, `_require_proposal_sheet`, `get_proposal_board`.
- [x] 4.3 RED previews do not persist (transfer, circuit, undo-split, **impute**).
- [x] 4.4 GREEN keep `preview_proposal_transfer|circuit|undo_split|impute`.

## Phase 5: OWL + views

- [x] 5.1 RED `tests/test_receipt_proposal_ui.py` — helpers pure (regex-assert, `_t` only); **omit `path`**; button after Document Review, XLSX last; Spanish OWL / English views.
- [x] 5.2 GREEN `receipt_proposal_helpers.esm.js` (`formatAmount`, `splitKind`, `cardClass`, `statusLabel`, `validateTransferAmount`, `transferButtonLabel`, `sanitizeBoardPayload`, `nextIsolate`, `CIRCUITS`).
- [x] 5.3 GREEN `receipt_proposal_action.esm.js` + `.xml` + `.scss` (document_review; DnD; 250 ms debounce).
- [x] 5.4 GREEN `views/collection_receipt_proposal_views.xml` — omit `path`.

## Phase 6: Actions + regression

- [x] 6.1 RED `tests/test_receipt_proposal_actions.py` — transfer/set_circuit/impute/close/reopen return full board; typed amount only; close note on difference.
- [x] 6.2 GREEN mutating RPCs: shrink-then-grow → **same-customer** owner (not overall; `_check_voucher_partners`) → FIFO → events → board.
- [x] 6.3 RED unify, undo-split, same-customer owner.
- [x] 6.4 GREEN those paths.
- [x] 6.5 RED mutation event types (auto_impute only if FIFO `changes`).
- [x] 6.6 GREEN `_proposal_log` + close/reopen.
- [x] 6.7 Run addon `--mode=update`, then `invoke test -m collection --mode=update`.
- [x] 6.8 `pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**`.

<!-- prettier-ignore-end -->
