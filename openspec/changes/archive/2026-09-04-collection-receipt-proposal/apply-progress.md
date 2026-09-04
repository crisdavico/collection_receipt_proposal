# Apply Progress: collection-receipt-proposal

**Change**: collection-receipt-proposal **Mode**: Strict TDD **Work unit**: Phase 6
Actions + regression **Updated**: 2026-09-04 **applyState**: all_done

## Completed Tasks

### Phase 1: Foundation (prior batch)

- [x] 1.1 Align `tests/common.py` mixin (copy `TestCollectionReceipt` helpers; import
      collection fixtures; never subclass).
- [x] 1.2 RED `tests/test_receipt_proposal_events.py` — gated create; write/unlink
      refuse except cascade; newest-first.
- [x] 1.3 GREEN `models/collection_receipt_proposal_event.py`.
- [x] 1.4 RED ACL `1,0,1,0`; company `ir.rule`; no `sudo()`/groups.
- [x] 1.5 GREEN `security/ir.model.access.csv` +
      `collection_receipt_proposal_security.xml`.
- [x] 1.6 Align `__manifest__.py`, `models/__init__.py` (keep `collection_receipt`
      import), `AGENTS.md`, `readme/DESCRIPTION.md`.

### Phase 2: Splits + voucher helpers (prior batch)

- [x] 2.1 RED `tests/test_receipt_proposal_split.py` — same-sheet persist; cross-sheet
      refuse; UNIQUE + amount `> 0`.
- [x] 2.2 GREEN `models/collection_receipt_value.py` `_check_same_allocation`.
- [x] 2.3 RED sheet-wide cap (`currency.compare_amounts`); over-cap refuse; at-cap
      persist.
- [x] 2.4 GREEN `_check_voucher_split_cap` (sum all values; drop allocation filter).
- [x] 2.5 RED assigned/free/split computes + `_proposal_card_label`.
- [x] 2.6 GREEN `models/collection_voucher.py`.

### Phase 3: FIFO + receipt depends (prior batch)

- [x] 3.1 RED `tests/test_receipt_proposal_fifo.py` — `invoice_balance` ceiling;
      partial/surplus/no-docs; idempotent overwrite; closed frozen; overdraft self-heal.
- [x] 3.2 GREEN `models/collection_allocation.py` fifo_key/plan/preview/recompute;
      `proposal_closed`; `cerrado` (not `allocation.state`).
- [x] 3.3 RED `tests/test_receipt_proposal_order.py` — key matches `_compute_line_ids`;
      undated last; empty `""`.
- [x] 3.4 GREEN keep `models/collection_receipt.py` totals `depends=` (FIFO writes
      SQL-safe).

### Phase 4: Sheet RPC + board payload (prior batch)

- [x] 4.1 RED `tests/test_receipt_proposal_board.py` — `{sheet,columns,pool,events}`;
      synthetic pool; `_require_proposal_sheet` refuses bad ids/state/company; open
      action `params.sheet_id`.
- [x] 4.2 GREEN `models/collection_sheet.py` open, `_require_proposal_sheet`,
      `get_proposal_board`.
- [x] 4.3 RED previews do not persist (transfer, circuit, undo-split, **impute**).
- [x] 4.4 GREEN keep `preview_proposal_transfer|circuit|undo_split|impute`.

### Phase 5: OWL + views (prior batch)

- [x] 5.1 RED `tests/test_receipt_proposal_ui.py` — helpers pure (regex-assert, `_t`
      only); **omit `path`**; button after Document Review, XLSX last; Spanish OWL /
      English views.
- [x] 5.2 GREEN `receipt_proposal_helpers.esm.js` (`formatAmount`, `splitKind`,
      `cardClass`, `statusLabel`, `validateTransferAmount`, `transferButtonLabel`,
      `sanitizeBoardPayload`, `nextIsolate`, `CIRCUITS`).
- [x] 5.3 GREEN `receipt_proposal_action.esm.js` + `.xml` + `.scss` (document_review;
      DnD; 250 ms debounce).
- [x] 5.4 GREEN `views/collection_receipt_proposal_views.xml` — omit `path`.

### Phase 6: Actions + regression (this batch)

- [x] 6.1 RED `tests/test_receipt_proposal_actions.py` —
      transfer/set_circuit/impute/close/reopen return full board; typed amount only;
      close note on difference.
- [x] 6.2 GREEN mutating RPCs: shrink-then-grow → **same-customer** owner (not overall;
      `_check_voucher_partners`) → FIFO → events → board.
