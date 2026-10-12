# AGENTS.md — collection_receipt_proposal

Agent operating manual for the **Conciliación de Cobranzas** board. Human docs:
[README.rst](README.rst) (generated from
[readme/DESCRIPTION.md](readme/DESCRIPTION.md)). Base addon this one extends:
[collection/AGENTS.md](../collection/AGENTS.md). Parent Doodba context:
[seedian/AGENTS.md](../../../../../AGENTS.md).

Ground truth order: source under this directory → `../collection/AGENTS.md` → this file
→ parent AGENTS.md.

## Project overview

- **What:** the reconciliation step between sheet **Confirm** (`proposal`) and **Close**
  — a drag-and-drop board that distributes a `collection.sheet`'s collected money across
  customers and the two circuits, keeping the imputación consistent by FIFO.
- **Stack:** Odoo 19, PostgreSQL 17, Doodba (`seedian` compose project).
  `depends: ["collection"]`, version `19.0.1.6.0`, `application: False`.
- **Stores the validated proposal only.** It writes into the existing `collection.*`
  models and never touches Odoo accounting. The report over this data is the
  **Asignaciones** XLSX export (`action_print_receipt_assignment_xlsx`), read-only and
  built from the same board helpers.

### The mapping (settled — this drives everything)

| Board concept               | Odoo model                                           |
| --------------------------- | ---------------------------------------------------- |
| Board                       | one `collection.sheet` in state `proposal`           |
| Customer card (column 2)    | `collection.allocation` (UNIQUE per sheet+partner)   |
| Circuito **FAC** / **PRE**  | `document_kind` = `invoice` / `quotation`            |
| Voucher row inside it       | `collection.receipt.value` (voucher × amount)        |
| Per-(customer, circuit) box | `collection.receipt` (UNIQUE per allocation+kind)    |
| Documento                   | `collection.allocation.line` of that `document_kind` |
| "Imputado"                  | `collection.allocation.line.amount_applied`          |
| "Sin imputar / a favor"     | `collection.receipt.amount_on_account`               |
| "Sin asignar" pool          | free > 0, `seller_deposit` included (synthetic)      |

## Repository map

| Path                                                | Role                                                                                                      |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `models/collection_receipt_value.py`                | Board card payload (`_proposal_card_payload`); same-sheet/cap live in core `collection`                   |
| `models/collection_voucher.py`                      | assigned / free (− `replaced_amount`); `_proposal_card_label`; pool payload                               |
| `models/collection_allocation.py`                   | Per-circuit figures + status (`_proposal_kind_status`); FIFO engine; close/reopen; payload                |
| `models/collection_receipt_proposal_event.py`       | Immutable audit trail; gated create; `_proposal_log` is the only sanctioned writer                        |
| `models/collection_sheet.py`                        | `action_open_receipt_proposal` + the whole board RPC surface; row locks; Close confirmation hook          |
| `models/collection_assignment_report.py`            | Asignaciones payload + `action_print_receipt_assignment_xlsx`; customer/circuit blocks, unassigned, recon |
| `report/collection_receipt_assignment_xlsx.py`      | ORM-free xlsxwriter builder (`Resumen` + `Clientes`); formats reused from `collection`                    |
| `security/ir.model.access.csv`                      | Event `1,0,1,0` for Collections User; close-confirm wizard `1,1,1,0` for Collections Manager              |
| `security/collection_receipt_proposal_security.xml` | One global company `ir.rule` on the event model                                                           |
| `views/collection_receipt_proposal_views.xml`       | `ir.actions.client` + the two inherited sheet-form header buttons                                         |
| `static/src/receipt_proposal/`                      | OWL client action (two-column board), pure helpers, templates, scoped SCSS                                |
| `static/src/receipt_proposal/amount_parser.esm.js`  | Import-free, locale-aware `parseAmount` / `rawAmount` (run in Node by the test suite)                     |
| `wizard/collection_sheet_close_confirm.py`          | Manager-only Close confirmation for an unfinished board (D7, warn only)                                   |
| `i18n/`                                             | `collection_receipt_proposal.pot` + `es_AR.po`                                                            |
| `tests/common.py`                                   | Receipt-shaped fixtures replicated from `collection`'s `TestCollectionReceipt`                            |

## Domain rules (do not break)

- **FIFO ordering MUST mirror `collection.receipt._compute_line_ids` byte for byte:**
  `(line.due_date or date.max, line.invoice_number or "")`, undated lines last.
  `document_numbers` is stored and renders `line_ids` in that order, so a FIFO that
  distributed in a different order would name documents in an order the money did not
  follow. `tests/test_receipt_proposal_order.py` is the guard against the two drifting.
- **FIFO ceiling is `invoice_balance`**, never `invoice_amount`: each document absorbs
  up to what the ERP still says is owed, then spills to the next.
- **`action_print_xlsx` MUST stay the last `type="object"` header button** on the sheet
  form: both `collection`'s `test_collection_ui` and this addon's
  `test_receipt_proposal_ui` assert it. New header buttons go _before_ it — the
  Asignaciones export is injected right after `action_open_receipt_proposal`.
