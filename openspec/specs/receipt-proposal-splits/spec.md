# Receipt Proposal Splits Specification

## Purpose

While this addon is installed, one voucher MAY back more than one customer on the same
proposal sheet. Cross-sheet splits stay forbidden. A sheet-wide amount cap MUST keep
voucher totals valid; core counts each customer's collected money from its receipt
values, so the largest-share owner pointer only names one owner.

## ADDED Requirements

### Requirement: Largest-share owner

After every mutation that changes a voucher's values, `voucher.allocation_id` MUST point
at the allocation that holds the largest assigned share of that voucher.

#### Scenario: Re-point after split

- GIVEN V assigned 30 to A then 70 to B
- WHEN the mutation completes
- THEN `voucher.allocation_id` MUST be B's allocation

#### Scenario: Re-point after undo

- GIVEN V split 70 on B and 30 on A, owner B
- WHEN undo-split keeps A's value
- THEN `voucher.allocation_id` MUST be A's allocation

### Requirement: Unify and undo split

Unify MUST merge a voucher's remaining value rows into one receipt value. Undo-split
MUST keep `keep_value_id`, unlink the voucher's other values, and set the kept amount to
the prior assigned total. After either, the voucher MUST have exactly one value row.

#### Scenario: Unify merges parts

- GIVEN V with two values toward the same destination receipt
- WHEN transfer runs with unify
- THEN exactly one value MUST remain for that voucher on that receipt
- AND its amount MUST equal the merged total

#### Scenario: Undo split keeps one part

- GIVEN V with values V1 (keep) amount 40 and V2 amount 60
- WHEN undo-split runs with `keep_value_id` = V1
- THEN V2 MUST be gone
- AND V1.amount MUST be 100

### Requirement: Replaced cash and remittance board lock

Proposal free amount MUST be `amount − assigned − replaced_amount`. A voucher whose free
amount is `<=` 0 MUST NOT appear in the unassigned pool. `seller_deposit` remittance
vouchers ARE pool cards (draggable onto a circuit) but MUST NOT receive `allocation_id`
from board owner sync. Replaced cash MUST keep its `allocation_id` after board mutations that do not
assign a remaining free share. Largest-share owner and partner-identity relax MUST remain
in this addon.
(Previously: Free amount was `amount − assigned` only, so replaced cash reappeared in
the pool.)

#### Scenario: Replaced cash leaves the pool

- GIVEN a cash voucher whose `replaced_amount` equals its `amount`
- WHEN the proposal board payload is built
- THEN that voucher MUST NOT appear in the unassigned pool

#### Scenario: Partial replace remains only for the free remainder

- GIVEN a cash voucher amount 100, assigned 0, replaced 40
- WHEN the proposal board payload is built
- THEN free amount MUST be 60
- AND the voucher MAY appear in the pool only for 60

#### Scenario: Remittance is pool-draggable but never owned

- GIVEN a `seller_deposit` with free amount greater than zero
- WHEN a board transfer from the pool targets a customer circuit
- THEN MUST succeed and that circuit's collected amount MUST include it
- AND that voucher `allocation_id` MUST remain unset

#### Scenario: Replaced cash keeps allocation_id

- GIVEN replaced cash with `allocation_id` set to customer A and zero remaining values
- WHEN a board mutation runs owner sync
- THEN `allocation_id` MUST remain A's allocation
- AND MUST NOT be cleared
