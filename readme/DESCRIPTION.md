Drag-and-drop reconciliation board for collection sheets in **Proposal**.

The `collection` addon already models what a cobranza needs, but not the step that
distributes the money: an operator had to edit `amount_applied` row by row with no view
of the whole sheet. This addon adds that step — the phase between **Confirm** and
**Close**.

A board opens from a `collection.sheet` in `proposal` (header button **Receipt
Proposal**). One column per `collection.allocation`, one card per
`collection.receipt.value`, two circuits per customer (`document_kind` `invoice` /
`quotation`), and an _unassigned_ pool of vouchers with money still to distribute. Cards
are dragged between customers and circuits; a voucher may be split across customers of
the same sheet.

Every change to a `(customer, circuit)` pair's collected total triggers a full FIFO
redistribution of that circuit: oldest `due_date` first, each document capped at its
`invoice_balance`, partial fill on the last document reached. The redistribution is
idempotent and discards manual `Imputar` edits, so the result depends only on the
current collected amount, the documents' due dates and their outstanding balances. FIFO
ordering is byte-identical to `collection.receipt._compute_line_ids`, so the receipt's
Applications page and its stored `document_numbers` summary always name documents in the
order the money followed.

The board writes into the existing `collection.*` models only — it stores the validated
proposal and never touches Odoo accounting. Every operation is recorded on the immutable
`collection.receipt.proposal.event` model with user, timestamp and from → to values.
Customers can be closed individually (a note is required when a circuit still shows a
difference); closed columns freeze and later redistributions skip them.
