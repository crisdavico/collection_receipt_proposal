Drag-and-drop reconciliation board for collection sheets in **Proposal**.

The `collection` addon already models what a cobranza needs, but not the step that
distributes the money: an operator had to edit `amount_applied` row by row with no view
of the whole sheet. This addon adds that step — the phase between **Confirm** and
**Close**.

A board opens from a `collection.sheet` in `proposal` (header button **Receipt
Proposal**) and reads left to right in two columns. The first holds the _unassigned_
pool: vouchers with money still to distribute, which by definition answer to no customer
debt yet. The second stacks one card per `collection.allocation`, and inside each of
them one card per circuit (`document_kind` `invoice` / `quotation`) carrying that
circuit's figures and the `collection.receipt.value` rows applied to it. **Ver
detalle**, on the circuit card's header line, expands that card downwards in place — the
card keeps its width, so the customer under the pointer does not re-lay out — to show
that debt in full: its documents, their balances and the editable imputation. As many
circuits stay expanded as the operator wants, and `Escape` closes them all.

A voucher is dragged from the pool onto the FAC or PRE card of a customer, so the drop
itself answers which circuit the money belongs to; it may be split across customers of
the same sheet.

A real planilla carries dozens of customers and a pool of mixed payment methods, so one
wrapping line of controls sits above the board — paid once, never once per customer. It
searches the lane by customer name or CUIT (accent-blind: `nunez` finds `Núñez`),
narrows every customer card to one circuit, narrows the pool to one payment method, and
reorders the lane by customer, by debt, by collected, or by what is collected and still
unimputed — the sort that puts the work that is left at the top. Every one of them reads
a figure the board already has, so nothing is asked of the server and no filter outlives
the screen. Filters hide and never disable: what they take away, the same control puts
back. The figures follow what is shown and name the sheet's own beside them, so a
filtered header never passes itself off as the whole planilla — except the pool's
`Requiere asignación`, which stays a fact about the planilla no filter can talk it out
of.

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
difference); a closed customer freezes and later redistributions skip it.

The proposal can leave Odoo as a spreadsheet: the header button **Exportar
Asignaciones** (visible on a sheet in `proposal` and on the `closed` sheet afterwards)
downloads a two-sheet workbook built in the same visual language as the Planilla de
Cobranza. **Resumen** carries one row per `(customer, circuit)` — collected, applied, on
account, total debt, pending, plus the per-circuit status.

**Clientes** stacks one section per customer, and inside it one section per circuit —
which is to say, per `collection.receipt`. Each circuit shows the documents it imputed
in the FIFO order the money followed, then the vouchers that funded it as one
`Comprobantes — <tipo>` block per payment method, each reshaped to the fields that
method actually has: a cheque prints bank, type and both dates, a transfer prints its
two accounts, a retention its kind. Then any cash a remittance replaced, then the
circuit's balance — cobrado, aplicado, a cuenta — read straight off the subtotals above
it. The circuit balances add into a customer total, the customer totals into a sheet
total, and the sheet closes with the money no receipt claimed and a reconciliation
against the sheet's own voucher total. A voucher split across circuits is highlighted
and only ever subtotalled by the share it put into that receipt.

The colouring is a deliberate ladder rather than decoration: the customer, circuit and
block headings step dark to light through one blue family so the nesting is legible at a
glance, subtotals stay quiet and are closed by a rule instead of a louder fill, and the
four total levels — block subtotal, circuit balance, customer total, sheet total — are
ranked by weight and size. Data rows carry a faint stripe to help the eye cross nine
columns. The only warm accent is a split voucher, and the reconciliation's Diferencia
row turns green or red so a sheet that does not close says so.

Both sheets are built from the board's own helpers, so the workbook can never disagree
with the screen.
