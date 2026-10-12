# Receipt Proposal FIFO Specification

## Purpose

Each (allocation, kind) circuit redistributes `amount_applied` by FIFO so receipt
`line_ids` / `document_numbers` follow the same order. Closed customers stay frozen.
Board close MUST NOT reuse `collection.allocation.state`.

## ADDED Requirements

### Requirement: FIFO sort key

`_proposal_fifo_key` MUST be identical to `collection.receipt._compute_line_ids` sort:
`(due_date or date.max, invoice_number or "")`. Undated lines MUST sort last. Empty
`invoice_number` MUST sort as `""`.

#### Scenario: Same order as receipt lines

- GIVEN the same allocation lines used to compute a receipt's `line_ids`
- WHEN `_proposal_fifo_key` orders those lines
- THEN the order MUST match `_compute_line_ids`

#### Scenario: Undated last and empty number

- GIVEN lines with due dates D1 < D2 and one line with no due date, plus two same-date
  lines whose numbers sort `"A"` then `""`
- WHEN the FIFO key is applied
- THEN dated lines MUST precede the undated line
- AND `"A"` MUST precede `""` among the same due date

### Requirement: Balance ceiling and remainder

FIFO MUST cap each document at `invoice_balance` (MUST NOT use `invoice_amount`). Oldest
due date first; the last reached line MAY be a partial fill; leftover budget MUST be
surplus; with no documents of that kind, applied MUST be 0 and the budget MUST remain
surplus. Budget defaults to that kind's receipt `total_values`.

#### Scenario: Ceiling is invoice_balance

- GIVEN budget 100, first doc `invoice_amount` 80 and `invoice_balance` 50, next doc
  balance 60
- WHEN the plan runs
- THEN the first doc MUST receive 50
- AND the second MUST receive 50

#### Scenario: Partial fill, surplus, and no documents

- GIVEN budget 30 and one doc balance 100; or budget 80 and docs totaling 50; or budget
  40 and zero docs of that kind
- WHEN the plan runs
- THEN the single doc MUST receive 30; or applied 50 with surplus 30; or applied 0 with
  surplus 40

### Requirement: Idempotent overwrite

Recompute MUST write the plan onto `line.amount_applied` and MUST ignore prior manual
`amount_applied`. Running recompute twice MUST leave amounts unchanged. Result MUST
depend only on current receipt `total_values`, each document's `due_date`, and
`invoice_balance`. When a circuit's applied exceeds that kind's collected, recompute
MUST restore the plan (self-heal).

#### Scenario: Second pass and discarded Imputar

- GIVEN a circuit already matching the plan, or lines with manual `amount_applied` that
  disagree with the plan
- WHEN recompute runs twice, or once after the manual edit
- THEN amounts MUST equal the plan after the first pass and MUST NOT change on the
  second
- AND the manual amounts MUST be overwritten

#### Scenario: Overdraft self-heals

- GIVEN quotation `amount_applied` sums above that kind's `total_values`
- WHEN recompute runs for quotation
- THEN applied amounts MUST match the quotation plan from current collected

### Requirement: Close, reopen, and status

`proposal_closed` MUST freeze the allocation. Recompute on a closed allocation MUST
return without writing. Close MUST require a non-empty note when any circuit has a
difference (collected vs applied or pending). Reopen MUST clear the freeze so later
recompute MAY write. `proposal_status` MUST be one of `sin_iniciar`, `parcial`,
`conciliado`, `a_favor`, `deuda`, `cruce`, `cerrado`. Closed MUST use `cerrado`. The
system MUST NOT reuse `collection.allocation.state` for this freeze. `proposal_closed`,
`proposal_note`, `proposal_closed_uid`, and `proposal_closed_date` MUST be writable and
creatable only inside the board's close/reopen scope (`collection_receipt_proposal_close`)
and MUST be `copy=False`. Recompute and manual impute MUST write the documents whose
`amount_applied` falls before the ones that rise, because core refuses a line write that
raises a receipt's applications above its values.

#### Scenario: Closed frozen

- GIVEN `proposal_closed` is true and current applied disagrees with the plan
- WHEN recompute runs
- THEN stored `amount_applied` MUST be unchanged

#### Scenario: Close note and reopen

- GIVEN a circuit difference and an empty note; or no difference; or a closed customer
- WHEN close runs; or close with a note / no difference; or reopen
- THEN empty-note-with-difference MUST refuse; otherwise close MUST persist
  `proposal_closed`, note, user, and timestamp; reopen MUST clear the freeze

#### Scenario: Status is not allocation state

- GIVEN a draft allocation that is proposal-closed
- WHEN `proposal_status` and `collection.allocation.state` are read
- THEN `proposal_status` MUST be `cerrado`
- AND `state` MUST remain `draft`
