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
`reset`, `close`, `reopen`; `name`; `description`; `value_from`; `value_to`; `user_id`
and `event_date` (set by the logger to the current user and now, whatever the caller's
context says); stored required precomputed indexed
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

Create MUST succeed only inside the privileged scope `collection_receipt_proposal_event`
(`collection_common.privileged`, a contextvar), opened only by `_proposal_log`, which
sets `user_id` and `event_date` itself and drops caller `default_*` context keys; a
context key of that name MUST have no effect. `write` MUST raise and leave the row
unchanged. `@api.ondelete` MUST raise unless the parent sheet cascade is unlinking (the
`collection_sheet_unlinking` scope). (Previously: create was gated by a context key any
caller could set, with a caller-chosen author and date.)

#### Scenario: Create gated

- GIVEN a create outside the privileged scope, with or without a context key of that name
- WHEN create is attempted
- THEN MUST refuse
- AND inside the scope (via `_proposal_log`), create MUST persist

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

Collections Users (`collection.group_collection_user`) MUST have read+create only
(`1,0,1,0`); plain internal users get no access. Write and unlink ACL MUST be denied. A
global `ir.rule` named
`collection_receipt_proposal_event_company_rule` MUST use
`[('company_id', 'in', company_ids)]` with no `groups`, in a `noupdate` file. Dedicated
groups MUST NOT be added. Calls MUST NOT `sudo()`.

#### Scenario: Other-company hidden

- GIVEN an event in a company the user is not allowed
- WHEN they search events
- THEN that event MUST NOT be visible

#### Scenario: Collections User read and create without sudo

- GIVEN a Collections User of an allowed company
- WHEN they read events or create inside the privileged scope
- THEN ACL MUST allow it without `sudo()`
- AND write/unlink ACL MUST deny
- AND a dedicated event group MUST NOT exist

### Requirement: Mutation events

Board mutations MUST append an event of the matching type: pool assign → `assign`; card
move → `transfer`; partial split → `split`; unify or undo-split → `unify`; circuit
change → `circuit`; manual impute → `impute`; FIFO recompute with non-empty changes →
`auto_impute`; board reset → `reset`; customer close → `close`; reopen → `reopen`. FIFO
with empty `changes` MUST NOT write `auto_impute`.

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
