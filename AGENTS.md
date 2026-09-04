# AGENTS.md — collection_receipt_proposal

Agent operating manual for the **Conciliación de Cobranzas** board. Human docs:
[README.rst](README.rst) (generated from
[readme/DESCRIPTION.md](readme/DESCRIPTION.md)). Base addon this one extends:
[collection/AGENTS.md](../collection/AGENTS.md). Parent Doodba context:
[seedian/AGENTS.md](../../../../../AGENTS.md).

Ground truth order: source under this directory → `../collection/AGENTS.md` → this file
→ parent AGENTS.md.

## Project overview

- **What:** the reconciliation step between sheet **Confirm** (`proposal`) and **Close**
  — a drag-and-drop board that distributes a `collection.sheet`'s collected money across
  customers and the two circuits, keeping the imputación consistent by FIFO.
- **Stack:** Odoo 19, PostgreSQL 17, Doodba (`seedian` compose project).
  `depends: ["collection"]`, version `19.0.1.0.0`, `application: False`.
- **Stores the validated proposal only.** It writes into the existing `collection.*`
  models and never touches Odoo accounting. A report over this data is a separate
  change.

### The mapping (settled — this drives everything)

| Board concept               | Odoo model                                           |
| --------------------------- | ---------------------------------------------------- |
| Board                       | one `collection.sheet` in state `proposal`           |
| Column (customer)           | `collection.allocation` (UNIQUE per sheet+partner)   |
| Circuito **FAC** / **PRE**  | `document_kind` = `invoice` / `quotation`            |
| Card                        | `collection.receipt.value` (voucher × amount)        |
| Per-(customer, circuit) box | `collection.receipt` (UNIQUE per allocation+kind)    |
| Documento                   | `collection.allocation.line` of that `document_kind` |
| "Imputado"                  | `collection.allocation.line.amount_applied`          |
| "Sin imputar / a favor"     | `collection.receipt.amount_on_account`               |
| "Sin asignar" pool          | voucher with `proposal_free_amount > 0` (synthetic)  |

## Repository map

| Path                                                | Role                                                                                       |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `models/collection_receipt_value.py`                | Sheet-scoped `_check_same_allocation`; sheet-wide `_check_voucher_split_cap`; card payload |
| `models/collection_receipt.py`                      | Explicit `depends` on the three receipt totals (see **Domain rules**)                      |
| `models/collection_voucher.py`                      | `proposal_value_ids` / assigned / free / is_split; `_proposal_card_label`; pool payload    |
| `models/collection_allocation.py`                   | Per-circuit figures + status; the FIFO engine; per-customer close/reopen; column payload   |
| `models/collection_receipt_proposal_event.py`       | Immutable audit trail; gated create; `_proposal_log` is the only sanctioned writer         |
| `models/collection_sheet.py`                        | `action_open_receipt_proposal` + the whole board RPC surface                               |
| `security/ir.model.access.csv`                      | One row: event `1,0,1,0` for `base.group_user`                                             |
| `security/collection_receipt_proposal_security.xml` | One global company `ir.rule` on the event model                                            |
| `views/collection_receipt_proposal_views.xml`       | `ir.actions.client` + the inherited sheet-form header button                               |
| `static/src/receipt_proposal/`                      | OWL client action, pure helpers, templates, scoped SCSS                                    |
| `tests/common.py`                                   | Receipt-shaped fixtures replicated from `collection`'s `TestCollectionReceipt`             |

## Domain rules (do not break)

- **FIFO ordering MUST mirror `collection.receipt._compute_line_ids` byte for byte:**
  `(line.due_date or date.max, line.invoice_number or "")`, undated lines last.
  `document_numbers` is stored and renders `line_ids` in that order, so a FIFO that
  distributed in a different order would name documents in an order the money did not
  follow. `tests/test_receipt_proposal_order.py` is the guard against the two drifting.
- **FIFO ceiling is `invoice_balance`**, never `invoice_amount`: each document absorbs
  up to what the ERP still says is owed, then spills to the next.
