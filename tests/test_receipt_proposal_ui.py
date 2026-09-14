# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re
from pathlib import Path

from lxml import etree

from odoo.tests import TransactionCase

_ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "src" / "receipt_proposal"


class TestReceiptProposalUi(TransactionCase):
    """RED/GREEN: OWL assets on disk and the inherited sheet form arch."""

    def _asset(self, filename):
        return (_ASSET_DIR / filename).read_text(encoding="utf-8")

    def test_asset_files_exist(self):
        """RED/GREEN: the four house-template asset files ship together."""
        for filename in (
            "receipt_proposal_action.esm.js",
            "receipt_proposal_helpers.esm.js",
            "receipt_proposal_action.xml",
            "receipt_proposal_action.scss",
        ):
            self.assertTrue((_ASSET_DIR / filename).is_file(), f"{filename} must exist")

    def test_client_action_is_registered_under_the_module_tag(self):
        """RED/GREEN: the OWL component registers the action tag."""
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn('registry\n  .category("actions")', source)
        self.assertIn(
            '"collection_receipt_proposal.receipt_proposal"',
            source,
        )
        self.assertIn(
            'static template = "collection_receipt_proposal.ReceiptProposalAction"',
            source,
        )
        self.assertIn("standardActionServiceProps", source)

    def test_component_uses_orm_and_notification_services(self):
        """RED/GREEN: the board talks to the server through the ORM service."""
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn('useService("orm")', source)
        self.assertIn('useService("notification")', source)
        for method in (
            "get_proposal_board",
            "action_proposal_transfer",
            "action_proposal_set_circuit",
            "action_proposal_undo_split",
            "action_proposal_impute",
            "action_proposal_close_customer",
            "action_proposal_reopen_customer",
            "preview_proposal_transfer",
            "preview_proposal_circuit",
            "preview_proposal_undo_split",
            "preview_proposal_impute",
        ):
            self.assertIn(method, source, f"{method} must be reachable from the board")

    def test_helpers_stay_free_of_odoo_imports_beyond_translation(self):
        """RED/GREEN: the helpers file imports only `_t`."""
        source = self._asset("receipt_proposal_helpers.esm.js")
        imports = [line for line in source.splitlines() if line.startswith("import ")]
        self.assertEqual(len(imports), 1)
        self.assertIn("@web/core/l10n/translation", imports[0])

    def test_helpers_export_the_documented_surface(self):
        """RED/GREEN: the pure helper surface the component relies on."""
        source = self._asset("receipt_proposal_helpers.esm.js")
        for symbol in (
            "export const CIRCUITS",
            "export function formatAmount",
            "export function splitKind",
            "export function cardClass",
            "export function statusLabel",
            "export function validateTransferAmount",
            "export function transferButtonLabel",
            "export function sanitizeBoardPayload",
            "export function nextIsolate",
            "export function glyphOf",
        ):
            self.assertIn(symbol, source, f"{symbol} must be exported")

    def test_helpers_implement_the_documented_pure_logic(self):
        """RED/GREEN: helper bodies stay regex-asserted; only `_t` for copy."""
        source = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn('new Intl.NumberFormat("es-AR"', source)
        self.assertIn('tag: "FAC"', source)
        self.assertIn('tag: "PRE"', source)
        self.assertIn('key: "invoice"', source)
        self.assertIn('key: "quotation"', source)
        self.assertIn('return columns.size > 1 ? "clientes" : "circuito"', source)
        self.assertIn("return current === voucherId ? null : voucherId", source)
        self.assertIn("export const PREVIEW_DEBOUNCE_MS = 250", source)
        self.assertIn('_t("El importe debe ser mayor que cero.")', source)
        self.assertIn('_t("El importe supera el máximo disponible.")', source)
        self.assertIn('_t("Devolver a Sin asignar")', source)
        self.assertIn('_t("Reunificar")', source)
        self.assertIn('_t("Transferir parte")', source)
        self.assertIn('_t("Transferir todo")', source)
        self.assertIn("STATUS_LABELS[status] || STATUS_LABELS.sin_iniciar", source)
        self.assertIn('return circuit ? circuit.cls : "c-none"', source)
        self.assertNotIn("useService", source)
        self.assertNotIn("@odoo/owl", source)
        self.assertNotIn("orm.call", source)

    def test_preview_debounce_is_250ms(self):
        """RED/GREEN: transfer preview waits 250 ms before the RPC."""
        action = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("PREVIEW_DEBOUNCE_MS", action)
        self.assertIn("window.setTimeout(callback, PREVIEW_DEBOUNCE_MS)", action)
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn("export const PREVIEW_DEBOUNCE_MS = 250", helpers)

    def test_templates_declare_every_board_surface(self):
        """RED/GREEN: pool, lane, customer/circuit cards, detail and overlays.

        The imputation grid is revealed inside the circuit card it belongs to,
        so there is no `ImputeModal` and no third column; a voucher applied to a
        circuit is a `VoucherRow` rather than a full `Card`.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        names = {node.get("t-name") for node in root.xpath("//t[@t-name]")}
        self.assertEqual(
            {
                "collection_receipt_proposal.ReceiptProposalAction",
                "collection_receipt_proposal.PoolColumn",
                "collection_receipt_proposal.CustomerLane",
                "collection_receipt_proposal.CustomerCard",
                "collection_receipt_proposal.FilterBar",
                "collection_receipt_proposal.CircuitCard",
                "collection_receipt_proposal.CircuitDetail",
                "collection_receipt_proposal.VoucherRow",
                "collection_receipt_proposal.TypeGlyph",
                "collection_receipt_proposal.ContextMenu",
                "collection_receipt_proposal.PreviewPanel",
                "collection_receipt_proposal.TransferModal",
                "collection_receipt_proposal.CircuitModal",
                "collection_receipt_proposal.UndoSplitModal",
                "collection_receipt_proposal.CloseModal",
                "collection_receipt_proposal.Drawer",
            },
            names,
        )

    def test_payment_type_is_read_by_shape_not_by_colour(self):
        """RED/GREEN: one glyph per `document_type`, monochrome and engraved.

        Colour on this board already means circuit -- `--c` / `--c-tint` paint
        the rail and tint of every card -- and that is the distinction which
        constrains imputation. So the payment type gets the shape channel: a
        `.pay-glyph` chip in the `.tag` family (`--clay-deep` + `--inset-sm`),
        with no hue of its own.
        """
        template = self._asset("receipt_proposal_action.xml")
        root = etree.fromstring(template.encode())
        glyph = root.xpath("//t[@t-name='collection_receipt_proposal.TypeGlyph']")[0]
        chip = glyph.xpath(".//span[@class='pay-glyph']")
        self.assertEqual(len(chip), 1)
        self.assertEqual(chip[0].get("aria-hidden"), "true")
        branches = [
            node.get("t-if") or node.get("t-elif")
            for node in glyph.xpath(".//t[@t-if or @t-elif]")
        ]
        self.assertEqual(
            [re.search(r"'(\w+)'", branch).group(1) for branch in branches],
            [
                "bank_transfer",
                "check",
                "echeck",
                "cash",
                "cash_deposit",
                "seller_deposit",
                "retention_certificate",
            ],
        )
        self.assertEqual(len(glyph.xpath(".//t[@t-else]")), 1)
        scss = self._asset("receipt_proposal_action.scss")
        chip_rule = re.search(r"\.pay-glyph \{(.+?)\n  \}", scss, re.S).group(1)
        self.assertIn("background: var(--clay-deep)", chip_rule)
        self.assertIn("color: var(--ink-2)", chip_rule)
        self.assertIn("box-shadow: var(--inset-sm)", chip_rule)
        for token in ("--fac", "--pre", "--ok", "--warn", "--bad", "--favor"):
            self.assertNotIn(token, chip_rule, f"{token} would re-colour the glyph")

    def test_the_glyph_costs_the_lane_no_height(self):
        """RED/GREEN: the chip rides inside `.pay-method`, which is 18px tall.

        The density rule says a card's height is spent on figures, never on
        chrome. A row's text is 12.5px, so an 18px chip fits the line the row
        already draws -- but only while it sits in the flex label rather than
        on a line of its own.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        calls = root.xpath("//t[@t-call='collection_receipt_proposal.TypeGlyph']")
        self.assertEqual(len(calls), 2, "the pool card and the assigned row")
        for call in calls:
            self.assertEqual(call.getparent().get("class"), "pay-method")
            self.assertEqual(
                call.xpath("./t[@t-set='glyph']")[0].get("t-value"),
                {
                    "collection_receipt_proposal.PoolColumn": (
                        "glyphOf(item.document_type)"
                    ),
                    "collection_receipt_proposal.VoucherRow": (
                        "glyphOf(card.document_type)"
                    ),
                }[call.xpath("ancestor::t[@t-name]")[0].get("t-name")],
            )
        scss = self._asset("receipt_proposal_action.scss")
        chip_rule = re.search(r"\.pay-glyph \{(.+?)\n  \}", scss, re.S).group(1)
        self.assertIn("height: 18px", chip_rule)
        self.assertIn("flex: none", chip_rule)

    def test_board_is_the_pool_and_the_customer_lane(self):
        """RED/GREEN: two columns, so the lane keeps the width it needs.

        The debt detail is revealed inside its own circuit card, not in a third
        column: a column would spend ~420px re-stating the customer and the
        circuit that the card beside it already names.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        board = root.xpath('//main[@class="board"]')
        self.assertEqual(len(board), 1)
        calls = [node.get("t-call") for node in board[0].xpath(".//t[@t-call]")]
        self.assertEqual(
            calls,
            [
                "collection_receipt_proposal.PoolColumn",
                "collection_receipt_proposal.CustomerLane",
            ],
        )
        self.assertNotIn(".rp-col.detail", self._asset("receipt_proposal_action.scss"))

    def test_customer_card_holds_one_card_per_circuit(self):
        """RED/GREEN: both circuits render inside the customer card.

        An empty circuit MUST still render — collapsed to a strip by
        `.rp-circ.empty` — because it is the drop target that creates the
        circuit's first receipt value. The loop runs over `visibleCircuitKeys`,
        which is `CIRCUIT_KEYS` unless the operator has set the circuit filter:
        the filter is the one sanctioned way a circuit card is hidden, and the
        same control puts it back.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        card = root.xpath('//t[@t-name="collection_receipt_proposal.CustomerCard"]')[0]
        loops = card.xpath('.//t[@t-foreach="visibleCircuitKeys"]')
        self.assertEqual(len(loops), 1)
        self.assertEqual(
            [node.get("t-call") for node in loops[0].xpath("./t[@t-call]")],
            ["collection_receipt_proposal.CircuitCard"],
        )
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitCard"]')[
            0
        ]
        self.assertIn("'empty'", circuit[0].get("t-attf-class"))

    def test_circuit_detail_carries_the_imputation_grid(self):
        """RED/GREEN: the expanded circuit edits the imputation, not a modal."""
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        detail = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitDetail"]')[
            0
        ]
        inputs = detail.xpath('.//input[starts-with(@t-attf-class, "imp num")]')
        self.assertEqual(len(inputs), 1)
        self.assertIn("onImputeInput(ev, row)", inputs[0].get("t-on-input"))
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertNotIn("openImpute", source)
        self.assertIn("openDetail(allocationId, kind)", source)
        self.assertIn("closeDetail(allocationId, kind)", source)

    def test_a_collapsed_card_pays_for_no_action_row(self):
        """RED/GREEN: the footer only exists expanded; the toggle is in the head.

        `Distribuir` / `Confirmar` still share one footer — a separate actions
        row inside the detail left the toggle alone on a further row. But that
        footer is 36px of chrome that every circuit in the lane used to pay for
        just to carry `Ver detalle`, so the toggle moved onto the header line
        the card already draws and the footer renders only while expanded.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitCard"]')[
            0
        ]
        foots = circuit.xpath('.//div[@class="rp-circ-foot"]')
        self.assertEqual(len(foots), 1)
        self.assertIn("isDetailOpen(column.allocation_id, kind)", foots[0].get("t-if"))
        clicks = [node.get("t-on-click") for node in foots[0].xpath(".//button")]
        self.assertEqual(len(clicks), 2)
        self.assertIn("autoDistribute", clicks)
        self.assertIn("confirmImpute", clicks)
        head = circuit.xpath('.//div[@class="rp-circ-head"]')[0]
        toggles = head.xpath('.//button[@class="rp-circ-toggle"]')
        self.assertEqual(len(toggles), 1)
        self.assertIn(
            "toggleDetail(column.allocation_id, kind)", toggles[0].get("t-on-click")
        )
        self.assertTrue(toggles[0].get("t-att-aria-expanded"))
        detail = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitDetail"]')[
            0
        ]
        self.assertFalse(detail.xpath(".//button"))
        self.assertNotIn("rp-circ-actions", self._asset("receipt_proposal_action.scss"))

    def test_the_figures_line_lives_in_the_header_and_goes_live(self):
        """RED/GREEN: one figures line, in the header, live while expanded.

        The figures used to own a row under the header, and the detail added a
        second row restating them — two rows of chrome for the same four
        numbers, while the header's own middle sat empty on a card that can be
        1400px wide. `circuitFigures` returns the payload's figures normally
        and the ones the operator's inputs are producing while expanded, so the
        header alone can carry both jobs.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitCard"]')[
            0
        ]
        head = circuit.xpath('.//div[@class="rp-circ-head"]')
        self.assertEqual(len(head), 1)
        self.assertEqual(len(head[0].xpath('./t/div[@class="rp-circ-nums"]')), 1)
        self.assertEqual(len(circuit.xpath('.//div[@class="rp-circ-nums"]')), 1)

        xml = self._asset("receipt_proposal_action.xml")
        self.assertNotIn("rp-circ-live", xml)
        self.assertNotIn("rp-circ-detail-top", xml)
        detail = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitDetail"]')[
            0
        ]
        self.assertFalse(detail.xpath('.//div[@class="section-title"]'))

        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("circuitFigures(column, kind) {", source)
        self.assertIn(
            "const detail = this.detailOf(column.allocation_id, kind);"
            "\n    if (!detail) {"
            "\n      return figures;",
            source,
        )
        self.assertIn("available: figures.collected - applied,", source)
        self.assertIn("pending: this.imputePending(detail),", source)

        scss = self._asset("receipt_proposal_action.scss")
        self.assertNotIn(".rp-circ-live", scss)
        self.assertNotIn(".rp-circ-detail-top", scss)
        nums = scss.split("\n  .rp-circ-nums {", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn("justify-content: space-between", nums)
        self.assertNotIn("flex-direction: column", nums)
        head_block = scss.split("\n  .rp-circ-head {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("flex-wrap: wrap", head_block)
        detail_block = scss.split("\n  .rp-circ-detail {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("max-width: 900px", detail_block)

    def test_the_detail_grid_stays_one_line_per_document(self):
        """RED/GREEN: every fact owns a column, so a row never stacks lines.

        A stacked number + dates cell costs ~56px per document inside a card
        already nested two levels deep. Six single-line columns cost ~30px and
        give each fact its own gap instead of crowding them into one cell.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        detail = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitDetail"]')[
            0
        ]
        self.assertEqual(len(detail.xpath(".//thead//th")), 6)
        rows = detail.xpath('.//tbody/tr[@t-foreach="detail.rows"]')
        self.assertEqual(len(rows), 1)
        cells = rows[0].xpath("./td")
        self.assertEqual(len(cells), 6)
        for cell in cells:
            self.assertLessEqual(
                len(cell.xpath("./div")) + len(cell.xpath("./span")),
                1,
                "a detail cell must hold at most one line of content",
            )
        empty = detail.xpath(".//tbody/tr[@t-if]/td")[0]
        self.assertEqual(empty.get("colspan"), "6")

    def test_the_detail_grid_is_dense_and_never_scrolls_sideways(self):
        """RED/GREEN: the card gives back height, and never gains width.

        The grid lives in one half of the customer card, so it is fitted to the
        card rather than scrolled inside it: a fixed layout hands each column a
        share of the width there is, and only the debt list scrolls, under a
        sticky header. Reading an imputation means comparing Saldo against
        Imputado, and a horizontal scrollbar puts those on two screens.
        """
        scss = self._asset("receipt_proposal_action.scss")
        block = scss.split("\n  .rp-circ-detail {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("padding: 6px 4px", block)
        self.assertIn("white-space: nowrap", block)
        self.assertIn("table-layout: fixed", block)
        self.assertIn("container-type: inline-size", block)
        self.assertNotIn("width: max-content", block)
        self.assertIn("max-height: 38vh", block)
        self.assertIn("overflow-y: auto", block)
        self.assertIn("overflow-x: hidden", block)
        self.assertIn("position: sticky", block)
        shared = scss.split("\n  td {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("padding: 11px 13px", shared)

    def test_the_detail_grid_drops_a_column_before_it_cuts_a_figure(self):
        """RED/GREEN: what gives when the card is too narrow, in order.

        The column shares add up to 100 at every step, so the row exactly fills
        the card. When even that is not enough the card drops Emitida, then
        Importe — both derivable, both still on the row's tooltips — rather
        than clip a date or a figure. The document number is the one cell
        allowed to reflow: its tail is what identifies it, so it wraps instead
        of ending in an ellipsis.
        """
        scss = self._asset("receipt_proposal_action.scss")
        block = scss.split("\n  .rp-circ-detail {", 1)[1].split("\n  }\n", 1)[0]
        steps = block.split("@container")
        self.assertEqual(
            [step.split("{", 1)[0].strip() for step in steps[1:]],
            ["(max-width: 480px)", "(max-width: 400px)", "(max-width: 320px)"],
        )
        # Emitida goes first, then Importe — and nothing else is ever hidden.
        self.assertEqual(
            re.findall(r"th:nth-child\((\d)\),\s+td:nth-child\(\d\)", block),
            ["3", "4"],
        )
        hidden = set()
        for step in steps:
            hidden |= {
                int(column)
                for column in re.findall(
                    r"th:nth-child\((\d)\),\s+td:nth-child\(\d\) \{\s+display: none",
                    step,
                )
            }
            shares = 0.0
            for selectors, width in re.findall(
                r"((?:th:nth-child\(\d\),\s+)*th:nth-child\(\d\)) \{\s+"
                r"width: ([\d.]+)%;",
                step,
            ):
                shares += float(width) * selectors.count("th:nth-child")
            if not shares:
                continue
            self.assertEqual(round(shares, 2), 100.0, "the shares must fill the card")
        self.assertEqual(hidden, {3, 4})
        doc = block.split("\n    td .doc {", 1)[1].split("\n    }", 1)[0]
        self.assertIn("white-space: normal", doc)
        self.assertIn("overflow-wrap: anywhere", doc)

    def test_expanding_a_circuit_never_changes_the_card_width(self):
        """RED/GREEN: the expanded circuit keeps its grid track and grows down.

        Spanning both tracks doubled the card's width and shoved the other
        circuit to a row of its own, so opening a grid re-laid out the customer
        under the pointer. Height is the only axis that moves.
        """
        scss = self._asset("receipt_proposal_action.scss")
        expanded = scss.split("\n  .rp-circ.expanded {", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn("grid-column", expanded)
        body = scss.split("\n  .rp-cust-body {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("repeat(2, minmax(0, 1fr))", body)
        self.assertIn("align-items: start", body)

    def test_the_lane_card_spends_its_height_on_data_not_chrome(self):
        """RED/GREEN: the density the lane is read at, pinned.

        Fitting more customers at a glance came from deleting repeated chrome,
        never figures: the footer went away while collapsed, the CUIT joined
        the name's line, and the circuit's noun moved into the pill that was
        already there. Every number the card carried, it still carries.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitCard"]')[
            0
        ]
        head = circuit.xpath('.//div[@class="rp-circ-head"]')[0]
        self.assertEqual(len(head.xpath('.//div[@class="rp-circ-nums"]/span')), 4)
        self.assertEqual(len(head.xpath('.//span[@class="rp-circ-count"]')), 1)
        # One pill, carrying the noun the separate label used to repeat.
        pills = head.xpath('./span[starts-with(@t-attf-class, "ct ")]')
        self.assertEqual(len(pills), 1)
        self.assertEqual(pills[0].get("t-out"), "circuits[kind].Noun")
        xml = self._asset("receipt_proposal_action.xml")
        self.assertNotIn("rp-circ-lab", xml)

        scss = self._asset("receipt_proposal_action.scss")
        self.assertNotIn(".rp-circ-lab", scss)
        title = scss.split("\n  .rp-cust-title {", 1)[1].split("\n  }\n", 1)[0]
        self.assertNotIn("display: block", title)

    def test_the_lane_header_costs_one_line_not_a_block(self):
        """RED/GREEN: the customer column's header is chrome, so it is one row.

        The lane's height is what customers are read in, and the header is
        paid before the first card: stacked — title over a row of stacked
        label/number pairs — it spent about a customer card's worth of lane on
        four figures. Flattened to one wrapping line it carries the two the
        lane is summed by, Cobrado and Deuda, with the count inline beside the
        title. Imputado and Sin imputar left the header because they are
        per-circuit questions the card below already answers per circuit —
        summed over every customer and both circuits they told the operator
        nothing they act on.
        """
        scss = self._asset("receipt_proposal_action.scss")
        head = scss.split("\n  .rp-lane-head {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("flex-direction: row", head)
        self.assertNotIn("flex-direction: column", head)
        # The count rides beside the title instead of owning a line of its own.
        self.assertIn("display: inline", head)
        # Tighter than the pool column's head, which has no such pressure.
        pool_head = scss.split("\n  .rp-col-head {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("padding: 16px 16px 12px", pool_head)
        self.assertIn("padding: 10px 16px 8px", head)

        meta = scss.split("\n  .rp-lane-meta {", 1)[1].split("\n  }\n", 1)[0]
        # Figures read label-beside-number, like the circuit card's own line.
        self.assertNotIn("flex-direction: column", meta)
        self.assertNotIn("justify-content: space-between", meta)
        self.assertIn("flex-wrap: wrap", meta)

        # Two figures, and they are the collected/debt pair.
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        lane = root.xpath('//t[@t-name="collection_receipt_proposal.CustomerLane"]')[0]
        figures = lane.xpath('.//div[@class="rp-lane-meta"]/span')
        self.assertEqual(len(figures), 2)
        self.assertEqual(
            [node.xpath("./em")[0].text.strip() for node in figures],
            ["Cobrado", "Deuda"],
        )
        # The dropped pair is dropped in the component too, not just hidden,
        # and Deuda sums the documents' own balance — `total`, the figure a
        # circuit card labels Deuda — not `pending`, which nets out what is
        # already imputed and so reads $ 0 on a fully distributed board.
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("const totals = {collected: 0, total: 0};", source)
        self.assertIn("totals.total += figures.total;", source)
        self.assertNotIn("totals.pending", source)
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn("fmt(laneTotals.total)", xml)
        for dropped in (
            "laneTotals.applied",
            "laneTotals.available",
            "laneTotals.pending",
        ):
            self.assertNotIn(dropped, xml)

    def test_every_circuit_expands_on_its_own(self):
        """RED/GREEN: `state.details` is a list, and a toggle closes only its own.

        Comparing what a customer owes across two circuits — or the same
        circuit across customers — is the job, so one open grid must not shut
        another. Each expanded circuit owns its entry, keyed by allocation and
        circuit, and the imputation figures are read per entry.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("details: [],", source)
        self.assertNotIn("detail: null,", source)
        self.assertIn("toggleDetail(allocationId, kind) {", source)
        self.assertIn(
            "if (this.isDetailOpen(allocationId, kind)) {"
            "\n      this.closeDetail(allocationId, kind);",
            source,
        )
        self.assertIn("detailOf(allocationId, kind) {", source)
        self.assertIn(
            "this.state.details = [...this.state.details, detail];",
            source,
        )
        self.assertIn(
            "(detail) => detail.allocation_id !== allocationId || detail.kind !== kind",
            source,
        )
        # Escape still clears the board, and every open grid resyncs on refresh.
        self.assertIn("closeAllDetails() {\n    this.state.details = [];", source)
        self.assertIn("this.closeAllDetails();", source)
        self.assertIn("this.syncDetails();", source)
        # The template reads the grid off the card's own entry, never a
        # board-wide one.
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn(
            '<t t-set="detail" t-value="detailOf(column.allocation_id, kind)" />',
            xml,
        )
        self.assertNotIn("state.detail", xml)

    def test_imputation_row_keeps_the_typed_text_and_the_parsed_amount(self):
        """RED/GREEN: `raw` is what was typed, `applied` the parsed figure.

        `parseAmount` drops "." as a thousands mark, so re-parsing a seeded
        `String(row.applied)` would read 1000.5 back as 10005. The two fields
        therefore travel together and only user input refreshes the amount.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("raw: String(row.applied)", source)
        self.assertIn("row.raw = ev.target.value", source)
        self.assertIn("row.applied = Number.isFinite(parsed) && parsed > 0", source)
        self.assertIn("imputeRowAmount(row) {\n    return row.applied;\n  }", source)

    def test_templates_bind_html5_drag_and_drop(self):
        """RED/GREEN: cards drag and columns drop, bound with `t-on-*`."""
        source = self._asset("receipt_proposal_action.xml")
        for handler in ("t-on-dragstart", "t-on-dragend", "t-on-dragover", "t-on-drop"):
            self.assertIn(handler, source)
        self.assertIn("t-att-draggable", source)

    def test_draggable_renders_the_literal_enumerated_value(self):
        """RED/GREEN: `draggable` must resolve to the string 'true' or 'false'.

        OWL's `setAttribute` turns a boolean `true` into `draggable=""`, and
        `draggable` is an enumerated attribute, not a boolean one: the empty
        string is invalid and falls back to `auto`, which leaves an `<article>`
        undraggable. The failure is silent, hence this guard.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        nodes = root.xpath("//*[@t-att-draggable]")
        self.assertTrue(nodes, "the board must declare draggable cards")
        for node in nodes:
            self.assertIn(
                "'true' : 'false'",
                node.get("t-att-draggable"),
                "t-att-draggable must yield a literal 'true'/'false' string",
            )

    def test_a_drop_zone_is_the_pool_or_one_customer_circuit(self):
        """RED/GREEN: dropping onto FAC or PRE already answers the circuit.

        The zone key pairs the customer with the circuit, so two cards of the
        same customer highlight independently, and the whole card is the target
        rather than only the rows holding vouchers.
        """
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn("onZoneDragOver(ev, column, kind)", xml)
        self.assertIn("onZoneDragOver(ev, null, '')", xml)
        self.assertIn("onZoneDrop(ev, column, kind)", xml)
        self.assertIn("onZoneDrop(ev, null, '')", xml)
        self.assertIn("t-on-dragleave", xml)
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            'return column ? `${column.allocation_id}:${kind}` : "pool";', source
        )
        self.assertIn(
            "this.openTransfer(dragged, column ? column.allocation_id : null, kind)",
            source,
        )
        self.assertIn('kind: toAllocationId ? kind || "" : "",', source)
        scss = self._asset("receipt_proposal_action.scss")
        circuit = scss.split("\n  .rp-circ {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("display: flex", circuit)
        self.assertIn("flex-direction: column", circuit)

    def test_board_columns_fill_their_height(self):
        """RED/GREEN: the three columns stretch, so neither ends short."""
        scss = self._asset("receipt_proposal_action.scss")
        board = scss.split("\n  .board {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("align-items: stretch", board)
        self.assertNotIn("align-items: flex-start", board)
        column = scss.split("\n  .rp-col {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("height: 100%", column)
        lane = scss.split("\n  .rp-lane {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("height: 100%", lane)
        self.assertIn("flex: 3 3", lane)

    def test_board_splits_a_quarter_to_the_pool(self):
        """RED/GREEN: the pool owns 1/4 of the board, the customer lane 3/4."""
        scss = self._asset("receipt_proposal_action.scss")
        column = scss.split("\n  .rp-col {", 1)[1].split("\n  }", 1)[0]
        lane = scss.split("\n  .rp-lane {", 1)[1].split("\n  }", 1)[0]
        # `flex-basis: 0` on both sides makes the grow factors the whole ratio,
        # so the split stays 1:3 whatever the board is wide.
        self.assertIn("flex: 1 1 0", column)
        self.assertIn("flex: 3 3 0", lane)
        self.assertNotIn("width: 312px", column)
        # A min-width each, so the two still scroll rather than crush on narrow.
        self.assertIn("min-width:", column)
        self.assertIn("min-width:", lane)

    def test_collapsed_customer_card_hides_its_circuits(self):
        """RED/GREEN: collapsing a customer keeps its header row visible."""
        scss = self._asset("receipt_proposal_action.scss")
        collapsed = scss.split("\n  .rp-cust.collapsed {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn(".rp-cust-body", collapsed)
        self.assertIn("display: none", collapsed)
        self.assertIn("rotate(-90deg)", collapsed)
        self.assertNotIn("writing-mode: vertical-rl", scss)

    def test_drawer_offers_both_tabs(self):
        """RED/GREEN: the drawer carries Conciliación and Historial."""
        source = self._asset("receipt_proposal_action.xml")
        self.assertIn("Conciliación", source)
        self.assertIn("Historial", source)

    def test_owl_copy_is_spanish_and_views_are_english(self):
        """RED/GREEN: OWL template copy is Spanish; view/action strings English."""
        xml = self._asset("receipt_proposal_action.xml")
        for phrase in (
            "Cargando el tablero de conciliación",
            "Sin asignar",
            "Transferir cobro",
            "Imputar cobranza",
            "Cerrar cliente en la planilla",
            "Deshacer división",
            "Cancelar",
        ):
            self.assertIn(phrase, xml, f"OWL must show Spanish copy: {phrase}")
        self.assertNotIn("Receipt Proposal", xml)
        self.assertNotIn("Loading the board", xml)

        views = (
            Path(__file__).resolve().parents[1]
            / "views"
            / "collection_receipt_proposal_views.xml"
        ).read_text(encoding="utf-8")
        self.assertIn('string="Receipt Proposal"', views)
        self.assertIn(">Receipt Proposal<", views)
        self.assertNotIn("Propuesta de recibo", views)
        self.assertNotIn("Propuesta de Recibo", views)

        action = self.env.ref(
            "collection_receipt_proposal.action_collection_receipt_proposal"
        )
        self.assertEqual(action.name, "Receipt Proposal")

    def test_module_ships_no_i18n_directory(self):
        """RED/GREEN: Spanish copy is inline; no i18n/ PO files."""
        addon = Path(__file__).resolve().parents[1]
        self.assertFalse((addon / "i18n").exists())

    def test_owl_templates_use_t_out(self):
        """RED/GREEN: Odoo 19 OWL templates use t-out, not deprecated t-esc."""
        xml = self._asset("receipt_proposal_action.xml")
        self.assertNotIn("t-esc=", xml)
        self.assertIn("t-out=", xml)

    def test_overlays_are_portaled_to_the_body(self):
        """RED/GREEN: modals, menu and drawer render at `<body>`, not in-place.

        Inside the action container their `position: fixed` layers sit under
        the Odoo navbar (Bootstrap `$zindex-fixed: 1030`), which paints over
        the backdrop and the top of a centred modal.
        """
        xml = self._asset("receipt_proposal_action.xml")
        self.assertEqual(xml.count("t-portal=\"'body'\""), 3)
        self.assertEqual(xml.count("o_receipt_proposal_portal"), 3)
        self.assertIn(
            'class="o_collection_receipt_proposal o_receipt_proposal_portal"', xml
        )

    def test_overlay_layers_clear_the_odoo_navbar(self):
        """RED/GREEN: menu < drawer < modal, all above Bootstrap's 1030."""
        scss = self._asset("receipt_proposal_action.scss")
        layers = {}
        for name, selector in (
            ("menu", "\n  .menu {"),
            ("overlay", "\n  .overlay {"),
            ("drawer", "\n  .drawer {"),
        ):
            block = scss.split(selector, 1)[1].split("\n  }", 1)[0]
            line = next(row for row in block.splitlines() if "z-index:" in row)
            layers[name] = int(line.split(":")[1].strip().rstrip(";"))
        for name, value in layers.items():
            self.assertGreater(value, 1030, f"{name} must clear the navbar")
        self.assertLess(layers["menu"], layers["drawer"])
        self.assertLess(layers["drawer"], layers["overlay"])

    def test_portal_wrapper_paints_no_box(self):
        """RED/GREEN: the portal wrapper carries tokens but paints no box."""
        scss = self._asset("receipt_proposal_action.scss")
        block = scss.split("\n  &.o_receipt_proposal_portal {", 1)[1].split("\n  }", 1)[
            0
        ]
        self.assertIn("display: contents", block)

    def test_modal_overlay_centres_its_dialog(self):
        """RED/GREEN: the backdrop centres the modal on both axes."""
        scss = self._asset("receipt_proposal_action.scss")
        block = scss.split("\n  .overlay {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("position: fixed", block)
        self.assertIn("inset: 0", block)
        self.assertIn("align-items: center", block)
        self.assertIn("justify-content: center", block)

    def test_scss_is_scoped_to_one_root_class(self):
        """RED/GREEN: nothing leaks outside `.o_collection_receipt_proposal`."""
        source = self._asset("receipt_proposal_action.scss")
        self.assertTrue(source.startswith(".o_collection_receipt_proposal {"))
        top_level = [
            line
            for line in source.splitlines()
            if line and not line.startswith((" ", "}", "\t"))
        ]
        self.assertEqual(top_level, [".o_collection_receipt_proposal {"])

    def test_no_bootstrap_class_name_collisions(self):
        """RED/GREEN: the board must not reuse unscoped framework class names.

        Bootstrap ships `.modal {position: fixed; top: 0; left: 0; height: 100%}`
        and `.modal-body {flex: 1 1 auto}` unscoped. Our own rules never set
        `position`, so Bootstrap won for that property and pinned the dialog to
        the top-left corner at full height, ignoring the backdrop's centring.
        """
        owned = {
            "modal",
            "modal-head",
            "modal-body",
            "modal-foot",
            "modal-header",
            "modal-footer",
            "modal-dialog",
            "modal-content",
            "card",
            "card-body",
            "card-header",
            "card-footer",
            "btn",
            "col",
            "row",
            "mark",
            "badge",
            "alert",
            "container",
            "clay",
        }
        xml = self._asset("receipt_proposal_action.xml")
        tokens = set()
        for match in re.finditer(r'(?:class|t-attf-class)="([^"]*)"', xml):
            for token in re.split(r"[\s{}]+", match.group(1)):
                token = token.strip()
                if token and re.fullmatch(r"[a-z][\w-]*", token):
                    tokens.add(token)
        clash = tokens & owned
        self.assertFalse(
            clash, f"these class names are owned by the framework: {sorted(clash)}"
        )

    def test_layout_is_responsive_at_the_bootstrap_breakpoints(self):
        """RED/GREEN: the board narrows in step with the Odoo shell around it."""
        scss = self._asset("receipt_proposal_action.scss")
        for breakpoint in ("1199.98px", "991.98px", "767.98px", "575.98px"):
            self.assertIn(
                f"@media (max-width: {breakpoint})",
                scss,
                f"the board must adapt at {breakpoint}",
            )

    def test_fixed_width_surfaces_have_narrow_overrides(self):
        """RED/GREEN: columns, dialogs, drawer and grids all give way."""
        scss = self._asset("receipt_proposal_action.scss")
        narrow = scss.split("@media (max-width: 767.98px) {", 1)[1].split(
            "\n  @media", 1
        )[0]
        for rule in (
            "flex: 0 0 86vw",
            "max-width: none",
            "grid-template-columns: 1fr",
            "padding: 12px;",
        ):
            self.assertIn(rule, narrow, f"{rule} must apply on narrow screens")
        wide = scss.split("@media (max-width: 991.98px) {", 1)[1].split(
            "\n  @media", 1
        )[0]
        self.assertIn("repeat(2, 1fr)", wide)

    def test_wide_content_scrolls_inside_its_own_container(self):
        """RED/GREEN: tables scroll on their own; the board never scrolls the page."""
        scss = self._asset("receipt_proposal_action.scss")
        table = scss.split("\n  .table-wrap {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("overflow-x: auto", table)
        board = scss.split("\n  .board {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("overflow-x: auto", board)
        lane = scss.split("\n  .rp-lane-body {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("overflow-y: auto", lane)

    def test_scss_reuses_the_house_palette_and_adds_circuit_tokens(self):
        """RED/GREEN: clay palette plus the board's circuit / status tokens."""
        source = self._asset("receipt_proposal_action.scss")
        for token in (
            "--clay: #f2effc",
            "--canvas: #eae6f6",
            "--ink: #3a3160",
            "--peri: #7b6ef6",
            "--rose: #ff7a93",
            "--fac:",
            "--pre:",
            "--ok:",
            "--warn:",
            "--bad:",
            "--favor:",
        ):
            self.assertIn(token, source, f"{token} must be defined")

    def test_filter_helpers_are_pure_and_exported(self):
        """RED/GREEN: matching, ordering and options are pure helper functions.

        The board filters a payload it already holds, so every filter decision
        is a pure function of `(payload, filters)`. Keeping them in the helpers
        file is what stops a template expression from growing a filter of its
        own — and the helpers file still imports nothing but `_t`.
        """
        source = self._asset("receipt_proposal_helpers.esm.js")
        for symbol in (
            "export const FILTER_DEFAULTS",
            "export const SORT_ORDERS",
            "export function normalizeText",
            "export function matchesCustomer",
            "export function visibleCircuitKeys",
            "export function columnTotals",
            "export function sortColumns",
            "export function filterPool",
            "export function poolMethodOptions",
        ):
            self.assertIn(symbol, source, f"{symbol} must be exported")
        imports = [line for line in source.splitlines() if line.startswith("import ")]
        self.assertEqual(len(imports), 1)
        self.assertIn("@web/core/l10n/translation", imports[0])
        self.assertNotIn("useService", source)
        self.assertNotIn("@odoo/owl", source)

        # The four defaults, and the four sort keys the lane offers.
        self.assertIn(
            'export const FILTER_DEFAULTS = {search: "", circuit: "", '
            'method: "", sort: "name"};',
            source,
        )
        for key in ('key: "name"', 'key: "debt"', 'key: "collected"', 'key: "pending"'):
            self.assertIn(key, source, f"SORT_ORDERS must offer {key}")

    def test_filter_bar_is_paid_once_above_the_board(self):
        """RED/GREEN: one wrapping line between the ControlPanel and the board.

        The lane's height is what customers are read in, so a control the
        operator sets once MUST NOT be paid once per customer: the bar renders
        beside `.isolate-bar`, above `<main class="board">`, never inside the
        lane or a customer card. `Limpiar filtros` renders only while something
        is set, so an untouched board spends nothing on an inert button.
        """
        xml = self._asset("receipt_proposal_action.xml")
        root = etree.fromstring(xml.encode())
        action = root.xpath(
            '//t[@t-name="collection_receipt_proposal.ReceiptProposalAction"]'
        )[0]
        calls = [node.get("t-call") for node in action.xpath(".//t[@t-call]")]
        self.assertIn("collection_receipt_proposal.FilterBar", calls)
        self.assertLess(
            calls.index("collection_receipt_proposal.FilterBar"),
            calls.index("collection_receipt_proposal.PoolColumn"),
            "the filter bar must render before the board",
        )
        for owner in ("CustomerLane", "CustomerCard", "CircuitCard"):
            holder = root.xpath(f'//t[@t-name="collection_receipt_proposal.{owner}"]')[
                0
            ]
            self.assertNotIn(
                "collection_receipt_proposal.FilterBar",
                [node.get("t-call") for node in holder.xpath(".//t[@t-call]")],
                f"the filter bar must not be paid once per {owner}",
            )

        bar = root.xpath('//t[@t-name="collection_receipt_proposal.FilterBar"]')[0]
        self.assertEqual(len(bar.xpath('.//div[@class="rp-filters"]')), 1)
        clear = bar.xpath('.//button[@t-if="hasFilters"]')
        self.assertEqual(len(clear), 1)
        self.assertIn("Limpiar filtros", clear[0].text)

        # One wrapping row, like the lane header it sits above.
        scss = self._asset("receipt_proposal_action.scss")
        rules = scss.split("\n  .rp-filters {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("flex-wrap: wrap", rules)
        self.assertNotIn("flex-direction: column", rules)

    def test_customer_search_reads_name_and_cuit_without_accents(self):
        """RED/GREEN: `nunez` finds `Núñez`, and the CUIT is searched too.

        The planilla writes a partner's legal name with its accents and the
        operator types without them, so the comparison folds case and strips
        diacritics on both sides. The CUIT joins the haystack because it is the
        one identifier an operator reads off a cheque.
        """
        source = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn('.normalize("NFD")', source)
        self.assertIn('.replace(/\\p{Diacritic}/gu, "")', source)
        self.assertIn(".toLowerCase()", source)
        self.assertIn("normalizeText(column.partner_name)", source)
        self.assertIn("normalizeText(column.partner_vat)", source)
        # An empty needle matches everything rather than nothing.
        self.assertIn("if (!needle) {\n    return true;\n  }", source)

        action = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("matchesCustomer(column, this.state.filters.search)", action)

    def test_circuit_filter_hides_a_card_but_never_a_customer(self):
        """RED/GREEN: the circuit filter narrows the loop, not the lane.

        `hasCircuit` still decides only the `.rp-circ.empty` strip — an empty
        circuit MUST keep rendering, because it is the drop target that creates
        that circuit's first receipt value. The operator's own circuit filter
        is the one sanctioned way a circuit card is hidden, and the same
        control puts it back.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn(
            "return CIRCUIT_KEYS.includes(circuit) ? [circuit] : CIRCUIT_KEYS;",
            helpers,
        )
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        card = root.xpath('//t[@t-name="collection_receipt_proposal.CustomerCard"]')[0]
        loops = card.xpath('.//t[@t-foreach="visibleCircuitKeys"]')
        self.assertEqual(len(loops), 1, "the customer card loops the visible circuits")
        self.assertEqual(
            [node.get("t-call") for node in loops[0].xpath("./t[@t-call]")],
            ["collection_receipt_proposal.CircuitCard"],
        )
        # The lane still lists every matching customer, filtered circuit or not.
        lane = root.xpath('//t[@t-name="collection_receipt_proposal.CustomerLane"]')[0]
        self.assertEqual(
            len(lane.xpath('.//t[@t-foreach="visibleColumns"]')),
            1,
            "the lane is narrowed by the customer search, never by the circuit",
        )
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitCard"]')[
            0
        ]
        self.assertIn("'empty'", circuit[0].get("t-attf-class"))

    def test_pool_method_options_come_from_the_pool_and_key_on_the_code(self):
        """RED/GREEN: options are built from the pool, keyed on `document_type`.

        `method` is the translated label and cannot be indexed on — the payload
        ships the raw code beside it for exactly this reason. Building the
        options from the pool itself is also what stops the control offering a
        filter that would empty the column.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn("options.has(item.document_type)", helpers)
        self.assertIn(
            "options.set(item.document_type, {code: item.document_type, "
            "label: item.method});",
            helpers,
        )
        self.assertIn("item.document_type === method", helpers)

        action = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "return filterPool(this.pool, this.state.filters.method);", action
        )
        # A control with nothing to choose between is not drawn at all: a
        # `disabled` select over an empty pool reads as a broken control, which
        # is exactly how it was reported. `canFilterMethod` is the one gate,
        # and the prune below clears a filter the control stops offering.
        self.assertIn(
            "get canFilterMethod() {\n    return this.poolMethodOptions.length > 1;",
            action,
        )
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn('<label class="rp-filter" t-if="canFilterMethod">', xml)
        bar = xml.split('t-name="collection_receipt_proposal.FilterBar"', 1)[1].split(
            "\n    </t>", 1
        )[0]
        self.assertNotIn("t-att-disabled", bar)
        xml = self._asset("receipt_proposal_action.xml")
        # The pool column renders the filtered list; the lane is untouched by it.
        self.assertIn('t-foreach="visiblePool"', xml)
        self.assertNotIn('t-foreach="pool"', xml)

    def test_a_stale_method_filter_is_pruned_on_refresh(self):
        """RED/GREEN: assigning the last cheque clears a `check` filter.

        Every mutation returns a full board, so `applyBoard` is where state
        that names a vanished row is dropped — `collapsed` and `openSplits`
        already are. A method filter is the only filter that can name one: the
        search, circuit and sort survive every refresh.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "this.canFilterMethod ? this.poolMethodOptions.map("
            "(option) => option.code) : []",
            source,
        )
        self.assertIn(
            "if (this.state.filters.method && !offered.has(this.state.filters.method))",
            source,
        )
        applied = source.split("  applyBoard(payload) {", 1)[1].split("\n  }", 1)[0]
        for survivor in ("filters.search", "filters.circuit", "filters.sort"):
            self.assertNotIn(
                survivor, applied, f"{survivor} must survive a board refresh"
            )

    def test_lane_sort_copies_before_it_sorts(self):
        """RED/GREEN: the payload's own column order is never mutated.

        `state.board.columns` is the server's answer and the board is re-read
        against it on every refresh, so an in-place `sort()` would quietly
        rewrite what `name` — the default order — is supposed to restore.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn("return [...columns];", helpers)
        self.assertIn("return [...columns].sort(", helpers)
        self.assertNotIn("columns.sort(", helpers.replace("[...columns].sort(", ""))
        # Descending, and over the visible circuits — the operator orders by
        # the figure the cards in front of them are showing.
        self.assertIn(
            "columnTotals(right, kinds)[field] - columnTotals(left, kinds)[field]",
            helpers,
        )
        self.assertIn(
            'const SORT_FIELDS = {debt: "total", collected: "collected", '
            'pending: "available"};',
            helpers,
        )

    def test_totals_and_counts_follow_the_filter(self):
        """RED/GREEN: the lane sums what it shows, and names what it hid.

        Filtering to five customers to ask how much money is in play is why an
        operator filters; a header that kept summing forty-seven of them would
        answer a question nobody asked. So `laneTotals` sums the visible
        columns over the visible circuits, and the sheet's own figure rides
        beside it as a muted reference — the `de <total>` idiom a partly
        assigned pool card already uses. The header stays one wrapping line
        carrying exactly the Cobrado/Deuda pair.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "return this.columnsTotals(this.visibleColumns, this.visibleCircuitKeys);",
            source,
        )
        self.assertIn("return this.columnsTotals(this.columns, CIRCUIT_KEYS);", source)
        self.assertIn("const totals = {collected: 0, total: 0};", source)
        self.assertNotIn("totals.pending", source)

        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        lane = root.xpath('//t[@t-name="collection_receipt_proposal.CustomerLane"]')[0]
        figures = lane.xpath('.//div[@class="rp-lane-meta"]/span')
        self.assertEqual(len(figures), 2)
        self.assertEqual(
            [node.xpath("./em")[0].text.strip() for node in figures],
            ["Cobrado", "Deuda"],
        )
        # Each figure carries the unfiltered one beside it while filtered.
        for node in figures:
            reference = node.xpath('./small[@t-if="hasFilters"]')
            self.assertEqual(len(reference), 1, "a filtered figure names the sheet's")
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn("fmtShort(sheetTotals.collected)", xml)
        self.assertIn("fmtShort(sheetTotals.total)", xml)
        # Both counts read `N de M` while filtered.
        self.assertIn("visibleColumns.length", xml)
        self.assertIn("visiblePool.length", xml)

    def test_pool_assignment_chip_ignores_the_filter(self):
        """RED/GREEN: `Todo asignado` is a sheet fact, not a view state.

        A method filter that renders no card MUST NOT let the pool claim the
        planilla is finished, so the chip and the `Pendiente de asignar` total
        stay keyed on the unfiltered pool.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        pool = root.xpath('//t[@t-name="collection_receipt_proposal.PoolColumn"]')[0]
        chip = pool.xpath('.//span[contains(@t-attf-class, "chip")]')[0]
        self.assertIn("pool.length ?", chip.get("t-attf-class"))
        self.assertNotIn("visiblePool", chip.get("t-attf-class"))
        label = chip.xpath("./t[@t-out]")[0].get("t-out")
        self.assertIn("pool.length", label)
        self.assertNotIn("visiblePool", label)

        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "get sheetPoolTotal() {\n    return this.pool.reduce(",
            source,
        )
        # `Pendiente de asignar` follows the filter and names the sheet's own
        # figure beside it, the same way the lane header does.
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn("fmt(poolTotal)", xml)
        self.assertIn("fmtShort(sheetPoolTotal)", xml)

    def test_filters_hide_but_never_disable(self):
        """RED/GREEN: a filter removes cards and changes nothing else.

        Hiding a circuit card takes it out of the drop zones because it is off
        screen, and that is the operator's own explicit choice, revertible from
        the same control — so nothing auto-reveals on `dragstart`, no mutation
        clears a filter, and `Escape` keeps meaning "close the overlays, then
        every expanded circuit".
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("filters: {...FILTER_DEFAULTS},", source)
        self.assertIn(
            "clearFilters() {\n    this.state.filters = {...FILTER_DEFAULTS};\n  }",
            source,
        )
        # Drag start is untouched by the filters.
        for handler in ("onCardDragStart(ev, card) {", "onPoolDragStart(ev, item) {"):
            body = source.split(handler, 1)[1].split("\n  }", 1)[0]
            self.assertNotIn("filters", body)
        # Escape keeps its meaning.
        escape = source.split("  onEscape() {", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn("filters", escape)
        self.assertIn("this.closeAllDetails();", escape)
        # Every mutation runs through `runMutation`, which never touches them.
        mutation = source.split("  async runMutation(rpcCall, successMessage) {", 1)[
            1
        ].split("\n  }", 1)[0]
        self.assertNotIn("filters", mutation)

    def test_sheet_form_button_is_inherited_correctly(self):
        """RED/GREEN: the button sits after Document Review, gated on proposal."""
        view = self.env.ref(
            "collection_receipt_proposal.view_collection_sheet_form_receipt_proposal"
        )
        root = etree.fromstring(view.arch.encode())
        anchors = root.xpath('//button[@name="action_open_document_review"]')
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0].get("position"), "after")
        buttons = anchors[0].xpath('.//button[@name="action_open_receipt_proposal"]')
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("string"), "Receipt Proposal")
        self.assertEqual(buttons[0].get("invisible"), "not id or state != 'proposal'")
        self.assertEqual(buttons[0].get("type"), "object")

    def test_assignment_export_button_is_inherited_and_gated(self):
        """RED/GREEN: Exportar Asignaciones sits after the board button."""
        view = self.env.ref(
            "collection_receipt_proposal.view_collection_sheet_form_receipt_proposal"
        )
        root = etree.fromstring(view.arch.encode())
        anchors = root.xpath('//button[@name="action_open_document_review"]')
        buttons = anchors[0].xpath(
            './/button[@name="action_print_receipt_assignment_xlsx"]'
        )
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("string"), "Exportar Asignaciones")
        self.assertEqual(buttons[0].get("type"), "object")
        self.assertEqual(
            buttons[0].get("invisible"),
            "not id or state not in ('proposal', 'closed')",
        )
        self.assertEqual(
            buttons[0].getprevious().get("name"), "action_open_receipt_proposal"
        )

    def test_assignment_export_sits_before_the_planilla_export(self):
        """RED/GREEN: the new button MUST NOT displace `action_print_xlsx`."""
        form = self.env.ref("collection.view_collection_sheet_form")
        root = etree.fromstring(form.get_combined_arch().encode())
        header = root.xpath("//header")[0]
        object_buttons = [
            node.get("name") for node in header.xpath('./button[@type="object"]')
        ]
        self.assertIn("action_print_receipt_assignment_xlsx", object_buttons)
        self.assertLess(
            object_buttons.index("action_print_receipt_assignment_xlsx"),
            object_buttons.index("action_print_xlsx"),
        )

    def test_export_xlsx_stays_the_last_object_button(self):
        """RED/GREEN: `action_print_xlsx` remains last before `state`."""
        form = self.env.ref("collection.view_collection_sheet_form")
        root = etree.fromstring(form.get_combined_arch().encode())
        header = root.xpath("//header")[0]
        object_buttons = [
            node.get("name") for node in header.xpath('./button[@type="object"]')
        ]
        self.assertIn("action_open_receipt_proposal", object_buttons)
        self.assertEqual(object_buttons[-1], "action_print_xlsx")
        self.assertLess(
            object_buttons.index("action_open_receipt_proposal"),
            object_buttons.index("action_print_xlsx"),
        )

    def test_client_action_record_claims_no_url_path(self):
        """RED/GREEN: `path` stays unset; `ir_act_client_path_unique` forbids ''."""
        action = self.env.ref(
            "collection_receipt_proposal.action_collection_receipt_proposal"
        )
        self.assertEqual(action.type, "ir.actions.client")
        self.assertEqual(action.tag, "collection_receipt_proposal.receipt_proposal")
        self.assertFalse(action.path)

    def test_manifest_bundles_the_assets(self):
        """RED/GREEN: the OWL directory ships in `web.assets_backend`."""
        manifest = (Path(__file__).resolve().parents[1] / "__manifest__.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"collection_receipt_proposal/static/src/receipt_proposal/**/*"',
            manifest,
        )
        self.assertIn('"depends": ["collection"]', manifest)
