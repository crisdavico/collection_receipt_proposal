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
        """RED/GREEN: board, column, card, menu, modals and drawer templates."""
        root = etree.fromstring(self._asset("receipt_proposal_action.xml").encode())
        names = {node.get("t-name") for node in root.xpath("//t[@t-name]")}
        self.assertEqual(
            {
                "collection_receipt_proposal.ReceiptProposalAction",
                "collection_receipt_proposal.PoolColumn",
                "collection_receipt_proposal.CustomerColumn",
                "collection_receipt_proposal.CircuitLine",
                "collection_receipt_proposal.Card",
                "collection_receipt_proposal.ContextMenu",
                "collection_receipt_proposal.PreviewPanel",
                "collection_receipt_proposal.TransferModal",
                "collection_receipt_proposal.CircuitModal",
                "collection_receipt_proposal.UndoSplitModal",
                "collection_receipt_proposal.ImputeModal",
                "collection_receipt_proposal.CloseModal",
                "collection_receipt_proposal.Drawer",
            },
            names,
        )

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

    def test_whole_column_is_the_drop_target(self):
        """RED/GREEN: columns fill the board, so empty space still accepts drops.

        With `align-items: flex-start` a short column is only as tall as its
        cards, and the empty space under it is outside the `<section>` that
        carries `t-on-drop` — the operator has to aim at the cards.
        """
        scss = self._asset("receipt_proposal_action.scss")
        board = scss.split("\n  .board {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("align-items: stretch", board)
        self.assertNotIn("align-items: flex-start", board)
        column = scss.split("\n  .rp-col {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("height: 100%", column)
        xml = self._asset("receipt_proposal_action.xml")
        self.assertIn("onColumnDragOver(ev, column)", xml)
        self.assertIn("onColumnDragOver(ev, null)", xml)
        self.assertIn("t-on-dragleave", xml)

    def test_collapsed_column_is_a_vertical_rail(self):
        """RED/GREEN: collapsing rotates the title instead of squashing it."""
        scss = self._asset("receipt_proposal_action.scss")
        collapsed = scss.split("\n  .rp-col.collapsed {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("writing-mode: vertical-rl", collapsed)
        self.assertIn(".detail-btn", collapsed)
        self.assertIn("width: 56px", collapsed)

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
            "flex-basis: 86vw",
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