- **Every change to a (customer, circuit) pair's collected total triggers a full FIFO
  redistribution of that circuit**, discarding manual `Imputar` edits. Idempotent by
  design: the result depends only on the current `receipt.total_values`, the documents'
  `due_date` and their `invoice_balance`. A `proposal_closed` allocation is frozen —
  `_proposal_recompute` returns `None` and writes nothing.
- **Cross-customer voucher splits are allowed within one sheet.**
  `_check_same_allocation` is relaxed to the sheet boundary, and
  `_check_voucher_split_cap` is widened to sum _every_ value of the voucher (not just
  the allocation's) and compare with `currency.compare_amounts`. Relaxing the first
  without widening the second would let a voucher be over-split across customers — that
  cap test is the important one.
- **`voucher.allocation_id` names the largest assigned share**, including another
  customer on the same sheet. `_check_voucher_allocation_partner` and
  `_check_voucher_partners` still refuse a mismatch unless the voucher has a receipt
  value on that allocation and both records share a sheet. Cross-sheet pointers and
  naming another customer's allocation without a share there stay refused.
  `_proposal_sync_voucher_owner` implements the overall-largest pointer.
- **`collection.receipt` totals carry an explicit `depends`.** The base declares
  `_compute_totals` depending on `line_ids.amount_applied`, but `line_ids` is a
  computed, non-stored Many2many with no inverse: Odoo falls back to
  `search([("line_ids", "in", ids)])` and raises _Cannot convert
  collection.receipt.line_ids to SQL_ the moment an existing `amount_applied` is written
  — which this board does on every mutation. Overriding the method does not help
  (`Field.get_depends` walks the whole MRO and **extends** the list), so
  `models/collection_receipt.py` redeclares `total_values`, `total_applied` and
  `amount_on_account` with `depends=` routed through the stored
  `allocation_id.line_ids`. Do not remove it without fixing the base first.
- **Order of writes inside a mutation: shrink the source, then grow the destination.**
  Growing first would trip the sheet-wide split cap on a transient over-total.
- **Every RPC re-validates server-side on every call** via `_require_proposal_sheet`
  (int, exists, `state == 'proposal'`, accessible) plus `_proposal_allocation` /
  `_proposal_value` / `_proposal_voucher` / `_proposal_kind` / `_proposal_amount`.
  Accept only the single number the user typed; recompute everything else server-side.
  Every mutating method returns the **full refreshed board payload**.
- **Previews run in Python** (`preview_proposal_*`) so FIFO has exactly one
  implementation. Do not port `fifoPlan` to JS. The JS debounces the transfer-amount
  input ~250 ms.
- **The board is reachable only from a `proposal`-state sheet**, via the header button.
  The button sits **after** `action_open_document_review` and **before**
  `action_print_xlsx` — `collection/AGENTS.md` requires `action_print_xlsx` remain the
  last object button before `<field name="state">`.
- **The client action carries no `path`.** `ir_act_client_path_unique` is a real UNIQUE
  constraint and `collection.action_collection_document_review` already occupies the
  empty string, so this action must omit the field (NULL) rather than write `''`.
- **Events are immutable.** `create` only under context key
  `collection_receipt_proposal_event` (use
  `collection.receipt.proposal.event._proposal_log`), `write` raises, `unlink` raises
  unless the sheet cascade is unlinking (`collection_sheet_unlinking`).
- **Never `sudo()`. No new groups.** Isolation is the multi-company `ir.rule` only.
- **Copy convention:** view/model strings in English, OWL template copy in Spanish —
  same as `document_review`. No `i18n/` directory; the `collection` family has none.
- **Odoo 19 idioms:** `models.Constraint` (not `_sql_constraints`), `<list>` (not
  `<tree>`), `@api.private`, `t-out`, `*.esm.js`.

## Skills to load before work

1. Always load **`odoo-19`**:
   `/home/crisd/projects/seedian/seedian/.agents/skills/odoo-19/SKILL.md`
2. Pick the matching guide under `.agents/skills/odoo-19/references/`.

## Setup commands

Run from the **Seedian repo root** (`seedian/`), not from this module directory:

```bash
invoke install -m collection_receipt_proposal
```

## Testing instructions

On an already-installed devel DB, default `mode=init` reports **0 tests**. Use update
mode, and re-run the base suite too, since this module relaxes one of its invariants:

```bash
invoke test -m collection_receipt_proposal --mode=update
invoke test -m collection --mode=update
```

| File                                     | Focus                                                                                                                                                       |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_receipt_proposal_fifo.py`    | plan / preview / recompute; idempotency; `invoice_balance` ceiling; undated last; surplus; no documents; closed frozen; overdraft self-heals; status ladder |
| `tests/test_receipt_proposal_order.py`   | `_proposal_fifo_key` == `_compute_line_ids` order, including both fallbacks                                                                                 |
| `tests/test_receipt_proposal_split.py`   | cross-customer split accepted in-sheet, rejected across sheets; sheet-wide cap; unify; undo; owner re-pointing                                              |
| `tests/test_receipt_proposal_board.py`   | payload shape; `_require_proposal_sheet` rejections; ACL                                                                                                    |
| `tests/test_receipt_proposal_actions.py` | transfer / set_circuit / impute / close / reopen and the event each writes                                                                                  |
| `tests/test_receipt_proposal_events.py`  | gated create; write/unlink refuse except sheet cascade; newest-first; ACL `1,0,1,0`; live company `ir.rule`; no `sudo()`/groups                             |
| `tests/test_receipt_proposal_ui.py`      | static-text assertions on the JS/SCSS/XML; inherited form arch                                                                                              |

`tests/common.py` replicates `collection`'s receipt fixtures rather than subclassing
`TestCollectionReceipt` — subclassing would re-run that whole suite. It also carries
partner, user, and company helpers that tolerate `account`'s NOT NULL DB columns
outliving its fields in the registry this module's tests load into. Company create
copies leftover `res_company` columns from `env.company` (same SQL pattern as
`collection` report/binding tests). `tests/test_receipt_proposal_events.py` exercises
the live company `ir.rule` hide path with that helper.

Strict TDD is enabled in `openspec/config.yaml`. Add or update tests in the same change
as behavior.

Lint (scoped):

```bash
pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**
```

## Code style

- Two-line `# Copyright 2026 Seedian` / `# License AGPL-3.0 or later` header on every
  `.py`.
- Follow parent pre-commit: Ruff, pylint-odoo, ESLint, Prettier XML, OCA checks. ESLint
  enforces `sort-imports` and `no-use-before-define` on the OWL files.
- Do not hand-edit generated `README.rst`; update `readme/` fragments and regenerate.
- Commit prefix (OCA style): `[ADD|IMP|FIX|REF|REM|MIG] collection_receipt_proposal: …`

## Known follow-ups

1. `allocation.total_vouchers` becomes approximate once a voucher is split across
   customers: `voucher.allocation_id` can only name one owner, so one column overstates
   and the other understates. The existing XLSX/PDF report reads that field. It likely
   needs to sum `receipt.value_ids` instead — out of scope here, but settle it before
   the report.
2. `document_numbers` is stored and depends on `line_ids.amount_applied`, so every board
   mutation triggers a stored recompute of the affected receipts. Functionally
   desirable, but real write amplification on a large sheet — worth a query-count
   assertion if boards get big.
3. `_compute_document_numbers`'s `@api.depends` omits `allocation_id.line_ids.due_date`
   while the order it renders comes from `line_ids`, which _is_ due-date sorted.
   Changing a line's `due_date` therefore leaves the stored string in a stale order.
   Accepted: the board never changes `due_date`; only a connector re-snapshot does.
4. Concurrency — two operators on the same board. Every mutation returns the full board,
   which self-heals most drift; add a `write_date` staleness check on the sheet if
   needed.
5. The `collection.receipt` `depends` fix in `models/collection_receipt.py` belongs
   upstream in `collection`. While it lives here, the base suite alone never exercises
   the broken path (it never writes `amount_applied` on an existing line with a receipt
   present).
