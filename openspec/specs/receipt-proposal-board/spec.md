# Receipt Proposal Board Specification

## Purpose

Proposal-state board that distributes voucher money across customers and FAC/PRE
(`invoice` / `quotation`). RPCs re-validate, mutate existing `collection.*` rows, and
return a full payload. Only Collections Users (`collection.group_collection_user`)
reach it; company isolation is the `ir.rule`.

## ADDED Requirements

### Requirement: Proposal entry action

`action_open_receipt_proposal` MUST run only when sheet `state` is `proposal`. It MUST
copy Document Review: `ensure_one`, saved sheet, client action XMLID, `params.sheet_id`.
The inherited form MUST place `Receipt Proposal` after `action_open_document_review` and
before `action_print_xlsx` (last object button before `state`). The button MUST be
invisible unless saved and `state == 'proposal'`, and MUST carry
`groups="collection.group_collection_user"`. View/model strings MUST be English; OWL copy
MUST be Spanish. `i18n/` MUST hold the module template and `es_AR.po`, which translates
the English strings. (Previously: no `i18n/` directory.)

#### Scenario: Opens on proposal with sheet_id

- GIVEN a saved sheet in `proposal`
- WHEN `action_open_receipt_proposal` runs
- THEN the client action MUST include `params.sheet_id` equal to that sheet

#### Scenario: Non-proposal refused

- GIVEN a sheet in `open`, `closed`, or `cancelled`
- WHEN `action_open_receipt_proposal` runs
- THEN MUST refuse

#### Scenario: Header button placement and visibility

- GIVEN the inherited sheet form arch
- WHEN the header buttons are read
- THEN `Receipt Proposal` MUST sit after Document Review and before Export XLSX
- AND it MUST be invisible unless `id` is set and `state` is `proposal`
- AND Export XLSX MUST still be last before `state`

### Requirement: RPC sheet gate

Every board RPC MUST call `_require_proposal_sheet`: positive integer `sheet_id`
(boolean refused), existing sheet, `state == 'proposal'`, readable in an allowed
company. Other-company and missing sheets MUST be refused. MUST NOT `sudo()`.

#### Scenario: Invalid sheet_id refused

- GIVEN `sheet_id` that is a boolean, non-int, missing, not `proposal`, or other-company
- WHEN any board RPC runs
- THEN MUST refuse
- AND MUST NOT mutate receipts or values

### Requirement: Board RPCs

The sheet MUST expose `get_proposal_board`; mutating `action_proposal_transfer`,
`action_proposal_set_circuit`, `action_proposal_undo_split`, `action_proposal_impute`,
`action_proposal_close_customer`, `action_proposal_reopen_customer`; and previews
`preview_proposal_transfer`, `preview_proposal_circuit`, `preview_proposal_undo_split`.
Transfer MUST accept `value_id` or `voucher_id`, destination, `document_kind`, typed
`amount`, and `unify`. Mutating RPCs MUST validate, mutate, re-point owner, recompute
affected circuits, write events, and return the full board. They MUST accept only the
typed amount; the server MUST recompute the rest. Previews MUST NOT write.

Every mutating RPC (transfer, assign, split, merge, impute, reset, customer
close/reopen) MUST first lock the vouchers whose money moves and the customer columns it
redistributes, in id order (vouchers first), with a no-op
`UPDATE ... SET write_date = write_date` and an ORM cache drop, before it validates
anything; a concurrent move is then retried on fresh data and refused normally instead
of over-assigning a voucher. A `retention_certificate` MUST move only between its own
customer's circuits: transfers from the pool or a card (whole or partial), their
previews, and merges MUST refuse the pool and any other customer with a `UserError`
naming the customer, and the board reset MUST leave it in place. (Previously: each
transaction checked the split cap against its own snapshot, and a retention could be
dragged to another customer or the pool.)

The OWL client MUST parse typed amounts with the user's decimal point and thousands
separator (Odoo `localization`): a thousands separator only in groups of exactly three
digits and never after a leading zero group, a lone separator before a group that is not
three digits is the decimal point, with both separators the last one is the decimal
point, and anything ambiguous, malformed, or in exponent notation MUST be refused
(`NaN`). Seeded inputs MUST read back unchanged. (Previously: every `.` was dropped, so
`500.50` read as 50050.)

#### Scenario: Transfer, circuit, impute, close, reopen

- GIVEN a proposal sheet with pool money and two customers
- WHEN transfer, set-circuit, impute, close-customer, or reopen-customer runs with a
  typed amount where applicable
- THEN the RPC MUST return a full board whose stored rows match the mutation
- AND client-supplied applied lines other than the typed amount MUST be ignored

#### Scenario: Retention stays with its customer

- GIVEN a retention certificate assigned to customer A
- WHEN a transfer targets customer B or the unassigned pool
- THEN MUST raise `UserError` naming customer A and MUST NOT move the value

#### Scenario: Previews do not persist

- GIVEN the same inputs as a mutating transfer, circuit change, or undo-split
- WHEN the matching preview RPC runs
- THEN the response MAY describe FIFO document changes
- AND stored values and `amount_applied` MUST be unchanged

### Requirement: Board payload

`get_proposal_board` MUST return `{sheet, columns, pool, document_types, events}`. `sheet`
MUST include
`id`, `name`, `state`, `currency`, `editable`. Each column MUST be one allocation with
partner fields, `closed`, `note`, `status`, per-kind totals, cards, and documents. Pool
entries MUST be synthetic (one per voucher with `proposal_free_amount > 0`), not
records. Unassigned money MUST NOT require writing `voucher.allocation_id`.

#### Scenario: Payload shape and synthetic pool

- GIVEN a proposal sheet with one fully assigned voucher and one voucher with free
  amount 60
- WHEN `get_proposal_board` runs
- THEN `columns` MUST list each allocation and `pool` MUST contain only the free-amount
  voucher with `free_amount` 60
- AND the assigned voucher MUST NOT appear in `pool`

### Requirement: No sudo and no new groups

RPCs and OWL MUST run as `collection.group_collection_user`; a plain internal user MUST
get `AccessError`. MUST NOT add groups or call `sudo()`. Static assets MUST nest under
`.o_collection_receipt_proposal` and register
`collection_receipt_proposal.receipt_proposal`. (Previously: any internal user,
`base.group_user`.)

#### Scenario: Collections User without sudo

- GIVEN a Collections User of an allowed company
- WHEN they open the board and run a mutating RPC
- THEN ACL MUST allow it without `sudo()`
- AND a dedicated proposal group MUST NOT exist
- AND a plain internal user MUST get `AccessError` on read and on any mutating RPC

### Requirement: Close confirmation for an unfinished board

With this addon installed, the sheet form's Close button MUST opt in, through a context
key, to a check that runs after core's manager check and over-applied gate: when the
board still holds pool money or customers not closed on it, Close MUST open the
manager-only `collection.sheet.close.confirm` dialog listing the pool amount, its voucher
count, and the open customers, with **Close Anyway** (closes the sheet) and **Back to the
Sheet**. A finished board MUST close directly. It is a warning, not a guard: raw state
writes and every other caller of `action_close` MUST close exactly as in `collection`.
The dialog's pool figures MUST use the same predicate as the board's pool column.

#### Scenario: Pending pool money asks first

- GIVEN a proposal sheet whose board pool still holds 60 on one voucher
- WHEN a Collections Manager presses Close on the form
- THEN the confirmation MUST open listing 60, one voucher, and the open customers
- AND the sheet MUST stay `proposal` until Close Anyway
