# Tasks: Receipt Proposal Board Filters

<!-- prettier-ignore-start -->

## Review Workload Forecast

Lines: 550-650 (about 260 source, about 340 tests). Split: one PR to addon `master`.

Decision needed before apply: No
Chained PRs recommended: No
400-line budget risk: Low

### Suggested Work Units

Client-side only — no model, no RPC, no security, no `collection/` edit. Docstrings
`"""RED/GREEN: <what>."""`. Test:
`invoke test -m collection_receipt_proposal --mode=update`.

| Unit | Goal | Focused test command | Rollback boundary |
|---|---|---|---|
|1|Pure helpers|`:TestReceiptProposalUi`|`receipt_proposal_helpers.esm.js`|
|2|Component state + getters|`:TestReceiptProposalUi`|`receipt_proposal_action.esm.js`|
|3|Bar template + SCSS|`:TestReceiptProposalUi`|`receipt_proposal_action.xml`, `.scss`|
|4|Docs|`:TestReceiptProposalUi`|AGENTS.md, readme|

## Phase 1: Pure helpers

- [x] 1.1 RED `tests/test_receipt_proposal_ui.py` — helper surface exports
      `FILTER_DEFAULTS`, `SORT_ORDERS`, `normalizeText`, `matchesCustomer`,
      `filterPool`, `poolMethodOptions`, `sortColumns`, `columnTotals`.
- [x] 1.2 RED same file — helpers still import only `_t`.
- [x] 1.3 GREEN implement them in `receipt_proposal_helpers.esm.js`.

## Phase 2: Component

- [x] 2.1 RED — `state.filters` defaults; `visibleColumns` / `visiblePool` /
      `poolMethodOptions` getters; `laneTotals` sums the visible set; `sheetTotals`
      keeps the unfiltered pair; `hasFilters`; `clearFilters`.
- [x] 2.2 RED — `applyBoard` prunes a stale `filters.method` and touches nothing else;
      `onEscape` is unchanged.
- [x] 2.3 RED — `sortColumns` copies before it sorts.
- [x] 2.4 GREEN implement in `receipt_proposal_action.esm.js`.

## Phase 3: Template and SCSS

- [x] 3.1 RED — `collection_receipt_proposal.FilterBar` joins the exact `t-name` set;
      the bar renders before `<main class="board">`; `Limpiar filtros` is gated on
      `hasFilters`.
- [x] 3.2 RED — lane loops `visibleColumns`, pool loops `visiblePool`, circuit loop
      runs over `visibleCircuitKeys`; the pool chip stays keyed on `pool.length`.
- [x] 3.3 RED — `.rp-filters` is one wrapping row, paid once, with the narrow-screen
      override; no framework class-name collision.
- [x] 3.4 GREEN implement template + SCSS.

## Phase 4: Docs

- [x] 4.1 AGENTS.md — the filter rules under "Domain rules (do not break)".
- [x] 4.2 `readme/DESCRIPTION.md` + regenerate `README.rst`.
- [x] 4.3 Bump `__manifest__.py` to `19.0.1.5.0`.

## Verify

- [x] V.1 `invoke test -m collection_receipt_proposal --mode=update`
- [x] V.2 `invoke test -m collection --mode=update`
- [x] V.3 `pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**`

<!-- prettier-ignore-end -->