- **The Asignaciones export is read-only and reuses the board's helpers**
  (`_proposal_kind_figures`, `_proposal_kind_lines`, `_proposal_kind_status`) plus
  `collection`'s customer codes and xlsxwriter formats. It never re-sorts documents and
  never recomputes a figure of its own. Gated on sheet `proposal` / `closed`; mixed
  allocation currencies raise, like the Planilla.
- **The `Clientes` sheet speaks the Planilla's language, nested by customer.** Nine
  columns, three heading levels that MUST stay visually distinct: navy `section` for the
  customer, lighter `band` for the circuit, grey `minor` for a block inside it. Each
  circuit _is_ a `collection.receipt`, so the sheet is the receipt simulation grouped
  the way an operator reads it.
- **Vouchers print one `Comprobantes — <tipo>` block per payment method**, each reshaped
  to the fields that method actually has — the same idea as `collection`'s own
  `_VOUCHER_BLOCK_COLUMNS`, generalised. A shape declares a `date` column and exactly
  four middle columns (`_VOUCHER_AMOUNT_COL - 2`); a test pins that arithmetic. No type
  ever carries a column that is always blank for it.
- **Only the applied column is ever summed.** A document block sums column F
  (`amount_applied`); a voucher block sums column I (the receipt value's share, or
  `proposal_free_amount` in the unassigned section). `Importe del Valor` in column H is
  for the reader and MUST NOT be subtotalled — a voucher split across two receipts would
  be double-counted — and the voucher subtotal's label merge deliberately swallows it so
  there is nowhere to put a wrong number. Cash-replacement amounts sit in their own
  column D for the same reason: the move is already reflected in the voucher rows.
- **Every total is a reference, never a recomputation.** The circuit balance reads the
  voucher subtotal cells and the document subtotal cell; the customer total reads its
  circuit balances; the sheet total reads the customer totals; the reconciliation reads
  the sheet total and the unassigned total. Each carries the ORM's own figure as its
  cached value, so a board/workbook divergence surfaces on the first recalculation. The
  document block is therefore emitted even when empty, so that reference is always
  valid.
- **The palette is a ladder, and fills mean structure.** Three heading levels step dark
  → medium → light in one blue family (`LVL1_FILL` customer, `LVL2_FILL` circuit,
  `LVL3_FILL` block), each at least 1.4x apart in luminance and each lighter than the
  last, with `collection`'s `HDR_BLUE` column header lighter still. Totals are ranked by
  **rule and type, not by more fills**: a quiet `SUB_FILL` subtotal closed by a navy top
  rule, then the dark `BALANCE_FILL` circuit band, then the customer total and the grand
  total sharing `LVL1_FILL` and separated by font size. Data rows carry a ~1.1x
  `ZEBRA_FILL` stripe — a hint for tracking across nine columns, never a band. The one
  warm accent is the split-voucher flag; the Diferencia row borrows `collection`'s own
  `_BANNER_FILL`. `tests/test_receipt_assignment_xlsx.py` pins the monotonic ladder, the
  1.25x adjacent-fill floor and a 4.5:1 WCAG AA text floor on every pair — do not add a
  fill without re-running it.
- **`_receipt_formats` MUST stay additive.** It never overrides a key the shared
  `_formats` already owns, so `Resumen` and the Planilla keep the house look byte for
  byte. New Clientes roles get new key names.
- **The `Clientes` sheet MUST NOT carry an autofilter.** It stacks customer, circuit,
  block, subtotal and balance rows, so filtering would hide rows the `SUM`s still count.
  It freezes and repeats the membrete instead.
- **`Valores sin asignar` keeps `seller_deposit`**, like the board pool: a remittance
  holding free money is a pool card, and the section exists to close the reconciliation
  against `sum(voucher.amount)`, so it has to appear.
- **The board is two columns, and the debt detail is revealed in place.** Column 1 is
  the unassigned pool — vouchers with no relationship to any customer debt yet. Column 2
  is the customer lane: one `.rp-cust` card per allocation, each holding exactly two
  `.rp-circ` cards (FAC and PRE) with that circuit's figures and the voucher rows
  applied to it. **Ver detalle** inside a circuit card expands that card in place
  (`CircuitDetail`), revealing the documents plus the editable imputation — there is no
  `ImputeModal` and no third column. A third column was built and removed: it spent
  ~420px re-stating the customer and circuit the card beside it already named, and took
  that width from the lane, leaving a circuit card ~320px wide — too narrow for the
  four-column grid it had to hold. `tests/test_receipt_proposal_ui.py` pins the two
  `t-call`s of `<main class="board">` in order.
