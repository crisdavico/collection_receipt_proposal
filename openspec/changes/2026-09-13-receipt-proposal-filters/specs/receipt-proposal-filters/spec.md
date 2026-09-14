# Receipt Proposal Filters Specification

## Purpose

Client-side view controls over the board payload `get_proposal_board` already returns:
customer search, circuit, pool payment method and lane sort order. No RPC, no field and
no domain is added. Filter state lives in the OWL component and dies with the action.

## ADDED Requirements

### Requirement: Filter bar

The board MUST render a `collection_receipt_proposal.FilterBar` template as one wrapping
`.rp-filters` line between the ControlPanel and `<main class="board">`, before
`.isolate-bar`. It MUST hold exactly four controls — customer search, circuit, pool
payment method, lane sort — and a `Limpiar filtros` button that renders only while
`hasFilters` is true. It MUST NOT render inside the lane or inside a customer card: its
height is paid once per board, never once per customer. It MUST NOT render when the
board failed to load.

#### Scenario: Bar renders once, above the board

- GIVEN a loaded board
- WHEN the action renders
- THEN exactly one `.rp-filters` MUST render, before `<main class="board">`
- AND it MUST NOT appear inside `.rp-lane` or `.rp-cust`

#### Scenario: Clear renders only when something is set

- GIVEN every filter at its default
- WHEN the bar renders
- THEN `Limpiar filtros` MUST NOT render
- AND setting any one filter MUST make it render

### Requirement: Customer search

`filters.search` MUST match a column on `partner_name` or `partner_vat`, compared with
case folded and diacritics stripped, so `nunez` matches `Núñez`. An empty or
whitespace-only search MUST match every column.

#### Scenario: Accent-insensitive name match

- GIVEN a column whose `partner_name` is `Núñez S.A.`
- WHEN the search is `nunez`
- THEN that column MUST be visible

#### Scenario: VAT match

- GIVEN a column whose `partner_vat` is `30-12345678-9`
- WHEN the search is `12345678`
- THEN that column MUST be visible

#### Scenario: Empty search matches everything

- GIVEN any board
- WHEN the search is empty or whitespace
- THEN every column MUST be visible

### Requirement: Circuit filter

`filters.circuit` MUST be `""`, `invoice` or `quotation`. When set, a customer card MUST
render only that circuit's card. It MUST NOT hide a customer, and it MUST NOT change
which circuits exist: `hasCircuit` still decides only the `.rp-circ.empty` strip, and an
empty circuit MUST still render when its circuit is visible, because it is the drop
target that creates that circuit's first receipt value.

#### Scenario: One circuit card per customer while filtered

- GIVEN a board with two customers
- WHEN the circuit filter is `invoice`
- THEN every customer card MUST render its FAC card and no PRE card
- AND both customers MUST still be listed

#### Scenario: Empty circuit still renders when visible

- GIVEN a customer with no movements on FAC
- WHEN the circuit filter is `invoice` or unset
- THEN the FAC card MUST render, collapsed to the `.rp-circ.empty` strip

### Requirement: Pool payment method filter

`filters.method` MUST be a raw `collection.voucher.document_type` code or `""`. Its
options MUST be derived from the current pool, one per distinct `document_type` present,
labelled with that voucher's translated `method` and ordered by label, so the control
never offers a filter that would empty the column. It MUST NOT be keyed on the `method`
label, which is translatable. The control MUST render only when the pool offers more
than one distinct type, and MUST NOT render disabled: with one type, filtering by it is
not filtering, and on an empty pool there is nothing to filter — a control drawn dead
reads as a control that is broken.

#### Scenario: Options come from the pool

- GIVEN a pool holding two cheques and one transfer
- WHEN the method options are read
- THEN exactly two options MUST exist, one per distinct `document_type`
- AND a `document_type` absent from the pool MUST NOT be offered

#### Scenario: Nothing to choose between, nothing drawn

- GIVEN a pool that is empty, or that holds one distinct `document_type`
- WHEN the filter bar renders
- THEN the payment-method control MUST NOT render
- AND it MUST NOT render as a disabled control

#### Scenario: Filter narrows the pool only

- GIVEN a pool holding two cheques and one transfer
- WHEN the method filter is `check`
- THEN the pool MUST list the two cheques
- AND the customer lane MUST be unchanged