- [x] 6.3 RED unify, undo-split, same-customer owner.
- [x] 6.4 GREEN those paths.
- [x] 6.5 RED mutation event types (auto_impute only if FIFO `changes`).
- [x] 6.6 GREEN `_proposal_log` + close/reopen.
- [x] 6.7 Run addon `--mode=update`, then `invoke test -m collection --mode=update`.
- [x] 6.8
      `pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**`.

## Files Changed

### Phase 1 (prior batch)

| File                                                | Action   | What Was Done                                                                                                                                                                                  |
| --------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/common.py`                                   | Modified | Copied remaining `TestCollectionReceipt` helpers (`_create_company`, `_restrict_user_to_company`, `_assert_acl` / rule / hide). SQL company insert copies leftover `account` NOT NULL columns. |
| `tests/test_receipt_proposal_events.py`             | Modified | Spec-complete RED/GREEN: gated create, transfer fields, invalid type, write unchanged, cascade unlink, newest-first search, ACL `1,0,1,0`, live `ir.rule`, no groups/`sudo()`.                 |
| `models/collection_receipt_proposal_event.py`       | Aligned  | Already implemented; tests confirmed gated create, write raise, `@api.ondelete` cascade via `collection_sheet_unlinking`.                                                                      |
| `security/ir.model.access.csv`                      | Aligned  | Event `base.group_user` `1,0,1,0`.                                                                                                                                                             |
| `security/collection_receipt_proposal_security.xml` | Aligned  | Global noupdate company `ir.rule`.                                                                                                                                                             |
| `__manifest__.py`                                   | Aligned  | `depends: ["collection"]`, `19.0.1.0.0`, `web.assets_backend` `receipt_proposal/**`.                                                                                                           |
| `models/__init__.py`                                | Aligned  | Kept `collection_receipt` import.                                                                                                                                                              |
| `AGENTS.md`                                         | Modified | Event test coverage + live company-rule helper note.                                                                                                                                           |
| `readme/DESCRIPTION.md`                             | Aligned  | Immutable event sentence already present.                                                                                                                                                      |

### Phase 2 (prior batch)

| File                                   | Action   | What Was Done                                                                                                                                                                                                                                                             |
| -------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_receipt_proposal_split.py` | Modified | Added UNIQUE + amount `> 0`; cross-sheet unchanged rows; at-cap persist; three-customer over-cap; assigned/free/split triangulation; `_proposal_card_label` transfer/check/name fallback. Left Phase 6 transfer/unify/undo/owner/pool cases in the class (already green). |
| `models/collection_receipt_value.py`   | Aligned  | `_check_same_allocation` is sheet-scope (`voucher.sheet_id == receipt.sheet_id`). `_check_voucher_split_cap` sums all values (no allocation filter) and uses `currency.compare_amounts`.                                                                                  |
| `models/collection_voucher.py`         | Aligned  | `proposal_assigned_amount` / `proposal_free_amount` / `proposal_is_split` and `@api.private _proposal_card_label()` already matched the spec.                                                                                                                             |

### Phase 3 (prior batch)

| File                                   | Action         | What Was Done                                                                                                                                                                                                                                                                                                         |
| -------------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_receipt_proposal_fifo.py`  | Modified       | Spec triangulation: ceiling 80/50/60→50+50; partial 30; surplus 80 vs 50; no-docs applied 0; closed freeze with disagreeing amounts; `cerrado` vs `state==draft`; SQL-safe totals after FIFO write. Existing idempotent/manual/overdraft/preview cases kept.                                                          |
| `tests/test_receipt_proposal_order.py` | Modified       | Same-due-date `False` number → key `(due, "")` and FIFO ids == `receipt.line_ids` (`""` before `"A"`, matching `_compute_line_ids`).                                                                                                                                                                                  |
| `models/collection_allocation.py`      | Aligned        | `_proposal_fifo_key` / `_proposal_fifo_plan` / `_proposal_preview` / `_proposal_recompute` already `@api.private`; ceiling `invoice_balance`; `proposal_closed` freeze returns `None`; `proposal_status` includes `cerrado` and does not write `allocation.state`. Close/reopen actions left on disk for Phase 6 RPC. |
| `models/collection_receipt.py`         | Aligned (keep) | Totals still declare explicit `depends=` so FIFO `amount_applied` writes stay SQL-safe. No production edit.                                                                                                                                                                                                           |

### Phase 4 (prior batch)

| File                                   | Action         | What Was Done                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| -------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_receipt_proposal_board.py` | Modified       | Spec triangulation: nested sheet/column/card/document/pool/event keys; synthetic pool (full assign + free 60, no `value_id`); `_require_proposal_sheet` open/proposal/closed/cancelled + missing + non-int + no-mutate; live other-company refuse via `_create_company`; open action `params.sheet_id` on proposal only; previews transfer/circuit/undo-split/impute do not persist (impute also asserts FIFO change tuples then empty after recompute). |
| `models/collection_sheet.py`           | Aligned (keep) | `action_open_receipt_proposal`, `_require_proposal_sheet`, `get_proposal_board`, and `preview_proposal_transfer\|circuit\|undo_split\|impute` already matched design. No production edit. Mutating RPCs left on disk for Phase 6.                                                                                                                                                                                                                        |

### Phase 5 (prior batch)

| File                                                          | Action         | What Was Done                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_receipt_proposal_ui.py`                           | Modified       | RED/triangulation: helper regex (`_t` only, CIRCUITS FAC/PRE, `formatAmount` es-AR, `splitKind`/`nextIsolate`/`validateTransferAmount`/`transferButtonLabel`); 250 ms debounce; Spanish OWL / English views / no `i18n/`; `t-out` not `t-esc`; `preview_proposal_impute`; English `string="Receipt Proposal"`. Kept collision list including `row`. |
| `static/src/receipt_proposal/receipt_proposal_helpers.esm.js` | Aligned (keep) | Pure helpers already exported; only `_t` import; `PREVIEW_DEBOUNCE_MS = 250`; `CIRCUITS` invoice/quotation. No production rewrite.                                                                                                                                                                                                                  |
| `static/src/receipt_proposal/receipt_proposal_action.esm.js`  | Aligned (keep) | document_review client action: `standardActionServiceProps`, ORM + notification, HTML5 DnD, 250 ms preview debounce. No production rewrite.                                                                                                                                                                                                         |
| `static/src/receipt_proposal/receipt_proposal_action.xml`     | Modified       | Renamed drawer `class="row"` → `drawer-title-row` (Bootstrap collision). Replaced `t-esc=` with `t-out=` (Odoo 19 / document_review). Spanish copy kept.                                                                                                                                                                                            |
| `static/src/receipt_proposal/receipt_proposal_action.scss`    | Modified       | Nested `.drawer-head .row` → `.drawer-title-row` under `.o_collection_receipt_proposal`. Clay/neumorphic + FAC/PRE tokens unchanged.                                                                                                                                                                                                                |
| `views/collection_receipt_proposal_views.xml`                 | Aligned (keep) | Client action omits `path`; English `Receipt Proposal` after Document Review, before XLSX; `invisible="not id or state != 'proposal'"`.                                                                                                                                                                                                             |

### Phase 6 (this batch)

| File                                     | Action   | What Was Done                                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_receipt_proposal_actions.py` | Modified | Full-board returns for transfer/circuit/impute/close/reopen; typed amount only (ignore `lines`/`changes`); close note on surplus and whitespace; unify/undo-split board returns; same-customer owner vs overall largest; owner clears when no same-customer share; event types including unify; `auto_impute` skipped when FIFO `changes` is empty. |
| `models/collection_sheet.py`             | Modified | `action_proposal_transfer` accepts and ignores client FIFO `lines`/`changes`. `_proposal_sync_voucher_owner` clears `allocation_id` when no same-customer share remains. Shrink-then-grow, FIFO, events, and board return were already on disk.                                                                                                     |

## TDD Cycle Evidence

### Phase 1 (prior batch)

| Task | Test File                                                                     | Layer       | Safety Net           | RED                                   | GREEN              | TRIANGULATE                                                 | REFACTOR                                    |
| ---- | ----------------------------------------------------------------------------- | ----------- | -------------------- | ------------------------------------- | ------------------ | ----------------------------------------------------------- | ------------------------------------------- |
| 1.1  | `tests/common.py` (exercised by events)                                       | Integration | N/A (align mixin)    | ✅ Helpers added before new ACL cases | ✅ Used by 1.2/1.4 | ➖ Structural copy                                          | ✅ SQL leftover-column company create       |
| 1.2  | `tests/test_receipt_proposal_events.py`                                       | Integration | N/A (new behaviors)  | ✅ Written first                      | ✅ 11/11 focused   | ✅ gated + transfer + invalid type + newest-first + cascade | ➖ Model already clean                      |
| 1.3  | same                                                                          | Integration | Existing event model | ✅ Tests named missing behaviors      | ✅ Passed          | covered by 1.2                                              | ➖ None needed                              |
| 1.4  | same                                                                          | Integration | Existing ACL rows    | ✅ Written first                      | ✅ Passed          | ✅ ACL flags + internal create/read + live hide + no groups | ➖ `_restrict_user_to_company` 3-step write |
| 1.5  | `security/*`                                                                  | Integration | Existing files       | ✅ Tests first                        | ✅ Passed          | ➖ Structural ACL/XML                                       | ➖ None needed                              |
| 1.6  | `__manifest__.py`, `models/__init__.py`, `AGENTS.md`, `readme/DESCRIPTION.md` | Structural  | Existing aligned     | ➖ Structural                         | ✅ Aligned         | ➖ Single output                                            | ➖ None needed                              |

### Phase 2 (prior batch)

| Task | Test File                              | Layer       | Safety Net                              | RED                                                                                              | GREEN                          | TRIANGULATE                                                                                 | REFACTOR                              |
| ---- | -------------------------------------- | ----------- | --------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------- | ------------------------------------- |
| 2.1  | `tests/test_receipt_proposal_split.py` | Integration | Existing split tests already green      | ✅ Written first (same-sheet persist, cross-sheet refuse + unchanged rows, UNIQUE, amount `> 0`) | ✅ Passed (18/18 class)        | ✅ same-sheet + cross-sheet + UNIQUE + 0 + negative                                         | ➖ Constraint inherit already clean   |
| 2.2  | `models/collection_receipt_value.py`   | Integration | Existing `_check_same_allocation`       | ✅ Tests named sheet-scope vs allocation-scope                                                   | ✅ Aligned; no production edit | covered by 2.1                                                                              | ➖ None needed                        |
| 2.3  | `tests/test_receipt_proposal_split.py` | Integration | Existing over-cap + write-cap           | ✅ Written first (over-cap two customers, over-cap three customers, at-cap 120+180)              | ✅ Passed                      | ✅ 200+150 refuse; 40+50+20 refuse; 120+180 persist; write 250 refuse                       | ➖ Cap already uses `compare_amounts` |
| 2.4  | `models/collection_receipt_value.py`   | Integration | Existing `_check_voucher_split_cap`     | ✅ Three-customer case would pass under allocation-filtered base                                 | ✅ Aligned; no production edit | covered by 2.3                                                                              | ➖ None needed                        |
| 2.5  | `tests/test_receipt_proposal_split.py` | Integration | First test already asserted full assign | ✅ Written first (unassigned/partial/split + transfer/check/name labels)                         | ✅ Passed                      | ✅ 0/300/false; 120/180/false; 200/100/true; TR-99; ACC-1; check bank+number; name fallback | ➖ Computes already clean             |
| 2.6  | `models/collection_voucher.py`         | Integration | Existing voucher helpers                | ✅ Tests named missing label/partial paths                                                       | ✅ Aligned; no production edit | covered by 2.5                                                                              | ➖ None needed                        |

### Phase 3 (prior batch)

| Task | Test File                              | Layer       | Safety Net                               | RED                                                                                                                                                       | GREEN                          | TRIANGULATE                                                                                                                                                    | REFACTOR                            |
| ---- | -------------------------------------- | ----------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| 3.1  | `tests/test_receipt_proposal_fifo.py`  | Integration | ✅ 20/20 fifo+order before edits         | ✅ Written first (spec ceiling 50+50; partial 30; surplus 80/50; no-docs applied 0; closed freeze on disagreeing amounts; cerrado≠state; SQL-safe totals) | ✅ 26/26 focused               | ✅ amount vs balance; two-doc partial + single-doc 30; surplus 300/200 + 80/50; preview+recompute no-docs; idempotent+manual overwrite; overdraft; closed None | ➖ Engine already clean             |
| 3.2  | `models/collection_allocation.py`      | Integration | Existing fifo_key/plan/preview/recompute | ✅ Tests named missing spec numbers + cerrado vs draft                                                                                                    | ✅ Aligned; no production edit | covered by 3.1                                                                                                                                                 | ➖ None needed                      |
| 3.3  | `tests/test_receipt_proposal_order.py` | Integration | Existing order class already green       | ✅ Written first (same-due-date empty `""` vs `"A"` matches `_compute_line_ids`)                                                                          | ✅ Passed                      | ✅ mixed-line id match; undated last; A-0001 before B-0002; key `(due, "")`; `""` before `"A"`                                                                 | ➖ Key already matches receipt sort |
| 3.4  | `models/collection_receipt.py`         | Integration | Existing `depends=`                      | ✅ SQL-safe totals test written first                                                                                                                     | ✅ Aligned; no production edit | covered by surplus `amount_on_account` + explicit totals after recompute                                                                                       | ➖ Keep `depends=` as-is            |

### Phase 4 (prior batch)

| Task | Test File                              | Layer       | Safety Net                                                   | RED                                                                                                                                        | GREEN                                  | TRIANGULATE                                                                                                                      | REFACTOR                          |
| ---- | -------------------------------------- | ----------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| 4.1  | `tests/test_receipt_proposal_board.py` | Integration | ✅ 11/11 board class before edits                            | ✅ Written first (nested keys; synthetic pool free 60; closed/cancelled; live other-company; open `params.sheet_id`; no-mutate on bad ids) | ✅ 19/19 focused                       | ✅ two-pool vs one-pool; open/proposal/closed/cancelled; missing vs non-int vs company hide; portal AccessError vs internal read | ➖ Payload builders already clean |
| 4.2  | `models/collection_sheet.py`           | Integration | Existing open/`_require_proposal_sheet`/`get_proposal_board` | ✅ Tests named missing spec paths                                                                                                          | ✅ Aligned; no production edit         | covered by 4.1                                                                                                                   | ➖ None needed                    |
| 4.3  | `tests/test_receipt_proposal_board.py` | Integration | Same 11/11 safety net                                        | ✅ Written first (transfer, circuit, undo-split, impute; impute change tuples 0→100 then empty after recompute)                            | ✅ Passed                              | ✅ four preview RPCs; impute with changes then without; stored values/`amount_applied`/events unchanged                          | ➖ Preview surface already clean  |
| 4.4  | `models/collection_sheet.py`           | Integration | Existing `preview_proposal_*`                                | ✅ Tests named missing undo-split + impute persist paths                                                                                   | ✅ Aligned; kept all four preview RPCs | covered by 4.3                                                                                                                   | ➖ None needed                    |

### Phase 5 (prior batch)

| Task | Test File                                     | Layer                                             | Safety Net                                                   | RED                                                                                                                                                                                     | GREEN                                         | TRIANGULATE                                                                                                                                              | REFACTOR                                   |
| ---- | --------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| 5.1  | `tests/test_receipt_proposal_ui.py`           | Unit (static-text `TransactionCase`; no HttpCase) | ✅ 1 failed / 25 (`{'row'}` collision) before new assertions | ✅ Written first (helper regex/`_t` only; Spanish OWL / English views / no i18n; `t-out`; 250 ms debounce; `preview_proposal_impute`; English button string). Collision list kept `row` | ✅ 0 failed / 30 after GREEN                  | ✅ Spanish phrases + English view/action name; helper CIRCUITS/formatAmount/splitKind/nextIsolate/validate/transfer labels; debounce 250; t-out vs t-esc | ➖ Tests only                              |
| 5.2  | `receipt_proposal_helpers.esm.js`             | Unit (regex)                                      | Helpers already on disk                                      | ✅ Tests named missing helper bodies + `_t` only                                                                                                                                        | ✅ Aligned; no production rewrite             | covered by 5.1 helper regex                                                                                                                              | ➖ Helpers already pure                    |
| 5.3  | `receipt_proposal_action.{esm.js,xml,scss}`   | Unit (static-text)                                | Same 1/25 `row` fail                                         | ✅ Collision + `t-esc` tests written first (RED 2 failed / 30)                                                                                                                          | ✅ Passed after `drawer-title-row` + `t-out=` | ✅ DnD handlers, 250 ms debounce, portals, clay/FAC/PRE tokens, no Bootstrap `row`                                                                       | ✅ Renamed scoped class; `t-esc` → `t-out` |
| 5.4  | `views/collection_receipt_proposal_views.xml` | Integration                                       | Existing inherit + client action                             | ✅ Tests named omit `path`, English string, after Document Review, XLSX last                                                                                                            | ✅ Aligned; no production rewrite             | ✅ inherit `position="after"`; combined arch XLSX last; `action.path` falsy                                                                              | ➖ Views already matched                   |

### Phase 6 (this batch)

| Task | Test File                                | Layer       | Safety Net                           | RED                                                                                                                       | GREEN                                                                              | TRIANGULATE                                                                                                    | REFACTOR                                   |
| ---- | ---------------------------------------- | ----------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| 6.1  | `tests/test_receipt_proposal_actions.py` | Integration | ✅ 0 failed / 18 before new tests    | ✅ Written first (full board for 5 RPCs; typed `lines`/`changes` ignored; close note on surplus + whitespace)             | ✅ RED 1 error / 21 (`lines=` TypeError); GREEN 0 failed / 21 after ignored kwargs | ✅ transfer+circuit+impute+close+reopen boards; FIFO 100+50 despite client 1.0; pending vs surplus close notes | ➖ Tests + unused kwargs                   |
| 6.2  | `models/collection_sheet.py`             | Integration | Existing mutating RPCs on disk       | ✅ Typed-amount test named missing ignore-kwargs                                                                          | ✅ Passed after `del lines, changes`                                               | covered by 6.1 FIFO vs client rows; shrink-then-grow already proven by split/transfer tests                    | ➖ Ignore-kwargs only                      |
| 6.3  | `tests/test_receipt_proposal_actions.py` | Integration | ✅ 0 failed / 21                     | ✅ Written first (unify merge; undo-split keep; same-customer owner; owner clears when none)                              | ✅ RED 1 failed + 1 error / 25 (stale owner; UserError vs ValidationError)         | ✅ unify 120+80→200; undo keep 200; A=100/B=200 owner A; all-to-B owner False                                  | ➖ Test assertion to UserError             |
| 6.4  | `models/collection_sheet.py`             | Integration | Existing sync helper                 | ✅ Owner-clear test named missing `allocation_id = False`                                                                 | ✅ Passed after clear-when-no-candidates                                           | covered by 6.3                                                                                                 | ✅ Clear owner when no same-customer share |
| 6.5  | `tests/test_receipt_proposal_actions.py` | Integration | ✅ 0 failed / 25                     | ✅ Written first (assign/split/transfer/circuit/impute/close/reopen types; unify; empty FIFO `changes` skips auto_impute) | ✅ 0 failed / 28 (aligned; `_proposal_log` already skipped empty changes)          | ✅ auto_impute present then unchanged on second recompute; ≥2 unify events                                     | ➖ Tests only                              |
| 6.6  | `_proposal_log` + close/reopen           | Integration | Existing event writer                | ✅ Close/reopen user+timestamp asserted in 6.5                                                                            | ✅ Aligned; no production rewrite                                                  | covered by 6.5                                                                                                 | ➖ Logger already gated                    |
| 6.7  | addon + collection `--mode=update`       | Integration | N/A (harness)                        | ➖ Runtime                                                                                                                | ✅ addon 0/132; collection 0/749                                                   | ➖ Suites                                                                                                      | ➖ None                                    |
| 6.8  | pre-commit                               | Lint        | First pass failed E501 + except-pass | ✅ Docstrings shortened; cross-customer owner uses `assertRaises(UserError)`                                              | ✅ `pre-commit` exit 0                                                             | ➖ Lint                                                                                                        | ✅ Line length + except-pass               |

### Test Summary

- **Total tests written (Phase 6)**: 10 new methods on `TestReceiptProposalActions`
  (full-board RPCs, typed amount, surplus close note, unify, undo-split, same-customer
  owner, owner-clear, event types, auto_impute skip, unify events)
- **Total tests passing (focused class)**: 28 / 28
  (`0 failed, 0 error(s) of 28 tests when loading database 'devel'`; runner stats also
  logged `collection_receipt_proposal: 30 tests 2.13s 3363 queries`)
- **Layers used**: Integration (Odoo `TransactionCase`) (28 focused), Unit (0), E2E (0)
- **Approval tests** (refactoring): None — owner-clear is a new behavior, not a
  preserve-as-is extract
- **Pure functions created**: 0

Phase 5 summary (prior): 30/30 UI class; helpers already pure.

## Work Unit Evidence

### Phase 1 (prior batch)

| Evidence                                          | Required value                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Focused test command and exact result             | `docker compose run --rm -e DB_FILTER='^devel$' odoo odoo --test-enable --stop-after-init --workers=0 -u collection_receipt_proposal --test-tags /collection_receipt_proposal:TestReceiptProposalEvents` → `0 failed, 0 error(s) of 11 tests when loading database 'devel'`                                              |
| Runtime harness command/scenario and exact result | `invoke test -m collection_receipt_proposal --mode=update` → `1 failed, 0 error(s) of 97 tests`. Failure is `TestReceiptProposalUi.test_no_bootstrap_class_name_collisions` (`{'row'}` class-name collision) — Phase 5 OWL, outside that work unit. All 11 Phase 1 event/ACL tests in that run started and did not fail. |
| Rollback boundary                                 | Event model + event ACL/`ir.rule` + `tests/common.py` helpers + `tests/test_receipt_proposal_events.py` + AGENTS.md testing notes. Do not revert OWL/static or other-phase model inherits.                                                                                                                               |

### Phase 2 (prior batch)

| Evidence                                          | Required value                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result             | `docker compose run --rm -e DB_FILTER='^devel$' odoo odoo --test-enable --stop-after-init --workers=0 -u collection_receipt_proposal --test-tags /collection_receipt_proposal:TestReceiptProposalSplit` → `0 failed, 0 error(s) of 18 tests when loading database 'devel'` (stats: `collection_receipt_proposal: 20 tests 1.04s 1600 queries`) |
| Runtime harness command/scenario and exact result | Same Doodba `TransactionCase` path as invoke `--mode=update`; focused class tag used because `invoke test` cannot pass a class tag. Full-module OWL `row` failure remains Phase 5 and was not re-run.                                                                                                                                          |
| Rollback boundary                                 | `tests/test_receipt_proposal_split.py` Phase 2 assertions; `models/collection_receipt_value.py` sheet-scope + sheet-wide cap; `models/collection_voucher.py` assigned/free/split + `_proposal_card_label`. Do not revert Phase 1 event/ACL, Phase 6 owner/unify/transfer RPCs, or OWL/static.                                                  |

### Phase 3 (prior batch)

| Evidence                                          | Required value                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result             | `docker compose run --rm -e DB_FILTER='^devel$' odoo odoo --test-enable --stop-after-init --workers=0 -u collection_receipt_proposal --test-tags /collection_receipt_proposal:TestReceiptProposalFifo,/collection_receipt_proposal:TestReceiptProposalOrder` → `0 failed, 0 error(s) of 26 tests when loading database 'devel'` (stats: `collection_receipt_proposal: 30 tests 1.49s 1866 queries`). Safety net before edits: `0 failed, 0 error(s) of 20 tests`. |
| Runtime harness command/scenario and exact result | Same Doodba `TransactionCase` path as invoke `--mode=update`; focused class tags because `invoke test` cannot pass a class tag. SQL-safe path: `_proposal_recompute` writes `amount_applied` then reads `total_values` / `total_applied` / `amount_on_account` without `Cannot convert collection.receipt.line_ids to SQL`. Full-module OWL `row` failure remains Phase 5 and was not re-run.                                                                     |
| Rollback boundary                                 | `tests/test_receipt_proposal_fifo.py` and `tests/test_receipt_proposal_order.py` Phase 3 assertions. Production FIFO/receipt files were aligned in place (no rewrite). Do not revert Phase 1 event/ACL, Phase 2 splits/voucher helpers, Phase 6 close-note RPC, or OWL/static.                                                                                                                                                                                    |

### Phase 4 (prior batch)

| Evidence                                          | Required value                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result             | `docker compose run --rm -e DB_FILTER='^devel$' odoo odoo --test-enable --stop-after-init --workers=0 -u collection_receipt_proposal --test-tags /collection_receipt_proposal:TestReceiptProposalBoard` → `0 failed, 0 error(s) of 19 tests when loading database 'devel'` (stats: `collection_receipt_proposal: 21 tests 1.40s 2174 queries`). Safety net before edits: `0 failed, 0 error(s) of 11 tests`.  |
| Runtime harness command/scenario and exact result | Same Doodba `TransactionCase` path as invoke `--mode=update`; focused class tag because `invoke test` cannot pass a class tag. Live other-company board RPC refused without mutating home-sheet values. Previews returned FIFO `changes` while stored `collection.receipt.value` amounts, `amount_applied`, and event ids stayed unchanged. Full-module OWL `row` failure remains Phase 5 and was not re-run. |
| Rollback boundary                                 | `tests/test_receipt_proposal_board.py` Phase 4 assertions. Production `models/collection_sheet.py` was aligned in place (no rewrite). Do not revert Phase 1–3, Phase 6 mutating RPCs, or OWL/static.                                                                                                                                                                                                          |

### Phase 5 (prior batch)

| Evidence                                          | Required value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result             | `docker compose run --rm -e DB_FILTER='^devel$' odoo odoo --test-enable --stop-after-init --workers=0 -u collection_receipt_proposal --test-tags /collection_receipt_proposal:TestReceiptProposalUi` → `0 failed, 0 error(s) of 30 tests when loading database 'devel'` (stats: `collection_receipt_proposal: 32 tests 0.10s 106 queries`). Safety net: `1 failed, 0 error(s) of 25 tests` (`{'row'}`). After RED tests, before GREEN: `2 failed, 0 error(s) of 30 tests` (`row` + `t-esc=`). |
| Runtime harness command/scenario and exact result | N/A — design/tasks: static-text UI tests; no HttpCase/tours. Same Doodba `TransactionCase` path as invoke `--mode=update`; focused class tag because `invoke test` cannot pass a class tag. Collision test now passes: XML class tokens ∩ Bootstrap owned set is empty after `drawer-title-row`.                                                                                                                                                                                              |
| Rollback boundary                                 | `tests/test_receipt_proposal_ui.py`; `static/src/receipt_proposal/receipt_proposal_action.xml` (`drawer-title-row`, `t-out`); `static/src/receipt_proposal/receipt_proposal_action.scss` (`.drawer-title-row`). Do not revert Python models, Phase 1–4, or Phase 6 mutating RPCs. Helpers and views were aligned in place.                                                                                                                                                                    |

### Phase 6 (this batch)

| Evidence                                          | Required value                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result             | `docker compose run --rm -e DB_FILTER='^devel$' odoo odoo --test-enable --stop-after-init --workers=0 -u collection_receipt_proposal --test-tags /collection_receipt_proposal:TestReceiptProposalActions` → `0 failed, 0 error(s) of 28 tests when loading database 'devel'` (stats: `collection_receipt_proposal: 30 tests 2.13s 3363 queries`). Safety net: `0 failed, 0 error(s) of 18 tests`. |
| Runtime harness command/scenario and exact result | `invoke test -m collection_receipt_proposal --mode=update` → `0 failed, 0 error(s) of 132 tests` (stats: `146 tests 6.81s 10297 queries`). `invoke test -m collection --mode=update` → `0 failed, 0 error(s) of 749 tests` (stats: `817 tests 38.33s 63697 queries`). Both `--mode=update` on db `devel`.                                                                                         |
| Rollback boundary                                 | `tests/test_receipt_proposal_actions.py`; `models/collection_sheet.py` (`action_proposal_transfer` ignored `lines`/`changes`; `_proposal_sync_voucher_owner` clear-when-none). Do not revert Phase 1–5 OWL/FIFO/splits/events. Uninstalling this addon remains the product rollback.                                                                                                              |

## Deviations from Design

None — implementation matches design. Client action tag
`collection_receipt_proposal.receipt_proposal` omits `path`. Header button sits after
Document Review and before Export XLSX. OWL copy is Spanish; view/action strings are
English; no `i18n/`. Helpers are pure (`_t` only). SCSS nests under
`.o_collection_receipt_proposal`. Drawer head uses `drawer-title-row` instead of
Bootstrap `row`. OWL templates use `t-out`.

Odoo’s patched `assertRaises` cannot take an exception tuple (`issubclass()` TypeError).
Other-company board RPC refuse uses `try`/`except (UserError, AccessError)`. (Phase 4)

## Issues Found

1. Live `res.company` ORM create fails in this addon's test registry because leftover
   `account` NOT NULL columns (`fiscalyear_last_day`, etc.) have no matching fields.
   Mixin now SQL-copies those columns from `env.company` (collection report/binding
   pattern). (Phase 1)
2. Internal-user `write` raises `UserError` (immutability) before ACL `AccessError`.
   Spec still holds: write is refused; ACL flags deny write/unlink; unlink as internal
   user raises `AccessError`. (Phase 1)
3. Full-module `invoke test` previously failed
   `TestReceiptProposalUi.test_no_bootstrap_class_name_collisions` on class `row`. Fixed
   in Phase 5 by renaming to `drawer-title-row` (test not weakened).
4. `_proposal_card_label` fixtures must be created on an **open** sheet: writing
   `voucher_number` / `from_account` on a `proposal`-state voucher raises the base
   freeze `UserError`.
5. Odoo result line reported 18 tests while `tests.stats` logged 20 for the module tag
   in Phase 2; Phase 3 result line reported 26 tests while `tests.stats` logged 30;
   Phase 4 result line reported 19 tests while `tests.stats` logged 21; Phase 5 result
   line reported 30 tests while `tests.stats` logged 32. All started methods in the
   focused classes passed.
6. FIFO/`cerrado` engine and receipt `depends=` were already on disk; Phase 3 aligned
   via tests rather than rewriting production.
7. Sheet open/`_require_proposal_sheet`/`get_proposal_board`/preview RPCs were already
   on disk; Phase 4 aligned via tests rather than rewriting production. Mutating
   `action_proposal_*` were completed in Phase 6.
8. OWL action/helpers/views were already on disk from another agent; Phase 5 aligned via
   tests, renamed the Bootstrap `row` class, and replaced `t-esc` with `t-out`.
9. Cross-customer owner write raises voucher `UserError`
   (`_check_voucher_allocation_partner`) before allocation `_check_voucher_partners`
   `ValidationError`. Tests assert `UserError`. (Phase 6)
10. `_proposal_sync_voucher_owner` previously left a stale same-customer owner after
    transferring all shares to another customer. It now clears `allocation_id`.
    (Phase 6)
11. Odoo result line reported 28 focused tests while `tests.stats` logged 30; addon
    suite 132 vs stats 146; collection suite 749 vs stats 817. All started methods
    passed.

## Remaining Tasks

None — all 32 tasks `[x]`. **applyState**: all_done.

## Workload / PR Boundary

- Mode: stacked PR slice (`stacked-to-main`)
- Current work unit: Phase 6 Actions + regression
- Boundary: `tests/test_receipt_proposal_actions.py` and `models/collection_sheet.py`
  (ignored transfer kwargs + same-customer owner clear). Starts from Phase 5 OWL on
  disk; ends when focused actions + addon + collection suites are 0 failed and
  pre-commit passes. Does not revert Phase 1–5.
- Estimated review budget impact: small production diff (ignore `lines`/`changes`; clear
  owner when no same-customer share) plus action-test additions; under 400 authored
  lines for this slice.