- **The detail grid is one line per document, and it never scrolls sideways.** The
  shared `th`/`td` rhythm (11px both axes) is tuned for a dialog; inside a card nested
  two levels deep a stacked number+dates cell costs ~56px per document and the card
  outgrows the viewport. So `.rp-circ-detail` gives each fact its own column
  (`Documento | Vence | Emitida | Importe | Saldo | Imputado`, ~30px a row) on its own
  tighter padding (`6px 4px`) — the shared `td` rhythm is untouched, because the dialog
  still needs it. The grid lives in half a customer card, which is narrower than six
  natural columns, so it is **fitted** to the card rather than scrolled inside it:
  `table-layout: fixed` with per-column shares that add up to 100, and the `.table-wrap`
  scrolls on **one** axis only (`38vh` under a sticky header, so twenty invoices scroll
  rather than stretch the lane; `overflow-x: hidden`). Reading an imputation means
  comparing Saldo against Imputado, and a sideways scrollbar put those two on different
  screens. When the card is too narrow even for fitted columns it **drops a column
  rather than cut a figure**, in this order (`@container` on `.rp-circ-detail`, which is
  sized by the card and not by the viewport): Emitida at 480px, Importe at 400px, then
  the type steps down at 320px. Dates render short (`fmtDate` → `dd/mm/yy`) and the two
  money columns render bare (`fmtBare`, no symbol — the column heading says which figure
  it is and the Imputado input never had one); the full value of every cell rides on its
  `title`. The document number is the only cell allowed to reflow — its tail is what
  tells one invoice from the next, so it wraps instead of ending in an ellipsis. Never
  widen the shared `td` padding over this, never re-stack a cell, and never hand a
  column back to a horizontal scrollbar: `tests/test_receipt_proposal_ui.py` pins the
  six columns, the one-line cells, the fitted layout, the drop order and the shares
  summing to 100.
- **One figures line, in the header, live while expanded.** `.rp-circ-nums` sits inside
  `.rp-circ-head` beside the tag, the name and the value count — the header's middle was
  empty on a card that can be 1400px wide while the figures owned a row below it, and a
  third row restated them once expanded. `circuitFigures(column, kind)` returns the
  payload's figures normally and the ones the operator's inputs are producing while that
  circuit is expanded, which is what lets one line do both jobs. There is no
  `.rp-circ-live` strip and no `.rp-circ-detail-top`; `CircuitDetail` is the grid plus
  its warnings, with no heading and no buttons. Figures read label-beside-number and
  wrap — never `flex-direction: column`, never `justify-content: space-between`, which
  tore them to opposite edges. `Distribuir por antigüedad` and `Confirmar imputación`
  share the one `.rp-circ-foot`, which renders **only while expanded**; the Ver/Ocultar
  toggle is `.rp-circ-toggle`, last on the header line (see the density rule below). The
  visible "Imputar cobranza a …" heading became the grid's `aria-label`: the section is
  self-evident from the card it is inside, but the grid still needs an accessible name.
  The FIFO warning is the `Distribuir` button's `title`, not body copy — as a sentence
  it wrapped to two lines on every expansion. `.rp-circ-detail` is capped at
  `max-width: 900px` so the grid reads as a block instead of a ribbon.
- **An expanded circuit MUST keep its grid track and grow downwards**: it does not span
  the customer card (`.rp-circ.expanded` sets no `grid-column`), so the other circuit
  stays beside it rather than being pushed to a new row and the cards on the board never
  change width. Half a card is narrower than six natural columns, so the grid is fitted
  to the card it has — see the detail-grid rule above — and
  `.rp-circ-detail .table-wrap` scrolls vertically only. Any number of circuits are
  expanded at once (`state.details` is a list of `{allocation_id, kind, budget, rows}`
  entries, one per open grid) — the operator compares what a customer owes across both
  circuits, and the same circuit across customers, so closing one grid MUST leave the
  rest open. Every impute reader takes its entry (`imputeRows(detail)`,
  `imputeApplied(detail)`, `imputeLocked(detail)`, …) and the card reads its own with
  `detailOf(column.allocation_id, kind)`; `Escape` closes them all at once.
- **The lane's height is spent on figures, never on repeated chrome.** The operator
  reads this lane by scanning customers, so every pixel a card spends is paid once per
  customer on screen. Three rules hold the density, and none of them deletes a number:
  the footer exists only while a circuit is expanded (`Ver detalle` is a text toggle on
  the header line the card already draws — as a 28px button in a footer of its own it
  cost ~36px per circuit, ~72px per customer); the CUIT rides beside the partner name
  instead of stacking under it; and the circuit's noun lives **inside** the `.ct` pill
  (`Facturas` / `Presupuestos`, uppercased by CSS) rather than in a `.rp-circ-lab`
  repeating what the pill already said — which is also what keeps the four figures plus
  the count on one header line instead of wrapping to two. A collapsed circuit is
  therefore head + bar + rows, ~70px. If you need room, take it from chrome or from the
  `.rp-lane-body` / `.rp-cust-body` gaps; do not drop a figure, and do not round the
  amounts to `fmtShort` — a pending of `$ 0,40` must not read as `$ 0`.
  `tests/test_receipt_proposal_ui.py` pins the footer's `t-if`, the header toggle, the
  four figures, the one pill and the inline CUIT.
