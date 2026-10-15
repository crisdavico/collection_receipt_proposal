# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re
from pathlib import Path

from lxml import etree

from odoo.tests import TransactionCase

_ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "src" / "receipt_proposal"

#: `document_type` code -> the `--t-*` family that paints its whole card: base
#: (the rail), `-ink` (the glyph stroke), `-soft` (the chip) and `-tint` (the
#: card's wash). `unsupported` is deliberately absent: a type the catalogue does
#: not name keeps the grey of the house and earns no hue of its own.
GLYPH_HUES = {
    "bank_transfer": "--t-transfer",
    "check": "--t-check",
    "echeck": "--t-echeck",
    "cash": "--t-cash",
    "cash_deposit": "--t-deposit",
    "seller_deposit": "--t-seller",
    "retention_certificate": "--t-retention",
}


def _luminance(colour):
    """WCAG relative luminance of an ``#rrggbb`` string."""
    colour = colour.lstrip("#")
    channels = [int(colour[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    channels = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(first, second):
    """WCAG contrast ratio between two ``#rrggbb`` strings."""
    values = sorted((_luminance(first), _luminance(second)))
    return (values[1] + 0.05) / (values[0] + 0.05)


def _hue(colour):
    """Hue in degrees of an ``#rrggbb`` string, or ``None`` when achromatic."""
    colour = colour.lstrip("#")
    red, green, blue = (int(colour[index : index + 2], 16) / 255 for index in (0, 2, 4))
    high, low = max(red, green, blue), min(red, green, blue)
    if high == low:
        return None
    span = high - low
    if high == red:
        return (60 * ((green - blue) / span)) % 360
    if high == green:
        return 60 * (2 + (blue - red) / span)
    return 60 * (4 + (red - green) / span)


def _hue_gap(first, second):
    """Shortest distance between two hues on the wheel, in degrees."""
    return min((first - second) % 360, (second - first) % 360)


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
            "action_proposal_reset_vouchers",
            "preview_proposal_transfer",
            "preview_proposal_circuit",
            "preview_proposal_undo_split",
            "preview_proposal_impute",
        ):
            self.assertIn(method, source, f"{method} must be reachable from the board")

    def test_helpers_stay_free_of_odoo_imports_beyond_translation(self):
        """RED/GREEN: the helpers import only `_t` and the pure amount parser.

        The parser takes the user's separators as arguments, so neither module
        reads a service: the component passes Odoo's `localization`. The
        parser itself imports nothing, which is what lets plain Node load it
        (`tests/amount_parser_test.js`).
        """
        source = self._asset("receipt_proposal_helpers.esm.js")
        modules = re.findall(r'^import\s*\{[^}]*\}\s*from\s*"([^"]+)";', source, re.M)
        self.assertEqual(
            sorted(modules),
            [
                "@collection_receipt_proposal/receipt_proposal/amount_parser.esm",
                "@web/core/l10n/translation",
            ],
        )
        parser = self._asset("amount_parser.esm.js")
        self.assertNotRegex(parser, r"(?m)^\s*import\b")

    def test_helpers_export_the_documented_surface(self):
        """RED/GREEN: the pure helper surface the component relies on."""
        source = self._asset("receipt_proposal_helpers.esm.js")
        for symbol in (
            "export const CIRCUITS",
            "export function formatAmount",
            "export function splitKind",
            "export function typeClass",
            "export function validateTransferAmount",
            "export function transferButtonLabel",
            "export function sanitizeBoardPayload",
            "export function nextIsolate",
            "export function glyphOf",
            "export function resetSummary",
            "export function resetBlockers",
            "export function circuitGap",
            "export {parseAmount, rawAmount};",
        ):
            self.assertIn(symbol, source, f"{symbol} must be exported")
        parser = self._asset("amount_parser.esm.js")
        self.assertIn("export function parseAmount(raw, separators)", parser)
        self.assertIn("export function rawAmount(value, separators)", parser)

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
        self.assertIn("return `t-${glyphOf(documentType)}`", source)
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
                "collection_receipt_proposal.ResetModal",
                "collection_receipt_proposal.Drawer",
            },
            names,
        )

    def test_a_value_card_is_coloured_by_its_payment_type(self):
        """RED/GREEN: the whole card wears its `document_type`, on two channels.

        Both card shapes -- the pool's `article.rp-card` and the lane's
        `.rp-vrow` -- take `t-<code>` from `typeClass`, which paints the rail
        (`--g`), the wash (`--g-tint`) and, by inheritance, the glyph chip
        (`--g-soft` / `--g-ink`). Neither reads `--c*` any more: a pool card has
        no circuit at all, and an assigned row is already inside the circuit
        card that names FAC / PRE with its pill and its own tint, so the row's
        own colour was spending itself on a fact its container had given.
        Shape stays the primary channel and MUST stay complete -- it is what
        survives a colour-blind operator and a greyscale print -- so every code
        keeps its own SVG branch and `unsupported` keeps the `t-else`.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        pool = root.xpath('//t[@t-name="collection_receipt_proposal.PoolColumn"]')[0]
        card = pool.xpath(".//article[@t-attf-class]")[0]
        self.assertEqual(
            card.get("t-attf-class"), "rp-card {{ typeClass(item.document_type) }}"
        )
        row = root.xpath('//div[starts-with(@t-attf-class, "rp-vrow ")]')[0]
        self.assertIn("{{ typeClass(card.document_type) }}", row.get("t-attf-class"))
        for node in (card, row):
            self.assertNotIn("cardClass", node.get("t-attf-class"))
            self.assertNotIn("c-none", node.get("t-attf-class"))

        glyph = root.xpath("//t[@t-name='collection_receipt_proposal.TypeGlyph']")[0]
        chip = glyph.xpath(".//span[@class='pay-glyph']")
        self.assertEqual(len(chip), 1, "the chip picks no colour of its own")
        self.assertEqual(chip[0].get("aria-hidden"), "true")
        branches = [
            node.get("t-if") or node.get("t-elif")
            for node in glyph.xpath(".//t[@t-if or @t-elif]")
        ]
        self.assertEqual(
            [re.search(r"'(\w+)'", branch).group(1) for branch in branches],
            list(GLYPH_HUES),
        )
        self.assertEqual(len(glyph.xpath(".//t[@t-else]")), 1)

        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn("return `t-${glyphOf(documentType)}`", helpers)

        scss = self._asset("receipt_proposal_action.scss")
        for rule in (".rp-card {", ".rp-vrow {"):
            body = scss.split(f"\n  {rule}", 1)[1].split("\n  }", 1)[0]
            wash = "linear-gradient(var(--g-tint), var(--g-tint)), var(--clay)"
            self.assertIn(f"background: {wash}", body)
            self.assertIn("background: var(--g);", body)
            self.assertNotIn("--c-tint", body)
        chip_rule = re.search(r"\.pay-glyph \{(.+?)\n  \}", scss, re.DOTALL).group(1)
        # Inherited, never re-picked -- and greyed for a glyph drawn outside a
        # card, which is what `unsupported` gets from `.t-unsupported` too.
        self.assertIn("background: var(--g-soft, var(--clay-deep))", chip_rule)
        self.assertIn("color: var(--g-ink, var(--ink-2))", chip_rule)
        self.assertIn("box-shadow: var(--inset-sm)", chip_rule)
        self.assertNotIn("g-unsupported", scss)
        for code, token in GLYPH_HUES.items():
            rule = scss.split(f"\n  .t-{code} {{", 1)[1].split("\n  }", 1)[0]
            for suffix, role in (
                ("", "--g"),
                ("-ink", "--g-ink"),
                ("-soft", "--g-soft"),
                ("-tint", "--g-tint"),
            ):
                self.assertIn(f"{role}: var({token}{suffix});", rule, code)
        neutral = scss.split("\n  .t-unsupported {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("--g: var(--ink-3);", neutral)
        self.assertIn("--g-tint: transparent;", neutral)

    def test_the_two_colour_systems_never_borrow_each_other(self):
        """RED/GREEN: `--c*` is the circuit's, `--g*` is the payment type's.

        Two colour systems share this screen, so each has to own its variables
        outright: a `.c-*` class that set a `--g` -- or a `.t-*` that set a
        `--c` -- would make one reading bleed into the other on whatever
        element happened to carry both.
        """
        scss = self._asset("receipt_proposal_action.scss")

        # What a rule SETS, not what it reads: `.t-unsupported` legitimately
        # borrows the house greys by value, the way `.c-none` does.
        def declared(rule):
            return re.findall(r"^\s*(--[\w-]+):", rule, re.M)

        for code in list(GLYPH_HUES) + ["unsupported"]:
            rule = scss.split(f"\n  .t-{code} {{", 1)[1].split("\n  }", 1)[0]
            self.assertTrue(declared(rule))
            for name in declared(rule):
                self.assertTrue(
                    name.startswith("--g"), f".t-{code} sets {name}, not its own token"
                )
        for circuit in (".c-inv,", ".c-quo,", ".c-none {"):
            rule = scss.split(f"\n  {circuit}", 1)[1].split("\n  }", 1)[0]
            self.assertTrue(declared(rule))
            for name in declared(rule):
                self.assertTrue(
                    name.startswith("--c"), f"{circuit} sets {name}, not its own token"
                )
        # The circuit card is not one of the `.c-*` owners: its frame and wash
        # are the house's, the same on both circuits. The one place the board
        # says Facturas or Presupuestos in colour is the `.ct` pill, which
        # keys its fill on the circuit and on nothing else.
        for owner in (".rp-circ.inv,", ".rp-circ.quo,"):
            self.assertNotIn(owner, scss)
        pill = scss.split("\n  .ct {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("background: var(--ct-bg, var(--ink-3));", pill)
        for kind, token in (("inv", "--fac-ink"), ("quo", "--pre-ink")):
            fill = pill.split(f"&.{kind} {{", 1)[1].split("}", 1)[0]
            self.assertIn(f"--ct-bg: var({token});", fill)
        self.assertNotIn("--g", pill)

    def test_a_circuit_card_is_framed_the_same_on_every_customer(self):
        """RED/GREEN: `.rp-circ` wears the house frame and wash, on both circuits.

        Facturas and Presupuestos are read by comparing customers -- the same
        circuit down the lane -- so the circuit card has to look the same on
        all of them. What differs inside is the voucher rows, which are
        coloured by payment type. A frame and a wash tinted by the circuit put
        a second colour system on the whole surface of every card, competing
        with the payment types inside it, so both are the house's own and the
        `.ct` pill is what names the circuit.
        """
        scss = self._asset("receipt_proposal_action.scss")
        circuit = scss.split("\n  .rp-circ {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("border: 1px solid var(--edge);", circuit)
        self.assertIn("background: var(--clay-deep);", circuit)
        # Neither colour system may reach the card's frame or its wash: not the
        # payment type's `--g*`, and not the circuit's `--c*` either.
        self.assertNotIn("--g", circuit)
        self.assertNotRegex(circuit, r"var\(--c(?:-[\w-]+)?[,)]")
        for selector, token in ((".c-inv,", "--fac-line"), (".c-quo,", "--pre-line")):
            rule = scss.split(f"\n  {selector}", 1)[1].split("\n  }", 1)[0]
            self.assertIn(f"--c-line: var({token});", rule)
        for token in ("--fac-line: rgba(", "--pre-line: rgba("):
            self.assertIn(token, scss)
        # The empty strip keeps that same frame and only breaks it into
        # dashes: it is the drop target that creates the circuit's first
        # value, and a second grey `outline` on top of the border said the
        # same thing twice in a colour the circuit does not own.
        empty = scss.split("\n  .rp-circ.empty {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("border-style: dashed;", empty)
        self.assertNotIn("outline", empty)

    def test_a_customer_card_closes_itself_off_from_the_next_one(self):
        """RED/GREEN: `.rp-cust` carries a hard 1px edge, not just a shadow.

        A customer card is tall -- a header plus two circuit cards, more when
        one is expanded -- so where one ends and the next begins has to be
        visible without counting rows. The house shadow is diffuse and lands on
        the lane body's `--clay-deep`, which is nearly the card's own `--clay`,
        so the edge does the closing and the shadow only lifts the card. It
        costs no height: the board is `box-sizing: border-box` throughout.
        """
        scss = self._asset("receipt_proposal_action.scss")
        card = scss.split("\n  .rp-cust {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("border: 1px solid var(--edge);", card)
        self.assertIn("box-shadow: var(--raise-sm);", card)
        self.assertIn("--edge: rgba(", scss)
        root = scss.split("\n  *,", 1)[0]
        self.assertIn("box-sizing: border-box", root)
        # The one gap that separates a CUSTOMER from the next is the lane's.
        lane = scss.split("\n  .rp-lane-body {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("gap: 8px", lane)

    def test_the_payment_type_palette_is_legible_and_spread_out(self):
        """RED/GREEN: seven hues, off the circuit's two, each 4.5:1 on its chip.

        The ink paints a 1.4px SVG stroke, which is the thinnest mark the board
        draws, so the AA text floor is the right floor for it. The palette also
        has to be told apart across a grid of pool cards: the hues are spread
        around the wheel and every one keeps its distance from the circuit
        pair, whose meaning they must never seem to repeat. And a card's wash
        is built from its own base, so a tint can never drift onto a hue that
        belongs to another type.
        """
        scss = self._asset("receipt_proposal_action.scss")
        tokens = dict(re.findall(r"(--[\w-]+): (#[0-9a-f]{6});", scss))
        tints = dict(re.findall(r"(--[\w-]+): (rgba\([^)]+\));", scss))
        hues = {}
        for code, token in GLYPH_HUES.items():
            for suffix in ("", "-ink", "-soft"):
                self.assertIn(f"{token}{suffix}", tokens, code)
            self.assertGreaterEqual(
                _contrast(tokens[f"{token}-ink"], tokens[f"{token}-soft"]),
                4.5,
                f"{code} stroke on its chip",
            )
            base = tokens[token].lstrip("#")
            channels = ", ".join(
                str(int(base[index : index + 2], 16)) for index in (0, 2, 4)
            )
            self.assertEqual(
                tints[f"{token}-tint"],
                f"rgba({channels}, 0.11)",
                f"{code} must wash its card with its own base",
            )
            hues[code] = _hue(tokens[token])
        self.assertEqual(len({tokens[token] for token in GLYPH_HUES.values()}), 7)
        circuit = (_hue(tokens["--fac"]), _hue(tokens["--pre"]))
        for code, hue in hues.items():
            for other in circuit:
                self.assertGreaterEqual(
                    _hue_gap(hue, other), 20, f"{code} crowds a circuit hue"
                )
            for peer, peer_hue in hues.items():
                if peer != code:
                    self.assertGreaterEqual(
                        _hue_gap(hue, peer_hue), 20, f"{code} crowds {peer}"
                    )

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
        chip_rule = re.search(r"\.pay-glyph \{(.+?)\n  \}", scss, re.DOTALL).group(1)
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
        clicks = [node.get("t-on-click") or "" for node in foots[0].xpath(".//button")]
        self.assertEqual(len(clicks), 2)
        self.assertTrue(any("autoDistribute" in click for click in clicks))
        self.assertTrue(any("confirmImpute" in click for click in clicks))
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
        second row restating them — two rows of chrome for the same numbers,
        while the header's own middle sat empty on a card that can be 1400px
        wide. `circuitFigures` returns the payload's figures normally and the
        ones the operator's inputs are producing while expanded, so the header
        alone can carry both jobs.
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

        Fitting more customers at a glance came from deleting repeated chrome:
        the footer went away while collapsed, the CUIT joined the name's line,
        and the circuit's noun moved into the pill that was already there.

        The header keeps the two figures the circuit is *summed* by — Cob. and
        Deuda — read straight off the right edge of that pill. Imputado is the
        sum of a column the expanded grid already prints per document, and Sin
        imputar is not a subtotal at all but the budget that grid spends, so it
        moved to `.rp-circ-budget` in the footer, live, and only while the grid
        that spends it is open.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitCard"]')[
            0
        ]
        head = circuit.xpath('.//div[@class="rp-circ-head"]')[0]
        nums = head.xpath('.//div[@class="rp-circ-nums"]/span')
        self.assertEqual(
            [span.xpath("./em")[0].text for span in nums], ["Cob.", "Deuda"]
        )
        self.assertEqual(len(head.xpath('.//span[@class="rp-circ-count"]')), 1)
        # One pill, carrying the noun the separate label used to repeat, and
        # the two figures read straight off its right edge.
        pills = head.xpath('./span[starts-with(@t-attf-class, "ct ")]')
        self.assertEqual(len(pills), 1)
        self.assertEqual(pills[0].get("t-out"), "circuits[kind].Noun")
        figures = head.xpath('./t/div[@class="rp-circ-nums"]')[0]
        self.assertEqual(head.index(figures.getparent()), head.index(pills[0]) + 1)

        # Sin imputar lives in the footer, live, and only while expanded.
        foot = circuit.xpath('.//div[@class="rp-circ-foot"]')[0]
        budget = foot.xpath('./span[@class="rp-circ-budget"]')
        self.assertEqual(len(budget), 1)
        self.assertEqual(budget[0].xpath("./em")[0].text, "Sin imputar")
        self.assertIn("imputeAvailable(detail)", budget[0].xpath("./b")[0].get("t-out"))

        xml = self._asset("receipt_proposal_action.xml")
        self.assertNotIn("rp-circ-lab", xml)

        scss = self._asset("receipt_proposal_action.scss")
        self.assertNotIn(".rp-circ-lab", scss)
        title = scss.split("\n  .rp-cust-title {", 1)[1].split("\n  }\n", 1)[0]
        self.assertNotIn("display: block", title)

    def test_a_circuit_without_values_keeps_only_its_header(self):
        """RED/GREEN: no voucher applied, no coverage bar and no empty notice.

        A circuit that has debt but has not been paid yet drew a bar pinned at
        0 % and a ~55px "Sin valores aplicados" notice — between the two, half
        a customer card per circuit, paid once per customer on screen and
        saying nothing the header does not. So the card stops at its header:
        the pill, Cob./Deuda and the toggle stay, and the drop invitation
        becomes the text on the line that header already draws. No figure is
        dropped — the density is always paid out of chrome.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitCard"]')[
            0
        ]
        self.assertIn("'novalues'", circuit[0].get("t-attf-class"))
        head = circuit.xpath('.//div[@class="rp-circ-head"]')[0]
        hint = head.xpath('.//span[@class="rp-circ-count dim"]')
        self.assertEqual(len(hint), 1, "the invitation rides the header line")
        self.assertEqual(hint[0].get("t-else"), "")
        # The bar and the rows are the two blocks a circuit without values
        # stops paying for.
        prog = circuit.xpath('.//div[@class="rp-circ-prog"]')[0]
        rows = circuit.xpath('.//div[@class="rp-circ-rows"]')[0]
        for node in (prog, rows):
            self.assertEqual(node.get("t-if"), "hasValues(column, kind)")
        self.assertFalse(
            rows.xpath('.//p[contains(@class, "empty-hint")]'),
            "the empty notice is the header's text now, not a block of its own",
        )
        # Figures and toggle are untouched by the state.
        self.assertEqual(len(head.xpath('.//div[@class="rp-circ-nums"]')), 1)
        self.assertEqual(len(head.xpath('.//button[@class="rp-circ-toggle"]')), 1)

        action = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "hasValues(column, kind) {\n    return this.circuitCards(column, kind)"
            ".length > 0;",
            action,
        )
        scss = self._asset("receipt_proposal_action.scss")
        novalues = scss.split("\n  .rp-circ.novalues {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("padding-bottom", novalues)
        self.assertIn(".rp-circ.novalues .rp-circ-head {", scss)

    def test_the_unassigned_pool_flows_in_a_grid_of_short_cards(self):
        """RED/GREEN: the pool is counted at a glance, so it is dense.

        One vertical stack of ~110px cards showed five comprobantes in a
        column with the width for two abreast. The body flows in an auto-fill
        grid instead — one card per row while the column is narrow, more as it
        widens — and the card itself is three short lines. The `S/C` pill went
        with the old third line: every card in this column is unassigned, so a
        badge that reads the same on all forty distinguishes none of them. The
        payer's name stays, because it is who the card gets dragged to, and
        everything that truncates rides the article's `title`.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        pool = root.xpath('//t[@t-name="collection_receipt_proposal.PoolColumn"]')[0]
        card = pool.xpath(".//article[@t-attf-class]")[0]
        self.assertEqual(card.get("t-att-title"), "poolCardTitle(item)")
        self.assertEqual(
            [node.get("class") for node in card],
            ["rp-card-top", "rp-card-amount", "rp-card-who"],
        )
        self.assertFalse(card.xpath('.//span[@class="ct none"]'))
        who = card.xpath('./div[@class="rp-card-who"]')[0]
        self.assertEqual(
            [node.get("t-out") for node in who],
            ["item.reference", "item.partner_name"],
        )

        action = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("return [item.method, item.reference, item.partner_name]", action)

        scss = self._asset("receipt_proposal_action.scss")
        body = scss.split("\n  .rp-col.pool .rp-col-body {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("display: grid", body)
        self.assertIn("repeat(auto-fill, minmax(150px, 1fr))", body)
        self.assertIn("align-content: start", body)
        # The lane is NOT a grid: its body is the stack of customers.
        lane_body = scss.split("\n  .rp-lane-body {", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn("auto-fill", lane_body)
        # A hint with no card beside it still spans the row.
        self.assertIn(".rp-col.pool .rp-col-body > .empty-hint {", scss)
        # The compact card is scoped to the pool, so the shared `.rp-card`
        # rhythm the modals read is untouched.
        self.assertIn("\n  .rp-col.pool .rp-card {", scss)

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
        self.assertIn("padding: 8px 14px 6px", head)
        # The pool's head is one wrapping line too, on its own tight padding.
        pool_head = scss.split("\n  .rp-col.pool .rp-col-head {", 1)[1].split(
            "\n  }", 1
        )[0]
        self.assertIn("padding: 10px 14px 8px", pool_head)

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

        A seed written with `String(row.applied)` would always carry a `.`,
        which an es_AR board reads as a thousands mark when three digits
        follow it. `rawAmount` writes the user's own decimal point instead, so
        every seed goes through it; only user input refreshes the parsed
        amount.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("raw: rawAmount(row.applied, localization)", source)
        self.assertNotIn("String(row.applied)", source)
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

    def test_transfer_modal_never_re_asks_the_circuit(self):
        """RED/GREEN: the drop already chose FAC or PRE, so the modal does not.

        Two cards per customer means the gesture names the circuit. A picker
        inside the modal made the operator answer twice and let them contradict
        the card they aimed at. The picker belongs to the Cambiar circuito
        modal, which is the one entry point with no target circuit.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        modal = root.xpath('//t[@t-name="collection_receipt_proposal.TransferModal"]')[
            0
        ]
        rendered = etree.tostring(modal, encoding="unicode")
        self.assertNotIn("circ-pick", rendered)
        self.assertNotIn("setTransferKind", rendered)
        self.assertNotIn("Circuito de aplicación", rendered)
        self.assertNotIn("Elegí el circuito", rendered)
        # The target circuit is still shown — it is stated, not asked.
        self.assertIn("tstrip", rendered)
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertNotIn("setTransferKind", source)
        # The Cambiar circuito modal keeps its picker.
        circuit = root.xpath('//t[@t-name="collection_receipt_proposal.CircuitModal"]')[
            0
        ]
        self.assertIn("circ-pick", etree.tostring(circuit, encoding="unicode"))

    def test_transfer_preview_drops_the_circuit_it_already_fixed(self):
        """RED/GREEN: the FIFO preview names no circuit inside Transferir.

        The drop chose FAC or PRE and the `tstrip` states it, so a pill and a
        `facturas`/`presupuestos` noun on every plan line only repeat it. The
        Cambiar circuito and Deshacer division modals keep both: the first is
        about moving between circuits, the second reunifies parts that may sit
        on different ones.
        """
        xml = self._asset("receipt_proposal_action.xml")
        root = etree.fromstring(xml.encode())
        for name, expected in (
            ("TransferModal", "false"),
            ("CircuitModal", "true"),
            ("UndoSplitModal", "true"),
        ):
            modal = root.xpath(f'//t[@t-name="collection_receipt_proposal.{name}"]')
            self.assertTrue(modal, f"{name} must exist")
            sets = modal[0].xpath('.//t[@t-set="previewCircuits"]')
            self.assertEqual(len(sets), 1, f"{name} must set previewCircuits once")
            self.assertEqual(sets[0].get("t-value"), expected)
        # Every node that names a circuit is gated on that flag, either inside
        # its own expression or by a `t-if` on itself or an ancestor.
        panel = root.xpath('//t[@t-name="collection_receipt_proposal.PreviewPanel"]')[0]
        circuit_nodes = panel.xpath('.//*[contains(@t-out, "plan.document_kind")]')
        self.assertTrue(circuit_nodes, "the panel must still be able to name a circuit")
        for node in circuit_nodes:
            self.assertTrue(
                "previewCircuits" in node.get("t-out")
                or node.xpath('ancestor-or-self::*[@t-if="previewCircuits"]'),
                node.get("t-out"),
            )
        # The FAC/PRE tint on the row itself goes with the pill.
        rows = panel.xpath(
            './/*[starts-with(@t-attf-class, "ai-line ")'
            ' or starts-with(@t-attf-class, "ai-more ")]'
        )
        self.assertTrue(rows, "the panel must still render its plan rows")
        for node in rows:
            self.assertIn("previewCircuits", node.get("t-attf-class"))

    def test_preview_count_keeps_the_space_and_agrees_in_number(self):
        """RED/GREEN: `1 factura`, not `1facturas`.

        Two sibling `t-out` nodes rendered the count and the noun with no space
        between them, so the count label is built in one expression instead.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("previewCountLabel(plan, withCircuit)", source)
        self.assertIn("count === 1 ? circuit.one : circuit.noun", source)
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        for singular in ('one: "factura"', 'one: "presupuesto"'):
            self.assertIn(singular, helpers)
        panel = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        panel = panel.xpath('//t[@t-name="collection_receipt_proposal.PreviewPanel"]')[
            0
        ]
        rendered = etree.tostring(panel, encoding="unicode")
        self.assertIn("previewCountLabel(plan, previewCircuits)", rendered)
        self.assertNotIn('t-out="plan.changes.length"', rendered)

    def test_the_transfer_strip_reads_as_a_statement_not_a_field(self):
        """RED/GREEN: the `tstrip` states the route, it never offers to edit it.

        In this design the sunken shadow means "type here" and the raised one
        means "press me", so a strip carrying both read as an editable field
        with a button inside it. It is a flat, shadowless surface; the circuit
        still shows through the `ct` pill and a plain tint.
        """
        scss = self._asset("receipt_proposal_action.scss")
        strip = scss.split("\n  .tstrip {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("box-shadow: none", strip)
        self.assertNotIn("--inset", strip)
        self.assertNotIn("--raise", strip)
        target = strip.split("\n    .to {", 1)[1].split("\n    }", 1)[0]
        self.assertIn("box-shadow: none", target)
        self.assertIn("var(--c-tint", target)

    def test_the_transfer_modal_states_what_the_target_circuit_owes(self):
        """RED/GREEN: Deuda / Cobrado / Falta ride under the `tstrip`.

        The modal covers the circuit card that carried those figures, and
        splitting a value is exactly the question "how much does this circuit
        still need?" — without the line the operator had to cancel, read the
        card and drag again. It repeats the card's own label-beside-number
        idiom and, like the `tstrip` above it, it is a reading and not a
        control: flat and shadowless, because a sunken surface in this design
        says "type here" and what is typed is the amount below.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        modal = root.xpath('//t[@t-name="collection_receipt_proposal.TransferModal"]')[
            0
        ]
        figures = modal.xpath('.//div[@t-if="transferFigureGroups.length"]')
        self.assertEqual(len(figures), 1, "the figures line renders once")
        rendered = etree.tostring(figures[0], encoding="unicode")
        for label in ("Deuda", "Cobrado", "Falta", "A favor"):
            self.assertIn(f"<em>{label}</em>", rendered)
        self.assertIn("group.figures.total", rendered)
        self.assertIn("group.figures.collected", rendered)
        # It states the figures; the route and the circuit stay the strip's job.
        self.assertNotIn("circuitClass", rendered)
        scss = self._asset("receipt_proposal_action.scss")
        block = scss.split("\n  .tfigs {", 1)[1].split("\n  }\n", 1)[0]
        self.assertNotIn("--inset", block)
        self.assertNotIn("--raise", block)
        self.assertNotIn("box-shadow", block)

    def test_a_transfer_side_that_is_not_a_circuit_carries_no_figures(self):
        """RED/GREEN: the pool has no debt, so it contributes no group.

        Dropping from `Sin asignar` leaves only the destination group, and
        `Devolver a Sin asignar` leaves only the origin one.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        figures = source.split("  circuitFiguresOf(allocationId, kind) {", 1)[1].split(
            "\n  }\n", 1
        )[0]
        self.assertIn("if (!allocationId || !kind) {", figures)
        self.assertIn("return null;", figures)
        groups = source.split("  get transferFigureGroups() {", 1)[1].split(
            "\n  }\n", 1
        )[0]
        self.assertIn("modal.source_allocation_id, modal.source_kind", groups)
        self.assertIn("modal.to_allocation_id, modal.kind", groups)

    def test_the_gap_is_debt_minus_collected_never_the_payload_pending(self):
        """RED/GREEN: `Falta` answers "how much money is still missing here".

        `pending` is debt net of what FIFO already imputed, so a circuit
        holding money that is not imputed yet would read as needing more than
        it does. The figure the operator is about to type is debt minus
        collected.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        body = helpers.split("export function circuitGap(figures, currency) {", 1)[
            1
        ].split("\n}", 1)[0]
        self.assertIn(
            "splitAmount(circuit.total) - splitAmount(circuit.collected)", body
        )
        self.assertNotIn("pending", body)
        # Two sums of floats leave a remainder the shortcut would seed verbatim.
        self.assertIn("roundAmount(", body)
        rounder = helpers.split("export function roundAmount(value, currency) {", 1)[
            1
        ].split("\n}", 1)[0]
        self.assertIn("Number(splitAmount(value).toFixed(decimals))", rounder)

    def test_the_cover_shortcut_names_its_amount_and_never_repeats_todo(self):
        """RED/GREEN: `Cubrir $ …` renders only when it says something new.

        A gap wider than the value is what `Todo` already does, and a circuit
        with nothing missing has nothing to cover — a dead or duplicate
        control on screen reads as a broken one, so it is not drawn.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        quick = source.split("  get transferGapQuick() {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn(
            "gap > 0 && gap < modal.maximum - AMOUNT_EPSILON ? gap : 0", quick
        )
        self.assertIn('_t("Cubrir %s", this.fmt(this.transferGapQuick))', source)
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        button = root.xpath('//button[@t-out="transferGapQuickLabel"]')
        self.assertEqual(len(button), 1)
        self.assertEqual(button[0].get("t-if"), "transferGapQuick")
        self.assertIsNone(button[0].get("disabled"))
        self.assertEqual(button[0].get("t-on-click"), "setTransferGap")

    def test_the_amount_seed_survives_a_decimal(self):
        """RED/GREEN: a seed is written in the user's decimal point.

        Seeding the input with `String(1000.5)` once came back as 10005, so
        the modal opened over its own maximum with the confirm button dead.
        The seed carries the locale's decimal point and no thousands mark, so
        `parseAmount` reads it back as the same number in every locale (the
        round trips run in `tests/amount_parser_test.js`).
        """
        parser = self._asset("amount_parser.esm.js")
        body = parser.split("export function rawAmount(value, separators) {", 1)[
            1
        ].split("\n}", 1)[0]
        self.assertIn(".replace(DOT, decimalPoint)", body)
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("raw_amount: rawAmount(maximum, localization)", source)
        self.assertIn(
            "modal.raw_amount = rawAmount(this.transferGapQuick, localization)",
            source,
        )
        self.assertNotIn("raw_amount: String(maximum)", source)

    def test_every_typed_amount_is_read_in_the_user_locale(self):
        """RED/GREEN: the component hands Odoo's separators to every read.

        A call without them falls back to `.` as the decimal point, which on
        an es_AR board would read `1.234` as 1.234 instead of 1234.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            'import {localization} from "@web/core/l10n/localization";', source
        )
        calls = []
        for match in re.finditer(
            r"\b(parseAmount|rawAmount|validateTransferAmount)\(", source
        ):
            depth, end = 1, match.end()
            while depth:
                depth += {"(": 1, ")": -1}.get(source[end], 0)
                end += 1
            calls.append((match.group(1), source[match.end() : end - 1]))
        self.assertGreaterEqual(len(calls), 7)
        for name, arguments in calls:
            last = arguments.strip().rstrip(",").rsplit(",", 1)[-1].strip()
            self.assertEqual(
                last, "localization", f"{name}({arguments.strip()}) must pass it"
            )

    def test_preview_lines_keep_the_space_before_the_dash(self):
        """RED/GREEN: `Luciana Morelli — sin cambios.`, never `Morelli—`.

        OWL drops a whitespace-only text node between two elements, so the dash
        has to sit in a text node that carries it rather than open a `t-else`.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        panel = root.xpath('//t[@t-name="collection_receipt_proposal.PreviewPanel"]')[0]
        for node in panel.xpath(".//b[@t-out='plan.partner_name']"):
            tail = node.tail or ""
            self.assertTrue(
                tail.strip().startswith("\u2014"),
                f"the dash must follow the name in its own text node, got {tail!r}",
            )
            self.assertTrue(tail.endswith(" "), f"a space must close {tail!r}")

    def test_dragging_to_an_edge_scrolls_the_board_under_the_pointer(self):
        """RED/GREEN: the drag scrolls the lane when the pointer nears an edge.

        HTML5 drag and drop moves nothing on its own: the operator drags a
        value to the foot of the lane and the customer they are aiming at is
        simply off screen. The board tracks the pointer in a CAPTURE-phase
        `dragover` -- the drop zones stop propagation on the way up, and
        capture runs before them -- and scrolls on its own animation frame,
        because `dragover` stops firing the moment the pointer holds still
        against the edge, which is exactly when the list has to keep running.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn('document.addEventListener("dragover"', source)
        self.assertIn("this.dragScrollListener, true)", source)
        self.assertIn('document.removeEventListener("dragover"', source)
        self.assertIn(
            "window.requestAnimationFrame(() => this.autoScrollFrame())", source
        )
        self.assertIn("window.cancelAnimationFrame(this.dragScrollFrame)", source)
        # Both drag sources arm it, and every end of a drag disarms it.
        for handler in ("onCardDragStart(ev, card) {", "onPoolDragStart(ev, item) {"):
            block = source.split(f"  {handler}", 1)[1].split("\n  }\n", 1)[0]
            self.assertIn("this.startAutoScroll();", block)
        for handler in ("onDragEnd() {", "onZoneDrop(ev, column, kind) {"):
            block = source.split(f"  {handler}", 1)[1].split("\n  }\n", 1)[0]
            self.assertIn("this.stopAutoScroll();", block)
        self.assertIn("this.stopAutoScroll();\n    });", source)

    def test_autoscroll_only_drives_a_really_scrollable_ancestor(self):
        """RED/GREEN: `overflow: hidden` is not a scroll container.

        The board is full of cards that clip with `overflow: hidden`, and a
        clipping element still accepts a written `scrollTop`. Without the
        filter the innermost card would swallow the gesture and scroll its own
        contents instead of letting the lane run. The walk climbs until one
        ancestor actually moves, so a lane that has hit bottom hands the
        gesture to the board rather than eating it.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            'const SCROLLABLE_OVERFLOW = new Set(["auto", "scroll"]);', source
        )
        block = source.split("  autoScrollAt(x, y) {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("document.elementFromPoint(x, y)", block)
        self.assertIn("SCROLLABLE_OVERFLOW.has(style.overflowY)", block)
        self.assertIn("SCROLLABLE_OVERFLOW.has(style.overflowX)", block)
        self.assertIn("node = node.parentElement", block)
        self.assertIn(
            "if (node.scrollTop !== top || node.scrollLeft !== left) {",
            block,
            "the walk must stop at the first ancestor that really moved",
        )

    def test_autoscroll_step_is_symmetric_and_pure(self):
        """RED/GREEN: up and down come out of one signed calculation.

        The delta is geometry over a rect, so it lives with the pure helpers
        and the component only reads a rect, adds and writes. Nearing the start
        of an axis yields a negative step and nearing its end a positive one,
        which is what makes the header scroll up and the foot scroll down
        without a second code path. The band never exceeds half the axis, or a
        short container would scroll for every pointer inside it.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        block = helpers.split("function axisScrollStep(start, end, position) {", 1)[
            1
        ].split("\n}\n", 1)[0]
        self.assertIn("Math.min(AUTOSCROLL_EDGE, span / 2)", block)
        self.assertIn("if (position < start + edge) {", block)
        self.assertIn("return -Math.ceil((1 - depth) * AUTOSCROLL_STEP);", block)
        self.assertIn("if (position > end - edge) {", block)
        self.assertIn("return Math.ceil((1 - depth) * AUTOSCROLL_STEP);", block)
        # Outside the container counts as pinned to the edge: the pointer
        # leaves the lane before the button is released.
        self.assertEqual(block.count("Math.max("), 2)
        delta = helpers.split("export function autoscrollDelta(rect, x, y) {", 1)[
            1
        ].split("\n}\n", 1)[0]
        self.assertIn("x: axisScrollStep(rect.left, rect.right, x)", delta)
        self.assertIn("y: axisScrollStep(rect.top, rect.bottom, y)", delta)
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("autoscrollDelta,", source)

    def test_dropping_a_value_on_its_own_circuit_is_ignored(self):
        """RED/GREEN: a self-drop opens no modal.

        With the circuit pre-answered there is nothing left to change, so the
        modal would open with Cancelar as its only live button.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        drop = source.split("  onZoneDrop(ev, column, kind) {", 1)[1].split(
            "\n  }\n", 1
        )[0]
        self.assertIn("card.document_kind === kind", drop)
        self.assertIn("this.allocationOfCard(card) === column.allocation_id", drop)

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
        self.assertIn("flex: 5 5", lane)

    def test_board_splits_two_sevenths_to_the_pool(self):
        """RED/GREEN: the pool owns 2/7 of the board, the customer lane 5/7.

        The ratio is set by the pool's card grid and nothing else. A quarter
        left ~322px of card track after the body's margin and padding, short
        of two cards abreast, so the column that exists to be counted at a
        glance fell back to single file at every width; a full third bought
        the second card with lane the customer cards needed. 2/7 with a 150px
        grid track is the narrowest split that still fits two.
        """
        scss = self._asset("receipt_proposal_action.scss")
        column = scss.split("\n  .rp-col {", 1)[1].split("\n  }", 1)[0]
        lane = scss.split("\n  .rp-lane {", 1)[1].split("\n  }", 1)[0]
        # `flex-basis: 0` on both sides makes the grow factors the whole ratio,
        # so the split stays 2:5 whatever the board is wide.
        self.assertIn("flex: 2 2 0", column)
        self.assertIn("flex: 5 5 0", lane)
        self.assertNotIn("width: 312px", column)
        # A min-width each, so the two still scroll rather than crush on narrow.
        self.assertIn("min-width: 300px", column)
        self.assertIn("min-width:", lane)
        # Two cards abreast is what the width is for, and the two numbers are
        # one decision: the track has to fit inside what the split hands over.
        body = scss.split("\n  .rp-col.pool .rp-col-body {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("minmax(150px, 1fr)", body)

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

    def test_module_ships_es_ar_translations(self):
        """The board copy is inline Spanish, but server messages are English.

        Access, guard and money errors added by the production hardening are
        English source strings, so es_AR users need the shipped catalog.
        """
        addon = Path(__file__).resolve().parents[1]
        self.assertTrue((addon / "i18n" / "es_AR.po").is_file())
        self.assertTrue((addon / "i18n" / "collection_receipt_proposal.pot").is_file())

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
        # The customer card's two circuits stop sitting side by side before the
        # board itself starts stacking.
        self.assertIn(".rp-cust-body", wide)
        self.assertIn("grid-template-columns: 1fr", wide)

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

    def test_circuit_rows_are_grouped_by_payment_type(self):
        """RED/GREEN: a circuit card's rows are ordered by comprobante type.

        Every row inside a Facturas card is `document_kind == "invoice"` by
        construction -- the circuit IS the card -- so the only kind that varies
        from row to row is the voucher's own `document_type`, and that is what
        the operator has in their hand while reconciling: the cheques together,
        the transferencias together. The key is the translated `method` label,
        the same one `methodOptions` sorts the method select by, so the card
        and the filter name the types in one order. It sorts a COPY, like
        `sortColumns`, because `column.cards` is the server's answer and the
        board is re-read against it on every refresh -- and on one criterion
        only, so JS's stable sort keeps the payload's `value_id` order inside a
        type and no untouched row moves on a refresh.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn("export function sortCardsByType", helpers)
        body = helpers.split("export function sortCardsByType(cards) {", 1)[1].split(
            "\n}", 1
        )[0]
        self.assertIn("[...cards].sort(", body, "it MUST sort a copy of the payload")
        self.assertIn(
            'localeCompare(String(right.method || ""), "es")',
            body,
            "the key is the translated method label, like methodOptions",
        )
        self.assertEqual(
            body.count(".sort("), 1, "one criterion only -- stability does the rest"
        )
        self.assertNotIn(
            "document_kind",
            body,
            "document_kind is the circuit and is constant inside the card",
        )

        action = self._asset("receipt_proposal_action.esm.js")
        self.assertIn("  sortCardsByType,\n", action)
        self.assertIn(
            "circuitCards(column, kind) {\n"
            "    return sortCardsByType("
            "column.cards.filter((card) => card.document_kind === kind));",
            action,
            "the circuit's rows go through the type ordering",
        )

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
            "export function methodOptions",
        ):
            self.assertIn(symbol, source, f"{symbol} must be exported")
        # Translation plus the board's own import-free amount parser; no
        # service, no OWL.
        modules = re.findall(r'^import\s*\{[^}]*\}\s*from\s*"([^"]+)";', source, re.M)
        self.assertEqual(
            sorted(modules),
            [
                "@collection_receipt_proposal/receipt_proposal/amount_parser.esm",
                "@web/core/l10n/translation",
            ],
        )
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

    def test_filter_bar_is_paid_once_inside_the_control_panel(self):
        """RED/GREEN: the bar rides the breadcrumb row, not a band of its own.

        The lane's height is what customers are read in, so a control the
        operator sets once MUST NOT be paid once per customer — and it must not
        be paid as a band either. The ControlPanel already draws a row the
        board cannot avoid, and its `layout-actions` slot is the empty half of
        it, so the bar renders there: it costs the board nothing, and the
        ~62px it used to spend between the header and `<main class="board">`
        goes back to the lane. `Limpiar filtros` renders only while something
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
        # And it renders there by being the ControlPanel's layout-actions.
        slot = action.xpath('.//ControlPanel/t[@t-set-slot="layout-actions"]')
        self.assertEqual(len(slot), 1)
        self.assertEqual(
            [node.get("t-call") for node in slot[0].xpath(".//t[@t-call]")],
            ["collection_receipt_proposal.FilterBar"],
        )
        self.assertFalse(
            action.xpath('.//main[@class="board"]/preceding-sibling::t[@t-call]'),
            "nothing may sit between the ControlPanel and the board",
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

        # One wrapping row, and no margin of its own: the ControlPanel owns
        # the spacing now, and the actions region has to give it the width.
        scss = self._asset("receipt_proposal_action.scss")
        rules = scss.split("\n  .rp-filters {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("flex-wrap: wrap", rules)
        self.assertNotIn("flex-direction: column", rules)
        self.assertIn("margin: 0", rules)
        panel = scss.split("\n  > .o_control_panel {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn(".o_control_panel_actions", panel)
        self.assertIn("flex: 1 1 auto", panel)

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

    def test_method_options_are_the_whole_catalog_keyed_on_the_code(self):
        """RED/GREEN: every document type is offered, keyed on `document_type`.

        `method` is the translated label and cannot be indexed on — the payload
        ships the raw code beside it for exactly this reason. The options are
        the company's catalog, not the pool's current contents: built from the
        pool, the `check` option disappeared under the cursor the moment the
        last cheque was assigned. The pool is still walked, so a code the
        catalog no longer names but an old voucher still carries is offered
        too, under the label that voucher's card shows.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn(
            "export function methodOptions(documentTypes, pool) {",
            helpers,
        )
        self.assertIn(
            "options.set(type.code, {code: type.code, label: type.label});", helpers
        )
        self.assertIn("options.has(item.document_type)", helpers)
        self.assertIn(
            "options.set(item.document_type, {code: item.document_type, "
            "label: item.method});",
            helpers,
        )
        self.assertIn("item.document_type === method", helpers)
        # The raw code has to survive the sanitizer for the filter to compare
        # it: the glyph is resolved at the point of drawing, and coercing the
        # payload through `glyphOf` turned every type without a glyph of its
        # own into `unsupported`, which no filter could then name.
        self.assertIn("document_type: sanitizeText(card.document_type),", helpers)
        self.assertIn("document_type: sanitizeText(item.document_type),", helpers)
        self.assertNotIn("glyphOf(sanitizeText(", helpers)

        action = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "return filterPool(this.pool, this.state.filters.method);", action
        )
        self.assertIn("return methodOptions(this.documentTypes, this.pool);", action)
        # A control with nothing to choose between is not drawn at all: a
        # `disabled` select over an empty pool reads as a broken control, which
        # is exactly how it was reported. `canFilterMethod` is the one gate,
        # and the prune below clears a filter the control stops offering.
        self.assertIn(
            "get canFilterMethod() {\n    return this.pool.length > 0 && "
            "this.methodOptions.length > 1;",
            action,
        )
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn('<label class="rp-filter" t-if="canFilterMethod">', xml)
        # No filter control is ever rendered disabled — they hide instead. The
        # one `t-att-disabled` the bar carries belongs to `Restablecer`, which
        # is a mutation, not a filter, and is guarded against a busy board.
        bar = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        bar = bar.xpath('//t[@t-name="collection_receipt_proposal.FilterBar"]')[0]
        disabled = bar.xpath(".//*[@t-att-disabled]")
        self.assertEqual(
            [node.get("class") for node in disabled], ["rp-btn danger rp-reset"]
        )
        self.assertEqual(disabled[0].get("t-att-disabled"), "state.busy")
        xml = self._asset("receipt_proposal_action.xml")
        # The pool column renders the filtered list; the lane is untouched by it.
        self.assertIn('t-foreach="visiblePool"', xml)
        self.assertNotIn('t-foreach="pool"', xml)

    def test_a_method_filter_without_a_control_is_pruned_on_refresh(self):
        """RED/GREEN: emptying the pool clears the filter set on it.

        Every mutation returns a full board, so `applyBoard` is where state
        the board can no longer revert is dropped — `collapsed` and
        `openSplits` already are. The method filter is the only filter whose
        control can stop being drawn: with the pool empty the select is gone
        and a `check` filter would keep hiding cards with nothing to clear it.
        It is pruned against what the control offers, never the raw pool — the
        catalog still names a type whose last voucher was just assigned. The
        search, circuit and sort survive every refresh.
        """
        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "this.canFilterMethod ? this.methodOptions.map("
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

    def test_the_pool_header_is_one_line_like_the_lane_s(self):
        """RED/GREEN: the title and the pending total share one wrapping row.

        Stacked — title, total, chip, drag hint, then a 30px `Restablecer` —
        the head spent five blocks before the first card, in the column whose
        whole question is how many comprobantes are left. The total reads
        label-beside-number against the row's right edge, the button moved to
        the filter bar and the chip went away entirely. The hint stays: it is
        what says the column is draggable.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        pool = root.xpath('//t[@t-name="collection_receipt_proposal.PoolColumn"]')[0]
        row = pool.xpath('.//div[@class="rp-col-title-row"]')[0]
        self.assertEqual(
            [node.get("class") for node in row],
            ["rp-col-title", "rp-col-meta"],
        )
        meta = row.xpath('./div[@class="rp-col-meta"]')[0]
        self.assertEqual(meta.xpath("./em")[0].text.strip(), "Pendiente de asignar")
        self.assertEqual(meta.xpath("./b")[0].get("t-out"), "fmt(poolTotal)")
        # The head is two blocks now: the row and the drag hint.
        head = pool.xpath('.//div[@class="rp-col-head"]')[0]
        self.assertEqual(len(head), 2)
        self.assertEqual(head[1].get("class"), "hint")

        scss = self._asset("receipt_proposal_action.scss")
        meta_rule = scss.split("\n  .rp-col-meta {", 1)[1].split("\n  }\n", 1)[0]
        # Label beside number, like `.rp-lane-meta` — never stacked.
        self.assertIn("display: flex", meta_rule)
        self.assertNotIn("display: block", meta_rule)
        row_rule = scss.split("\n  .rp-col.pool .rp-col-title-row {", 1)[1].split(
            "\n  }\n", 1
        )[0]
        self.assertIn("flex-wrap: wrap", row_rule)
        self.assertIn("display: inline", row_rule, "the count rides the title's line")
        self.assertIn("margin-left: auto", row_rule, "the figure closes the row")

    def test_the_pool_has_no_assignment_chip(self):
        """RED/GREEN: `Requiere asignación` is gone, and nothing replaced it.

        The chip restated the count the title already carries beside it, and
        the one state it named on its own — finished — is what the empty body
        says in words (`Todos los comprobantes están asignados.`). Removing it
        is also what lets the header hold its one line in a narrower column.
        The `Pendiente de asignar` total keeps the rule the chip was written
        for: it follows the filter and names the sheet's own figure beside it,
        so a method filter that renders no card never claims the planilla is
        finished.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        pool = root.xpath('//t[@t-name="collection_receipt_proposal.PoolColumn"]')[0]
        self.assertFalse(pool.xpath('.//*[contains(@t-attf-class, "chip")]'))
        self.assertNotIn("Requiere asignación", "".join(pool.itertext()))
        # The empty body is what tells the operator the column is finished.
        body = pool.xpath('.//div[@class="rp-col-body"]')[0]
        self.assertIn(
            "Todos los comprobantes están asignados.", "".join(body.itertext())
        )

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

    def test_reset_rides_the_filter_bar_and_asks_before_it_empties(self):
        """RED/GREEN: `Restablecer` is a filter-bar button behind a confirmation.

        It is a board-wide action, not a filter, so it sits at the right edge
        of the one row the board already pays for once -- in the pool head it
        was a 30px block on top of the column that is read by counting cards.
        It hides rather than renders dead when there is nothing to return, and
        it never mutates without a modal that names the cards, the customers
        and the money at stake.
        """
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        bar = root.xpath('//t[@t-name="collection_receipt_proposal.FilterBar"]')[0]
        button = bar.xpath('.//button[contains(@class, "rp-reset")]')[0]
        self.assertEqual(button.get("t-if"), "canReset")
        self.assertEqual(button.get("t-on-click"), "openReset")
        self.assertIn("danger", button.get("class"))
        self.assertIn("Restablecer comprobantes", "".join(button.itertext()))
        pool = root.xpath('//t[@t-name="collection_receipt_proposal.PoolColumn"]')[0]
        self.assertFalse(pool.xpath(".//button[@t-on-click='openReset']"))
        scss = self._asset("receipt_proposal_action.scss")
        self.assertNotIn(".rp-col-reset", scss)
        filters = scss.split("\n  .rp-filters {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("margin-left: auto", filters)

        modal = root.xpath('//t[@t-name="collection_receipt_proposal.ResetModal"]')[0]
        text = "".join(modal.itertext())
        self.assertIn("tipo de comprobante", text)
        for figure in ("resetSummary.cards", "resetSummary.customers"):
            self.assertTrue(modal.xpath(f'.//dd[@t-out="{figure}"]'), figure)
        self.assertTrue(modal.xpath('.//dd[@t-out="fmt(resetSummary.amount)"]'))
        confirm = modal.xpath('.//button[@t-on-click="confirmReset"]')[0]
        self.assertEqual(
            confirm.get("t-att-disabled"), "state.busy or resetBlockers.length"
        )

        source = self._asset("receipt_proposal_action.esm.js")
        self.assertIn(
            "return this.editable && this.resetSummary.cards > 0",
            source,
        )
        self.assertIn('"action_proposal_reset_vouchers", [this.sheetId]', source)

    def test_reset_never_returns_a_retention_to_the_pool(self):
        """RED/GREEN: the summary counts exactly what the server will move.

        A retention is tax the customer withheld on their own documents, so
        the server leaves those values where they are -- and a summary that
        counted them would promise money the pool is never going to show.
        """
        helpers = self._asset("receipt_proposal_helpers.esm.js")
        self.assertIn(
            'export const RETENTION_CERTIFICATE = "retention_certificate"', helpers
        )
        self.assertIn("card.document_type !== RETENTION_CERTIFICATE", helpers)
        self.assertNotIn("SELLER_DEPOSIT", helpers)
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn("Las retenciones se quedan donde están.", xml)

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

    def test_client_action_record_has_unique_url_path(self):
        """The board has a named URL distinct from Document Review."""
        action = self.env.ref(
            "collection_receipt_proposal.action_collection_receipt_proposal"
        )
        self.assertEqual(action.type, "ir.actions.client")
        self.assertEqual(action.tag, "collection_receipt_proposal.receipt_proposal")
        self.assertEqual(action.path, "collection-reconciliation")
        self.assertNotEqual(
            action.path,
            self.env.ref("collection.action_collection_document_review").path,
        )

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
