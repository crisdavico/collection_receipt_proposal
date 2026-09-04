# Receipt Proposal Board Specification

## Purpose

Proposal-state board that distributes voucher money across customers and FAC/PRE
(`invoice` / `quotation`). RPCs re-validate, mutate existing `collection.*` rows, and
return a full payload. Isolation is company `ir.rule` only.

## ADDED Requirements

### Requirement: Proposal entry action

`action_open_receipt_proposal` MUST run only when sheet `state` is `proposal`. It MUST
copy Document Review: `ensure_one`, saved sheet, client action XMLID, `params.sheet_id`.
The inherited form MUST place `Receipt Proposal` after `action_open_document_review` and
before `action_print_xlsx` (last object button before `state`). The button MUST be
invisible unless saved and `state == 'proposal'`. View/model strings MUST be English;
OWL copy MUST be Spanish. MUST NOT add `i18n/`.

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

#### Scenario: Transfer, circuit, impute, close, reopen

- GIVEN a proposal sheet with pool money and two customers
- WHEN transfer, set-circuit, impute, close-customer, or reopen-customer runs with a
  typed amount where applicable
- THEN the RPC MUST return a full board whose stored rows match the mutation
- AND client-supplied applied lines other than the typed amount MUST be ignored

#### Scenario: Previews do not persist

- GIVEN the same inputs as a mutating transfer, circuit change, or undo-split
- WHEN the matching preview RPC runs
- THEN the response MAY describe FIFO document changes
- AND stored values and `amount_applied` MUST be unchanged

### Requirement: Board payload

`get_proposal_board` MUST return `{sheet, columns, pool, events}`. `sheet` MUST include
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

RPCs and OWL MUST run as `base.group_user`. MUST NOT add groups or call `sudo()`. Static
assets MUST nest under `.o_collection_receipt_proposal` and register
`collection_receipt_proposal.receipt_proposal`.

#### Scenario: Internal user without sudo

- GIVEN an authenticated internal user of an allowed company
- WHEN they open the board and run a mutating RPC
- THEN ACL MUST allow it without `sudo()`
- AND a dedicated proposal group MUST NOT exist