- **The lane's own header is one line.** `.rp-lane-head` is paid once, before the first
  card, and stacked — a title over a row of stacked label/number pairs — it cost ~100px
  of the lane, about a whole customer card. It is a single wrapping flex row instead:
  the `cliente(s)` count renders inline beside the title (`display: inline`, lane-scoped
  so the pool column's stacked `.rp-col-head` is untouched) and the totals read
  label-beside-number at the right of that row. It carries **two** figures, `Cobrado`
  and `Deuda`: Imputado and Sin imputar are per-circuit questions, answered per circuit
  by the card below and by the drawer, and summed over every customer and both circuits
  they name nothing the operator can act on. `laneTotals` therefore sums only those two,
  and its Deuda is `figures.total` — the documents' own `invoice_balance`, the same
  figure a circuit card labels Deuda. It MUST NOT sum `pending` (`total - applied`):
  netting out what is already imputed makes the lane's debt read `$ 0` on exactly the
  board that is finished, which is the one case the header is read on. The pool column
  keeps its taller head: it carries the chip and the drag hint, and its cards are not
  what the operator scans.
- **A value card is coloured by its payment type; a circuit card is coloured by its
  circuit. Two colour systems, two sets of tokens, and neither writes the other's.**
  `--c` / `--c-ink` / `--c-soft` / `--c-tint` are the circuit's, assigned by `.c-inv` /
  `.c-quo` / `.c-none`, and they dress what a circuit owns: the `.rp-circ` card, its
  `.ct` pill, its drop zones, the `tstrip` and the previews. `--g` / `--g-ink` /
  `--g-soft` / `--g-tint` are the payment type's, assigned by `.t-<code>`, and they
  dress what a **comprobante** owns: the pool's `article.rp-card` and the lane's
  `.rp-vrow`, **whole** — rail (`--g`), wash (`--g-tint`) and, by inheritance, the
  `.pay-glyph` chip (`--g-soft` + `--g-ink`, which is why the chip picks no class of its
  own and falls back to the house greys). A `.c-*` rule MUST NOT declare a `--g*` and a
  `.t-*` MUST NOT declare a `--c*`; borrowing by value (`.t-unsupported` reading
  `--ink-3`, the way `.c-none` does) is fine. Neither reading is lost by this split: a
  pool card has **no circuit at all** — its old `c-none` painted grey on grey — and an
  assigned row is already inside the circuit card that names FAC / PRE with its pill and
  its own tint, so the row's colour used to spend itself restating what its container
  had just said. What a row cannot say on its own is which comprobante it is, and that
  is what it now says. `typeClass(document_type)` is the only builder of that class and
  it goes through `glyphOf`, so a class can never name a rule the SCSS does not have;
  there is no `cardClass` any more.
- **The payment type is read by shape FIRST and by hue second.** The `.pay-glyph` chip
  rendered by `collection_receipt_proposal.TypeGlyph` keeps one inline SVG per code with
  `unsupported` as the `t-else` fallback, and that branch set MUST stay complete: shape
  is what survives a colour-blind operator, a greyscale print and a 150px card. The
  translated method label is written right beside it, so hue is always reinforcement and
  never the only carrier. The palette is constrained so that the second colour system
  cannot be mistaken for the first: **seven hues spread around the wheel, each at least
  20° off `--fac` (246°), off `--pre` (189°) and off every other type**, each `-ink` at
  ≥ 4.5:1 on its own `-soft` — that ink paints a 1.4px stroke, the thinnest mark the
  board draws — and each `-tint` built as `rgba()` of **its own** base at `0.11`, the
  alpha the circuit tints already use, so a wash can never drift onto a neighbour's hue.
  `unsupported` deliberately has no hue: `.t-unsupported` is the neutral twin of
  `.c-none`, because a type the catalogue cannot name has not earned a colour in the
  key. The chip stays engraved (`--inset-sm`) and rides **inside** `.pay-method`, which
  is already an 18px `inline-flex` line on both card shapes, so the glyph costs the lane
  no height (see the density rule above), and it carries `aria-hidden` because the
  method label is written right beside it. Both payloads therefore ship the raw
  `document_type` code alongside the translated `method` label: the label is
  translatable and cannot be keyed on. `tests/test_receipt_proposal_ui.py` pins the
  branch order, both cards' class, the token ownership of each system, the contrast
  floor, the hue spread and the tint's provenance;
  `tests/test_receipt_proposal_board.py` pins the payload key.

- **A circuit card looks the same on every customer, and its frame is what says so.**
  Facturas and Presupuestos are read by **comparing customers** — the same circuit down
  the lane — so `.rp-circ` is framed with a 1px border in `var(--c-line, var(--edge))`,
  and `--c-line` (`--fac-line` / `--pre-line`, the circuit hue at `0.45`) is set by the
  circuit classes and by nothing else. What differs from customer to customer is the
  voucher rows inside, which are coloured by payment type; the frame is what says that a
  card full of cheques and a card full of transfers are still the same Facturas. **No
  property of a circuit card may be keyed on its contents** — not the border, not the
  wash, not a `--g*`. `.rp-circ.empty` keeps that same frame and only breaks it into
  dashes (`border-style: dashed`): the strip **is** the invitation to drop, which is
  what a dashed edge already says, and the grey `outline` it used to draw on top of the
  border said it twice in a colour the circuit does not own — it is gone, one mechanism
  does both jobs.
- **A customer card closes itself off with a hard edge, not with a shadow.** `.rp-cust`
  carries `border: 1px solid var(--edge)` — the house's own shadow colour raised to an
  alpha that reads as a line — plus the `--raise-sm` it already had. The card is tall
  (header, two circuit cards, more when one is expanded), so where one customer ends and
  the next begins has to be visible without counting rows, and the shadow could not do
  it alone: it is diffuse and lands on the lane body's `--clay-deep`, which is nearly
  the card's own `--clay`. The edge closes the card and the shadow only lifts it. It
  costs **no height** — the action is `box-sizing: border-box` throughout — and the one
  gap that separates a customer from the next, `.rp-lane-body`'s, is `8px` so that edge
  has room to read. That gap is still the first place to take height back from if the
  lane ever needs it (see the density rule above); the border is not.
- **The filter bar is a view over the payload, and it is paid once per board.**
  `state.filters` holds four controls — customer search (`partner_name` + `partner_vat`,
  case folded and diacritics stripped, so `nunez` finds `Núñez`), circuit FAC/PRE, pool
  payment method, and the lane's sort order — and `FILTER_DEFAULTS` is their neutral
  state. A control with nothing to choose between MUST NOT be drawn: the payment-method
  select renders only while `canFilterMethod` (more than one `document_type` in the
  pool) and is **never** rendered disabled — a dead control on screen reads as a broken
  one, and `applyBoard` clears `filters.method` against what the control offers so a
  filter never outlives its control. Every one of them reads a field
  `get_proposal_board` already ships, so a filter MUST NOT grow an RPC, a domain or a
  stored preference; filter state dies with the action, like `collapsed` and `details`.
  `.rp-filters` renders once, between the ControlPanel and `<main class="board">`, as
  one wrapping line — the lane's height is what customers are read in, so a control the
  operator sets once MUST NEVER be paid once per customer. Matching, ordering and
  option-building live in the helpers as pure functions; no template expression filters.
- **Filters hide, they never disable.** A hidden circuit card stops being a drop zone
  because it is off screen, and that is the operator's own explicit choice, reverted
  from the same control: nothing auto-reveals on `dragstart`, no mutation clears a
  filter, `Escape` keeps meaning "close the overlays, then every expanded circuit", and
  no RPC argument changes. The one exception is pruning — `applyBoard` clears
  `filters.method` when that `document_type` has left the pool, the same way it prunes
  `collapsed` and `openSplits`; search, circuit and sort survive every refresh.
- **The circuit filter is the ONLY sanctioned way a circuit card is hidden.**
  `visibleCircuitKeys` narrows the customer card's loop; `hasCircuit` still decides only
  the `.rp-circ.empty` strip, and an empty circuit still renders when its circuit is
  visible. The circuit filter narrows cards, never the lane: a customer with no movement
  on the filtered circuit stays listed.
- **Figures follow the filter, and the sheet's own figure rides beside them.**
  `laneTotals` sums `visibleColumns` over `visibleCircuitKeys`, `poolTotal` sums
  `visiblePool`, and while `hasFilters` each shows the unfiltered figure as a muted
  `de <total>` (`sheetTotals` / `sheetPoolTotal`, in `fmtShort`) — the idiom a partly
  assigned pool card already uses. Both counts read `N de M`. The **pool's assignment
  chip is exempt**: `Requiere asignación` / `Todo asignado` stays keyed on the
  unfiltered `pool.length`, because a method filter that emptied the column MUST NOT
  claim the planilla is finished. The lane header still carries exactly the
  Cobrado/Deuda pair on one wrapping line. `tests/test_receipt_proposal_ui.py` pins all
  of this.
- **Sorting copies before it sorts.** `state.board.columns` is the server's answer and
  the board is re-read against it on every refresh, so `sortColumns` returns a new array
  — an in-place `sort()` would rewrite the order `name`, the default, exists to restore.
  `debt` / `collected` / `pending` order descending on the sum over the **visible**
  circuits of `total` / `collected` / `available`.
- **A circuit card's voucher rows are ordered by payment type, and by nothing else.**
  Every row inside a Facturas card is `document_kind == "invoice"` by construction — the
  circuit _is_ the card — so the only kind that varies row to row is the voucher's own
  `document_type`, which is what the operator has in hand while reconciling: the cheques
  together, the transferencias together. `sortCardsByType` keys on the translated
  `method` label, the same key `methodOptions` sorts the method select by, so the card
  and the filter name the types in one order; the raw code is an arbitrary catalogue
  order (`DOCUMENT_TYPE_SELECTION`) and orders nothing a reader recognises. Like
  `sortColumns` it sorts a **copy** — `column.cards` is the server's answer and the
  board is re-read against it on every refresh — and on **one** criterion only, so JS's
  stable sort preserves the payload's `value_id` order inside a type and a row the
  operator did not touch never moves on a refresh. `circuitCards` is the single place it
  is applied, so the count, the rows and `hasValues` can never disagree.
- **A circuit card MUST render even when empty**, collapsed to a strip by
  `.rp-circ.empty`: it is the drop target that creates that circuit's first receipt
  value, so hiding it would make the circuit unreachable. `hasCircuit` decides the
  strip, never whether the card exists.
- **A drop zone is the pool column or one (customer, circuit) pair**, keyed
  `` `${allocation_id}:${kind}` ``. Dropping onto FAC or PRE is what answers the circuit
  question, so `openTransfer` receives the `kind` and **the transfer modal MUST NOT ask
  for it again** — there is no circuit picker and no `setTransferKind` on that modal,
  only the `tstrip` showing where the value is going. The gesture already said it;
  re-asking made the operator answer twice and let them contradict the card they aimed
  at. The picker lives on the **Cambiar circuito** modal (`openCircuit`), which is the
  entry point that genuinely has no target circuit. Two circuits of the same customer
  therefore highlight independently, and dropping a value back onto the circuit it
  already sits in is ignored in `onZoneDrop` rather than opening a modal whose only live
  button is Cancelar — `transferIsNoop` stays as the guard behind it.
- **A drag scrolls the board itself — HTML5 drag and drop scrolls nothing.** While a
  value is in the air the pointer is tracked in a **capture-phase** `dragover` on
  `document` (the drop zones stop propagation on the way up, so a bubbling listener
  would go deaf exactly over the cards) and the scrolling runs on its own
  `requestAnimationFrame`: `dragover` stops firing the moment the pointer holds still
  against an edge, which is when the operator is waiting for the list to keep running.
  `autoscrollDelta` is pure geometry over a rect — one signed step per axis, so the foot
  of the screen scrolls down and the header scrolls up out of the same calculation, with
  the band capped at half the axis and a pointer outside the container counted as pinned
  to its edge. The element that moves is the nearest ancestor under the pointer whose
  computed `overflow` on that axis is `auto` or `scroll` and that **actually moves**:
  the board is full of `overflow: hidden` cards that still accept a written `scrollTop`,
  and a lane that has hit bottom must hand the gesture to the board instead of eating
  it. Every end of a drag — `dragend`, a drop, unmount — tears the listener and the
  frame down. `tests/test_receipt_proposal_ui.py` pins all three.
- **The expanded circuit's imputation grid is rebuilt from the payload, never merged.**
  `syncDetail` runs on every `applyBoard`, because every mutation redistributes the
  circuit by FIFO and the server is the only truth for the result. A row carries both
  `raw` (what the operator typed) and `applied` (the parsed figure).
- **Typed amounts are parsed by locale, never guessed.** `amount_parser.esm.js` (no
  imports) takes the decimal point and thousands separator, and the component passes
  Odoo's `localization` at every call site. A thousands separator is accepted only in
  groups of exactly three digits and never after a leading zero group (`0.500` is not
  500); a lone separator before a group that is not three digits is the decimal point;
  with both `.` and `,` the last one is the decimal point; anything ambiguous, malformed
  or in exponent notation is `NaN`. `rawAmount` seeds inputs in the user's decimal point
  and positional notation, so every seed reads back unchanged.
  `tests/amount_parser_test.js` runs in Node from
  `tests/test_receipt_proposal_amount_parser.py`, which fails when Node is missing.
- **Every change to a (customer, circuit) pair's collected total triggers a full FIFO
  redistribution of that circuit**, discarding manual `Imputar` edits. Idempotent by
  design: the result depends only on the current `receipt.total_values`, the documents'
  `due_date` and their `invoice_balance`. A `proposal_closed` allocation is frozen —
  `_proposal_recompute` returns `None` and writes nothing.
- **Cross-customer voucher splits are allowed within one sheet.** Same-sheet
  `_check_same_allocation` and the sheet-wide `_check_voucher_split_cap` now live in
  core `collection` (`collection.receipt.value`). This addon MUST NOT re-override those
  constraints. Largest-share owner and partner-identity relax stay here. Core
  `total_vouchers` counts each customer's collected money through its receipt values, so
  the owner pointer below no longer decides what Close and the Planilla see.
- **`voucher.allocation_id` names the largest assigned share**, including another
  customer on the same sheet. `_check_voucher_allocation_partner` and
  `_check_voucher_partners` still refuse a mismatch unless the voucher has a receipt
  value on that allocation and both records share a sheet. Cross-sheet pointers and
  naming another customer's allocation without a share there stay refused.
  `_proposal_sync_voucher_owner` implements the overall-largest pointer. Replaced cash
  with no remaining values MUST keep that pointer. `seller_deposit` MUST NOT receive
  `allocation_id` from owner sync.
- **Free amount.** `proposal_free_amount` is `amount − assigned − replaced_amount`
  (`depends` includes `replaced_amount`). Free `<=` 0 stays off the unassigned pool.
  `seller_deposit` remittance is a pool card like any other and may be dropped on a
  circuit, but owner sync never gives it an `allocation_id`. The pool column and the
  Close confirmation share one predicate, `_proposal_pool_vouchers`.
- **Board row locks.** Every board mutation (transfer, assign, split, merge, impute,
  reset, customer close/reopen) locks the vouchers whose money moves and the customer
  columns it redistributes, in id order (vouchers first), then runs a no-op
  `UPDATE ... SET write_date = write_date` and drops the ORM cache. Under REPEATABLE
  READ a concurrent operator then gets a serialization failure, Odoo retries on fresh
  data, and the plan refuses the move with its normal error instead of over-assigning a
  voucher. A read before the lock only picks the rows to lock; every check runs on what
  is re-read after it.
- **Retention certificates stay with their customer (D6).** A `retention_certificate`
  moves only between its own customer's invoice and quotation circuits: transfers (from
  the pool or a card, whole or partial), their previews and merges refuse the pool and
  any other customer with a `UserError` naming the customer, and the board reset leaves
  it where it is. The UI may still offer such a drop target; the server refuses it.
