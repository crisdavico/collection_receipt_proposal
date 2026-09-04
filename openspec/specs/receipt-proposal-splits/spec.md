# Receipt Proposal Splits Specification

## Purpose

While this addon is installed, one voucher MAY back more than one customer on the same
proposal sheet. Cross-sheet splits stay forbidden. A sheet-wide amount cap and a
largest-share owner pointer MUST keep voucher totals valid.

## ADDED Requirements

### Requirement: Same-sheet split

While this addon is installed, `_check_same_allocation` MUST accept a
`collection.receipt.value` if and only if `voucher.sheet_id` equals `receipt.sheet_id`.
Same-sheet cross-customer values MUST persist. Values whose voucher and receipt belong
to different sheets MUST be refused. UNIQUE(receipt, voucher) and amount `> 0` MUST
still hold.

#### Scenario: Cross-customer same sheet accepted

- GIVEN voucher V amount 100 on sheet S, primarily on customer A
- WHEN values 40 on A's invoice receipt and 60 on customer B's invoice receipt on S
  persist
- THEN both MUST persist

#### Scenario: Cross-sheet refused

- GIVEN voucher V on sheet S1
- WHEN a value linking V to a receipt on sheet S2 is persisted
- THEN MUST refuse
- AND stored rows MUST be unchanged

### Requirement: Sheet-wide split cap

`_check_voucher_split_cap` MUST sum ALL `collection.receipt.value` amounts of the
voucher (MUST NOT filter by allocation). The system MUST compare that sum to the voucher
amount with `currency.compare_amounts`. Persist MUST refuse when the sum exceeds the
voucher amount.

#### Scenario: Over-cap across customers refused

- GIVEN voucher V amount 100 with 40 on A and 50 on B (same sheet)
- WHEN a further 20 on C is persisted
- THEN MUST refuse because 110 exceeds 100

#### Scenario: At-cap allowed

- GIVEN voucher V amount 100 with 40 on A
- WHEN 60 is persisted on B
- THEN both MUST persist

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
