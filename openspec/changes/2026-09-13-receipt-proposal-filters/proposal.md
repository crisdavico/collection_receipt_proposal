# Proposal: Receipt Proposal Board Filters

## Proposal question round

Settled with the requester before apply:

- **Scope:** four controls — customer search, circuit FAC/PRE, pool payment method, and
  a lane sort order. Status chips and "Ocultar cerrados" were offered and declined; the
  status chip on a customer card stays a read-only badge.
- **Where the work happens:** entirely client-side. `get_proposal_board` already ships
  every field a filter reads (`partner_name`, `partner_vat`, `document_type`, the
  per-circuit figures), so there is no new RPC, no new field and no new domain. A filter
  that needed the server would be a different change.
- **Totals follow the filter.** `laneTotals` sums the visible customers and their
  visible circuits, and the header carries the sheet's own figure beside it as a muted
  `de <total>` reference — the same idiom a pool card already uses for a partly assigned
  voucher. Filtering to five customers to ask what money is in play is the reason an
  operator filters at all; hiding cards while the header keeps summing forty-seven of
  them would answer a question nobody asked.
- **The pool chip is exempt.** `Requiere asignación` / `Todo asignado` is a sheet fact,
  so it stays keyed on the unfiltered pool: a method filter that emptied the column MUST
  NOT claim the sheet is finished.
- **Filters hide, they never disable.** A circuit hidden by the circuit filter is not a
  drop target while hidden, and that is the operator's own explicit choice, reversible
  from the same control. Nothing auto-reveals on `dragstart`, and no filter is cleared
  by a mutation.

## Why

The board was built for a sheet an operator could hold on one screen. A real
`collection.sheet` carries dozens of allocations and a pool of mixed payment methods,
and the lane is a single scrolling column: finding one customer means scrolling past
everyone already reconciled, and working the pool by payment method — assign every
cheque, then every transfer, which is how the money physically arrives — means reading
past the ones that are not that method.

Every one of those is a question the payload can already answer. What is missing is the
control that asks it.

## What changes

- **`.rp-filters`**, one wrapping line between the ControlPanel and the board, holding
  the four controls plus a `Limpiar filtros` button that renders only while a filter is
  set. It is paid once per board, like `.isolate-bar` beside it — never per customer.
- **Customer search** over `partner_name` and `partner_vat`, accent- and
  case-insensitive, so `nunez` finds `Núñez`.
- **Circuit filter** `Todos / Facturas / Presupuestos`, which hides the other circuit
  card inside every customer card. This is the one sanctioned way a circuit card is
  hidden — `hasCircuit` still decides only the `.rp-circ.empty` strip, and an empty
  circuit still renders so it can be dropped on.
- **Pool payment method**, whose options are built from the pool itself so the control
  never offers a filter that would empty the column. Keyed on the raw `document_type`
  code, never on the translatable `method` label.
- **Lane sort order**: `Cliente A→Z` (the server's own order, and the default),
  `Mayor deuda`, `Mayor cobrado`, `Más sin imputar`. Sorting copies before it sorts; the
  payload's order is never mutated.
- **`laneTotals`, the customer count and the pool count** follow the filter, each
  carrying the unfiltered figure beside it while a filter is set.
- **A stale pool-method filter is pruned in `applyBoard`**, the same way `collapsed` and
  `openSplits` are: assigning the last cheque clears a `check` filter rather than
  leaving the column empty under a control whose only option is gone.

## Non-goals

- No status filter and no "hide closed" toggle (declined this round).
- No server-side filtering, no new RPC, no stored user preference. Filter state lives in
  `state.filters` and dies with the action, like `collapsed` and `details`.
- The `Asignaciones` XLSX export is unchanged: it is the validated proposal, not the
  operator's current view, and a workbook that silently dropped filtered rows would
  disagree with its own totals.