- **`collection.receipt` totals carry an explicit `depends` in core.** Field-level
  `depends=` on `total_values` / `total_applied` / `amount_on_account` lives on
  `collection.receipt` in the `collection` addon (routed through stored
  `allocation_id.line_ids`, not the non-stored `line_ids` Many2many). Do not re-add a
  satellite `models/collection_receipt.py` override.
- **Order of writes inside a mutation: shrink the source, then grow the destination.**
  Growing first would trip the sheet-wide split cap on a transient over-total. For the
  same reason the FIFO recompute and the manual impute write the documents whose
  `amount_applied` falls before the ones that rise: core refuses a line write that
  raises a receipt's applications above its values.
- **Every RPC re-validates server-side on every call** via `_require_proposal_sheet`
  (int, exists, `state == 'proposal'`, accessible) plus `_proposal_allocation` /
  `_proposal_value` / `_proposal_voucher` / `_proposal_kind` / `_proposal_amount`.
  Accept only the single number the user typed; recompute everything else server-side.
  Every mutating method returns the **full refreshed board payload**.
- **Previews run in Python** (`preview_proposal_*`) so FIFO has exactly one
  implementation. Do not port `fifoPlan` to JS. The JS debounces the transfer-amount
  input ~250 ms.
- **The customer Drawer stays the home of history and close/reopen.** The expanded
  circuit answers "what does this circuit owe?"; the drawer answers "is this customer
  done?". Do not merge them. The detail is deliberately inline rather than in the
  drawer: the drawer overlays the board, and an operator has to be able to drag a
  voucher from the pool onto the circuit they are reading.
