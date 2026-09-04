# Receipt Proposal Events Specification

## Purpose

Immutable `collection.receipt.proposal.event` rows audit board mutations for the drawer
Historial tab. Create is gated; write is forbidden; unlink is forbidden except sheet
cascade.

## ADDED Requirements

### Requirement: Event model

The system MUST persist `collection.receipt.proposal.event` with: required indexed
`sheet_id` (cascade); optional `allocation_id` and `voucher_id`; required `event_type`
selection `assign`, `transfer`, `split`, `unify`, `circuit`, `impute`, `auto_impute`,
`close`, `reopen`; `name`; `description`; `value_from`; `value_to`; `user_id` defaulting
to the current user; `event_date` defaulting to now; stored required precomputed indexed
`company_id` related from the sheet. `_order` MUST be `event_date desc, id desc`.

#### Scenario: Fields and type list

- GIVEN a gated create with `event_type` `transfer`
- WHEN the row is read
- THEN MUST store sheet, type `transfer`, user, timestamp, and company of the sheet
- AND a type outside the selection MUST refuse

#### Scenario: Newest first

- GIVEN two events on the same sheet, E1 then E2
- WHEN the event list is read with default order
- THEN E2 MUST precede E1

### Requirement: Immutability

Create MUST succeed only when context key `collection_receipt_proposal_event` is set.
`write` MUST raise and leave the row unchanged. `@api.ondelete` MUST raise unless the
parent sheet cascade is unlinking.

#### Scenario: Create gated

- GIVEN context without `collection_receipt_proposal_event`
- WHEN create is attempted
- THEN MUST refuse
- AND with the context key, create MUST persist

#### Scenario: Write refused

- GIVEN an existing event
- WHEN write is attempted
- THEN MUST refuse
- AND stored fields MUST be unchanged

#### Scenario: Unlink refused except sheet cascade

- GIVEN an existing event
- WHEN unlink is attempted without sheet cascade
- THEN MUST refuse
- AND when the sheet is unlinked by cascade, the event rows MUST be removed

### Requirement: ACL and company rule

Internal users (`base.group_user`) MUST have read+create only (`1,0,1,0`). Write and
unlink ACL MUST be denied. A global `ir.rule` named
`collection_receipt_proposal_event_company_rule` MUST use
`[('company_id', 'in', company_ids)]` with no `groups`, in a `noupdate` file. Dedicated
groups MUST NOT be added. Calls MUST NOT `sudo()`.

#### Scenario: Other-company hidden

- GIVEN an event in a company the user is not allowed
- WHEN they search events
- THEN that event MUST NOT be visible

#### Scenario: Internal read and create without sudo

- GIVEN an authenticated internal user of an allowed company
- WHEN they read events or create with the context key
- THEN ACL MUST allow it without `sudo()`
- AND write/unlink ACL MUST deny
- AND a dedicated event group MUST NOT exist

### Requirement: Mutation events

Board mutations MUST append an event of the matching type: pool assign → `assign`; card
move → `transfer`; partial split → `split`; unify or undo-split → `unify`; circuit
change → `circuit`; manual impute → `impute`; FIFO recompute with non-empty changes →
`auto_impute`; customer close → `close`; reopen → `reopen`. FIFO with empty `changes`
MUST NOT write `auto_impute`.

#### Scenario: Actions write expected types

- GIVEN a proposal sheet
- WHEN transfer, set-circuit, impute, close-customer, or reopen-customer succeeds
- THEN an event of the matching type MUST exist for that sheet
- AND it MUST record user and timestamp

#### Scenario: Auto-impute only when FIFO changes

- GIVEN a recompute whose plan differs from current `amount_applied`; or one that
  matches
- WHEN recompute finishes
- THEN the differing case MUST write `auto_impute`
- AND the matching case MUST NOT