### Requirement: Stale method filter pruned

`applyBoard` MUST clear `filters.method` whenever the refreshed board's control no
longer offers it — the type has left the pool, or the control has stopped rendering —
the same way it prunes `collapsed` and `openSplits`. A filter MUST NEVER outlive the
control that set it. No other filter MUST be cleared by a mutation.

#### Scenario: Assigning the last cheque clears the cheque filter

- GIVEN the method filter is `check` and the pool holds one cheque
- WHEN that cheque is assigned and the refreshed board arrives
- THEN `filters.method` MUST be `""`
- AND the pool MUST render its remaining vouchers

#### Scenario: Search and sort survive a mutation

- GIVEN a search and a non-default sort are set
- WHEN any mutating RPC returns a refreshed board
- THEN both MUST still be set

### Requirement: Lane sort order

`filters.sort` MUST be one of `name` (the payload's own partner-name order, and the
default), `debt`, `collected`, `pending`. `debt`, `collected` and `pending` MUST order
descending on the sum over the **visible** circuits of, respectively, `total`,
`collected` and `available`. Sorting MUST copy before it sorts and MUST NOT mutate the
payload's `columns`.

#### Scenario: Default keeps the server order

- GIVEN `filters.sort` is `name`
- WHEN the lane renders
- THEN the columns MUST appear in the order `get_proposal_board` returned them

#### Scenario: Descending by debt

- GIVEN three customers with debts 100, 300 and 200
- WHEN `filters.sort` is `debt`
- THEN they MUST render 300, 200, 100

#### Scenario: Sorting leaves the payload untouched

- GIVEN any non-default sort
- WHEN the lane renders
- THEN `state.board.columns` MUST keep the order it was received in

### Requirement: Totals follow the filter

`laneTotals` MUST sum only the visible columns and, within each, only the visible
circuits. While any filter is set the lane header MUST also show the unfiltered figure
as a muted reference, and the customer and pool counts MUST read `N de M`. The lane
header MUST stay one wrapping line carrying exactly the `Cobrado` and `Deuda` pair.

#### Scenario: Filtered lane sums the visible customers

- GIVEN a sheet whose customers collected 100, 200 and 300
- WHEN the search leaves only the first two visible
- THEN the header `Cobrado` MUST read 300 and MUST show 600 as its reference

#### Scenario: Circuit filter narrows the sum

- GIVEN a customer collecting 100 on FAC and 50 on PRE
- WHEN the circuit filter is `invoice`
- THEN the header `Cobrado` MUST read 100

### Requirement: Pool chip ignores the filter

The pool's `Requiere asignación` / `Todo asignado` chip MUST be keyed on the unfiltered
pool: a method filter that renders no card MUST NOT make it read `Todo asignado`.
`Pendiente de asignar` follows the filter like every other figure and MUST carry the
sheet's own total beside it while filtered.

#### Scenario: Filtered-empty pool still requires assignment

- GIVEN a pool holding one transfer
- WHEN the method filter is `check`
- THEN the pool MUST render no card
- AND the chip MUST still read `Requiere asignación`

### Requirement: Filters hide, never disable

A filter MUST only remove cards from the render. It MUST NOT disable a drop zone, clear
`isolate`, close an expanded circuit, or change any RPC argument. Nothing MUST
auto-reveal on `dragstart`. `Escape` MUST keep its current meaning and MUST NOT clear a
filter.

#### Scenario: Drag is unaffected

- GIVEN any filter is set
- WHEN a voucher is dragged onto a visible circuit
- THEN the transfer modal MUST open with the same arguments it would open with unfiltered

#### Scenario: Escape does not clear filters

- GIVEN a search is set and a circuit is expanded
- WHEN `Escape` is pressed
- THEN every expanded circuit MUST close
- AND the search MUST still be set

### Requirement: Filter logic stays pure

Matching, ordering and option-building MUST live in
`receipt_proposal_helpers.esm.js` as pure exported functions, which MUST keep importing
only `_t`. The component MUST expose them as `visibleColumns`, `visiblePool` and
`poolMethodOptions` getters and MUST NOT filter inside a template expression.

#### Scenario: Helpers stay free of Odoo services

- GIVEN the helpers module
- WHEN its imports are read
- THEN only `@web/core/l10n/translation` MUST be imported