- **The board is reachable only from a `proposal`-state sheet**, via the header button,
  and only for Collections Users (the button, the Exportar Asignaciones button and every
  RPC; a plain internal user gets `AccessError`). The button sits **after**
  `action_open_document_review` and **before** `action_print_xlsx` —
  `collection/AGENTS.md` requires `action_print_xlsx` remain the last object button
  before `<field name="state">`.
- **The client action carries no `path`.** `ir_act_client_path_unique` is a real UNIQUE
  constraint and `collection.action_collection_document_review` already occupies the
  empty string, so this action must omit the field (NULL) rather than write `''`.
- **Events are immutable.** `create` only inside the `collection_receipt_proposal_event`
  privileged scope (`collection_common.privileged`, a contextvar), which only
  `collection.receipt.proposal.event._proposal_log` opens; it sets `user_id` and
  `event_date` itself and drops the caller's `default_*` context keys, so no caller can
  pick the author or the date. A context key of that name has no effect. `write` raises,
  `unlink` raises unless the sheet cascade is unlinking (`collection_sheet_unlinking`
  scope).
- **Customer close fields are board-only.** `proposal_closed`, `proposal_note`,
  `proposal_closed_uid` and `proposal_closed_date` are writable and creatable only
  inside the board's close/reopen scope (`collection_receipt_proposal_close`), so a
  direct write cannot skip the note rule or the event log. They are `copy=False`.
- **Close warns about an unfinished board (D7, warn only).** The sheet form's Close
  button sets a context key that opts in to the check: after core's manager check and
  over-applied gate, a board that still holds pool money or customers not closed opens
  the manager-only `collection.sheet.close.confirm` dialog (pool amount, voucher count,
  open customers; **Close Anyway** / **Back to the Sheet**). A finished board closes
  directly. It is a UX step, not a guard: raw state writes, scripts and other modules
  close exactly as core does.
- **The Asignaciones workbook writes text as text.** It is created with `collection`'s
  `WORKBOOK_OPTIONS` (`strings_to_formulas` and `strings_to_urls` off); intentional
  formulas go through `write_formula`. Its membrete follows the Planilla: report name
  and sheet reference, no company header and no printed date.
- **Never `sudo()`. No new groups.** Access is core's Collections User (board, events,
  buttons) and Collections Manager (close confirmation), plus the multi-company
  `ir.rule` on events.
- **Copy convention:** view/model strings in English, OWL template copy in Spanish —
  same as `document_review`. `i18n/es_AR.po` translates the English strings; the Spanish
  template copy stays as written. Re-export `i18n/collection_receipt_proposal.pot` from
  a fresh install (`odoo i18n export -d <db> -o <file>.pot collection_receipt_proposal`)
  when strings change.
- **Odoo 19 idioms:** `models.Constraint` (not `_sql_constraints`), `<list>` (not
  `<tree>`), `@api.private`, `t-out`, `*.esm.js`.

## Skills to load before work

1. Always load **`odoo-19`**:
   `/home/crisd/projects/seedian/seedian/.agents/skills/odoo-19/SKILL.md`
2. Pick the matching guide under `.agents/skills/odoo-19/references/`.

## Setup commands

Run from the **Seedian repo root** (`seedian/`), not from this module directory:

```bash
invoke install -m collection_receipt_proposal
```

## Testing instructions

On an already-installed devel DB, default `mode=init` reports **0 tests**. Use update
mode, and re-run the base suite too — same-sheet splits and the sheet-wide cap now live
in core `collection`:

```bash
invoke test -m collection_receipt_proposal --mode=update
invoke test -m collection --mode=update
```

| File                                           | Focus                                                                                                                                                       |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_receipt_proposal_fifo.py`          | plan / preview / recompute; idempotency; `invoice_balance` ceiling; undated last; surplus; no documents; closed frozen; overdraft self-heals; status ladder |
| `tests/test_receipt_proposal_order.py`         | `_proposal_fifo_key` == `_compute_line_ids` order, including both fallbacks                                                                                 |
| `tests/test_receipt_proposal_split.py`         | cross-customer split accepted in-sheet, rejected across sheets; sheet-wide cap; unify; undo; owner re-pointing; remittance/replaced-cash lock               |
| `tests/test_receipt_proposal_board.py`         | payload shape; `_require_proposal_sheet` rejections; Collections User ACL; replaced cash off the pool                                                       |
| `tests/test_receipt_proposal_actions.py`       | transfer / set_circuit / impute / close / reopen and the event each writes; remittance is a pool card but never an owner                                    |
| `tests/test_receipt_proposal_events.py`        | gated create; write/unlink refuse except sheet cascade; newest-first; Collections User ACL `1,0,1,0`; live company `ir.rule`; no `sudo()`/groups            |
| `tests/test_receipt_proposal_privileged.py`    | forged context keys cannot create events or write the close fields                                                                                          |
| `tests/test_receipt_proposal_concurrency.py`   | each mutation locks its rows before the first write; stale free amounts are re-read and refused                                                             |
| `tests/test_receipt_proposal_retention.py`     | retention certificates stay on their customer                                                                                                               |
| `tests/test_receipt_proposal_close_confirm.py` | the D7 Close confirmation and who sees it                                                                                                                   |
| `tests/test_receipt_proposal_split_close.py`   | a board that splits money across customers closes and prints per-share                                                                                      |
| `tests/test_receipt_proposal_amount_parser.py` | runs `tests/amount_parser_test.js` in Node                                                                                                                  |
| `tests/test_receipt_proposal_ui.py`            | static-text assertions on the JS/SCSS/XML; inherited form arch                                                                                              |

`tests/common.py` replicates `collection`'s receipt fixtures rather than subclassing
`TestCollectionReceipt` — subclassing would re-run that whole suite. It also carries
partner, user, and company helpers that tolerate `account`'s NOT NULL DB columns
outliving its fields in the registry this module's tests load into. Company create
copies leftover `res_company` columns from `env.company` (same SQL pattern as
`collection` report/binding tests). `tests/test_receipt_proposal_events.py` exercises
the live company `ir.rule` hide path with that helper.

Strict TDD is enabled in `openspec/config.yaml`. Add or update tests in the same change
as behavior.

Lint: this repository has its own hooks (`.pre-commit-config.yaml`, mirroring the
parent's). From this repository's root:

```bash
pre-commit run --all-files
```

## Code style

- Two-line `# Copyright 2026 Seedian` / `# License AGPL-3.0 or later` header on every
  `.py`.
- Follow this repository's pre-commit: Ruff, pylint-odoo, ESLint, Prettier, OCA checks.
  ESLint enforces `sort-imports` and `no-use-before-define` on the OWL files.
- Do not hand-edit generated `README.rst`; update `readme/` fragments and regenerate.
- Commit messages: Conventional Commits, `<type>(collection_receipt_proposal): …`.

## Known follow-ups

1. Settled: core `allocation.total_vouchers` now sums receipt values (plus vouchers
   whose money never reached a receipt), so a split voucher counts per share in Close
   and the Planilla (`tests/test_receipt_proposal_split_close.py`).
2. `document_numbers` is stored and depends on `line_ids.amount_applied`, so every board
   mutation triggers a stored recompute of the affected receipts. Functionally
   desirable, but real write amplification on a large sheet — worth a query-count
   assertion if boards get big.
3. `_compute_document_numbers`'s `@api.depends` omits `allocation_id.line_ids.due_date`
   while the order it renders comes from `line_ids`, which _is_ due-date sorted.
   Changing a line's `due_date` therefore leaves the stored string in a stale order.
   Accepted: the board never changes `due_date`; only a connector re-snapshot does.
4. Concurrency — settled by the board row locks (see Domain rules). There is no true
   two-transaction test yet; the tests pin the lock order and the re-read refusal.
5. Same-sheet receipt-value boundary, the sheet-wide split cap, and receipt-total
   `depends=` now live in core `collection`. Do not re-introduce satellite constraint or
   `collection.receipt` field overrides for those invariants.
