# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon

_EVENT_CONTEXT = "collection_receipt_proposal_event"
_DOCUMENT_KEYS = {
    "line_id",
    "number",
    "issue_date",
    "due_date",
    "amount",
    "balance",
    "applied",
}
_POOL_KEYS = {
    "voucher_id",
    "voucher_name",
    "method",
    "document_type",
    "reference",
    "date",
    "amount",
    "free_amount",
    "partner_id",
    "partner_name",
}
_EVENT_KEYS = {
    "id",
    "allocation_id",
    "voucher_id",
    "event_type",
    "name",
    "description",
    "value_from",
    "value_to",
    "user_name",
    "event_date",
}
_PREVIEW_KEYS = {
    "allocation_id",
    "document_kind",
    "budget",
    "surplus",
    "applied",
    "pending",
    "no_documents",
    "changes",
    "partner_name",
}


class TestReceiptProposalBoard(ReceiptProposalCommon, TransactionCase):
    """RED/GREEN: board payload shape and server-side sheet re-validation."""

    def setUp(self):
        super().setUp()
        self.scenario = self._board_scenario()
        self.sheet = self.scenario["sheet"]
        self.Sheet = self.env["collection.sheet"]

    def _snapshot_money(self):
        values = self.env["collection.receipt.value"].search(
            [("receipt_id.sheet_id", "=", self.sheet.id)]
        )
        lines = self.sheet.allocation_ids.mapped("line_ids")
        events = self.env["collection.receipt.proposal.event"].search(
            [("sheet_id", "=", self.sheet.id)]
        )
        return {
            "values": {value.id: value.amount for value in values},
            "value_ids": set(values.ids),
            "applied": {line.id: line.amount_applied for line in lines},
            "event_ids": set(events.ids),
        }

    def _assert_money_unchanged(self, before):
        self.assertEqual(self._snapshot_money(), before)

    def test_board_payload_shape(self):
        """RED/GREEN: sheet, columns, pool and events are all present."""
        board = self.Sheet.get_proposal_board(self.sheet.id)
        self.assertEqual(set(board), {"sheet", "columns", "pool", "events"})
        self.assertEqual(
            set(board["sheet"]),
            {"id", "name", "state", "currency", "editable"},
        )
        self.assertEqual(board["sheet"]["id"], self.sheet.id)
        self.assertEqual(board["sheet"]["name"], self.sheet.name)
        self.assertEqual(board["sheet"]["state"], "proposal")
        self.assertTrue(board["sheet"]["editable"])
        self.assertEqual(
            set(board["sheet"]["currency"]),
            {"id", "symbol", "position", "decimal_places"},
        )
        self.assertEqual(len(board["columns"]), 2)

    def test_column_payload_shape(self):
        """RED/GREEN: each column carries figures, cards and documents."""
        receipt = self._create_receipt(self.scenario["allocation_a"], "invoice")
        self._create_value(receipt, self.scenario["voucher_a"], 150.0)
        board = self.Sheet.get_proposal_board(self.sheet.id)
        column = next(
            item
            for item in board["columns"]
            if item["allocation_id"] == self.scenario["allocation_a"].id
        )
        self.assertEqual(
            set(column),
            {
                "allocation_id",
                "partner_id",
                "partner_name",
                "partner_vat",
                "closed",
                "note",
                "closed_by",
                "closed_date",
                "status",
                "circuits",
                "cards",
                "documents",
            },
        )
        self.assertEqual(set(column["circuits"]), {"invoice", "quotation"})
        self.assertEqual(
            set(column["circuits"]["invoice"]),
            {"collected", "applied", "available", "total", "pending"},
        )
        self.assertEqual(set(column["documents"]), {"invoice", "quotation"})
        self.assertTrue(column["documents"]["invoice"])
        self.assertEqual(set(column["documents"]["invoice"][0]), _DOCUMENT_KEYS)
        self.assertEqual(column["documents"]["invoice"][0]["number"], "FA-0001")
        self.assertEqual(column["documents"]["invoice"][0]["balance"], 100.0)
        self.assertEqual(len(column["cards"]), 1)
        self.assertEqual(
            set(column["cards"][0]),
            {
                "value_id",
                "voucher_id",
                "voucher_name",
                "method",
                "document_type",
                "reference",
                "date",
                "amount",
                "voucher_amount",
                "document_kind",
                "split_parts",
                "free_amount",
            },
        )

    def test_cards_and_pool_name_the_payment_document_type(self):
        """RED/GREEN: the board reads the type by shape, so it needs the code.

        `method` is the translated label and cannot be keyed on; the glyph
        picker in the OWL client switches on this raw selection code, and both
        card shapes -- the assigned row and the synthetic pool card -- draw it.
        """
        self.env.company.write(
            {
                "allowed_document_type_ids": [
                    Command.link(self.env.ref("collection.document_type_check").id)
                ]
            }
        )
        scenario = self._board_scenario(
            extra_b={
                "document_type": "check",
                "check_bank": "Galicia",
                "check_number": "00012345",
            }
        )
        receipt = self._create_receipt(scenario["allocation_a"], "invoice")
        self._create_value(receipt, scenario["voucher_a"], 150.0)
        board = self.Sheet.get_proposal_board(scenario["sheet"].id)
        column = next(
            item
            for item in board["columns"]
            if item["allocation_id"] == scenario["allocation_a"].id
        )
        self.assertEqual(column["cards"][0]["document_type"], "bank_transfer")
        pool = next(
            item
            for item in board["pool"]
            if item["voucher_id"] == scenario["voucher_b"].id
        )
        self.assertEqual(pool["document_type"], "check")

    def test_documents_are_listed_in_fifo_order(self):
        """RED/GREEN: the board renders documents oldest due date first."""
        board = self.Sheet.get_proposal_board(self.sheet.id)
        column = next(
            item
            for item in board["columns"]
            if item["allocation_id"] == self.scenario["allocation_a"].id
        )
        self.assertEqual(
            [row["number"] for row in column["documents"]["invoice"]],
            ["FA-0001", "FA-0002"],
        )

    def test_pool_lists_only_unassigned_money(self):
        """RED/GREEN: pool cards are synthetic, one per free voucher."""
        board = self.Sheet.get_proposal_board(self.sheet.id)
        self.assertEqual(len(board["pool"]), 2)
        receipt = self._create_receipt(self.scenario["allocation_b"], "invoice")
        self._create_value(receipt, self.scenario["voucher_b"], 100.0)
        board = self.Sheet.get_proposal_board(self.sheet.id)
        voucher_ids = {item["voucher_id"] for item in board["pool"]}
        self.assertNotIn(self.scenario["voucher_b"].id, voucher_ids)

    def test_pool_is_synthetic_for_free_amount_only(self):
        """RED/GREEN: fully assigned vouchers stay off the pool; free 60 stays."""
        receipt_a = self._create_receipt(self.scenario["allocation_a"], "invoice")
        self._create_value(receipt_a, self.scenario["voucher_a"], 300.0)
        receipt_b = self._create_receipt(self.scenario["allocation_b"], "invoice")
        self._create_value(receipt_b, self.scenario["voucher_b"], 40.0)
        board = self.Sheet.get_proposal_board(self.sheet.id)
        self.assertEqual(len(board["columns"]), 2)
        self.assertEqual(len(board["pool"]), 1)
        pool = board["pool"][0]
        self.assertEqual(set(pool), _POOL_KEYS)
        self.assertNotIn("value_id", pool)
        self.assertEqual(pool["voucher_id"], self.scenario["voucher_b"].id)
        self.assertEqual(pool["free_amount"], 60.0)
        self.assertEqual(pool["amount"], 100.0)
        self.assertNotIn(
            self.scenario["voucher_a"].id,
            {item["voucher_id"] for item in board["pool"]},
        )

    def test_event_payload_shape(self):
        """RED/GREEN: events[] carries the board audit keys, newest first."""
        Event = self.env["collection.receipt.proposal.event"]
        older = Event.with_context(**{_EVENT_CONTEXT: True}).create(
            {
                "sheet_id": self.sheet.id,
                "event_type": "assign",
                "name": "Older event",
            }
        )
        newer = Event.with_context(**{_EVENT_CONTEXT: True}).create(
            {
                "sheet_id": self.sheet.id,
                "event_type": "transfer",
                "name": "Newer event",
            }
        )
        board = self.Sheet.get_proposal_board(self.sheet.id)
        self.assertGreaterEqual(len(board["events"]), 2)
        self.assertEqual(set(board["events"][0]), _EVENT_KEYS)
        self.assertEqual(board["events"][0]["id"], newer.id)
        self.assertEqual(board["events"][1]["id"], older.id)
        self.assertEqual(board["events"][0]["event_type"], "transfer")

    def test_require_proposal_sheet_rejects_non_integers(self):
        """RED/GREEN: the injected sheet id is re-validated on every call."""
        for bad in (None, False, True, 0, -1, "1", 1.0):
            with self.assertRaises(UserError):
                self.Sheet.get_proposal_board(bad)

    def test_require_proposal_sheet_rejects_missing_records(self):
        """RED/GREEN: a deleted sheet id is refused."""
        sheet = self._create_sheet(force_new=True)
        sheet_id = sheet.id
        sheet.unlink()
        with self.assertRaises(UserError):
            self.Sheet.get_proposal_board(sheet_id)

    def test_require_proposal_sheet_rejects_other_states(self):
        """RED/GREEN: only `proposal` sheets open the board."""
        open_sheet = self._create_sheet(force_new=True)
        with self.assertRaises(UserError):
            self.Sheet.get_proposal_board(open_sheet.id)
        self._confirm(open_sheet)
        board = self.Sheet.get_proposal_board(open_sheet.id)
        self.assertEqual(board["sheet"]["id"], open_sheet.id)
        open_sheet.action_close()
        with self.assertRaises(UserError):
            self.Sheet.get_proposal_board(open_sheet.id)
        open_sheet.action_cancel()
        with self.assertRaises(UserError):
            self.Sheet.get_proposal_board(open_sheet.id)

    def test_invalid_sheet_id_does_not_mutate(self):
        """RED/GREEN: a refused board RPC leaves receipts and values untouched."""
        receipt = self._create_receipt(self.scenario["allocation_a"], "invoice")
        self._create_value(receipt, self.scenario["voucher_a"], 150.0)
        before = self._snapshot_money()
        for bad in (None, False, True, 0, -1, "1", 1.0):
            with self.assertRaises(UserError):
                self.Sheet.get_proposal_board(bad)
            with self.assertRaises(UserError):
                self.Sheet.preview_proposal_impute(
                    sheet_id=bad,
                    allocation_id=self.scenario["allocation_a"].id,
                    document_kind="invoice",
                )
        self._assert_money_unchanged(before)

    def test_board_refuses_a_user_without_sheet_access(self):
        """RED/GREEN: the RPC surface runs as the caller and never `sudo()`s."""
        portal = self._create_user("proposal_board_portal", "base.group_portal")
        with self.assertRaises(AccessError):
            self.env["collection.sheet"].with_user(portal).get_proposal_board(
                self.sheet.id
            )

    def test_sheet_company_rule_still_guards_the_board(self):
        """RED/GREEN: other-company sheets stay hidden by the global `ir.rule`."""
        self._assert_global_company_rule("collection.sheet")
        user = self._create_user("prop_board_home", "base.group_user")
        self._restrict_user_to_company(user, self.env.company)
        visible = self.Sheet.with_user(user).get_proposal_board(self.sheet.id)
        self.assertEqual(visible["sheet"]["id"], self.sheet.id)

        company_b = self._create_company("Proposal Board Hidden Co")
        seller_b = self._create_user("prop_board_seller_b", "base.group_user")
        sheet_b = self._create_sheet(
            seller_id=seller_b.id, company_id=company_b.id, force_new=True
        )
        self._confirm(sheet_b)
        before = self._snapshot_money()
        try:
            self.Sheet.with_user(user).get_proposal_board(sheet_b.id)
        except (UserError, AccessError):
            pass
        else:
            self.fail("other-company board RPC must refuse")
        self._assert_money_unchanged(before)
        self._assert_hidden_from_user(user, sheet_b, ["name", "id"])

    def test_action_open_receipt_proposal_returns_the_client_action(self):
        """RED/GREEN: the header button injects `sheet_id` into the action."""
        action = self.sheet.action_open_receipt_proposal()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "collection_receipt_proposal.receipt_proposal")
        self.assertEqual(action["params"]["sheet_id"], self.sheet.id)

    def test_action_open_receipt_proposal_refuses_non_proposal_sheets(self):
        """RED/GREEN: the button is unavailable outside `proposal`."""
        open_sheet = self._create_sheet(force_new=True)
        with self.assertRaises(UserError):
            open_sheet.action_open_receipt_proposal()
        self._confirm(open_sheet)
        action = open_sheet.action_open_receipt_proposal()
        self.assertEqual(action["params"]["sheet_id"], open_sheet.id)
        open_sheet.action_close()
        with self.assertRaises(UserError):
            open_sheet.action_open_receipt_proposal()
        open_sheet.action_cancel()
        with self.assertRaises(UserError):
            open_sheet.action_open_receipt_proposal()

    def test_internal_user_reads_the_board_without_sudo(self):
        """RED/GREEN: an allowed internal user reads the board as themselves."""
        user = self._create_user("proposal_board_internal", "base.group_user")
        board = self.Sheet.with_user(user).get_proposal_board(self.sheet.id)
        self.assertEqual(board["sheet"]["id"], self.sheet.id)
        self.assertEqual(len(board["columns"]), 2)

    def test_preview_transfer_does_not_persist(self):
        """RED/GREEN: transfer preview may describe FIFO changes and writes none."""
        receipt = self._create_receipt(self.scenario["allocation_a"], "invoice")
        value = self._create_value(receipt, self.scenario["voucher_a"], 200.0)
        before = self._snapshot_money()
        preview = self.Sheet.preview_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.scenario["allocation_b"].id,
            document_kind="invoice",
            amount=80.0,
        )
        self.assertEqual(len(preview), 2)
        for item in preview:
            self.assertEqual(set(item), _PREVIEW_KEYS)
        self.assertTrue(any(item["changes"] for item in preview))
        self._assert_money_unchanged(before)

    def test_preview_circuit_does_not_persist(self):
        """RED/GREEN: circuit preview does not move the stored card."""
        receipt = self._create_receipt(self.scenario["allocation_a"], "invoice")
        value = self._create_value(receipt, self.scenario["voucher_a"], 120.0)
        before = self._snapshot_money()
        preview = self.Sheet.preview_proposal_circuit(
            sheet_id=self.sheet.id,
            value_id=value.id,
            document_kind="quotation",
        )
        self.assertTrue(preview)
        self.assertEqual(value.receipt_id.document_kind, "invoice")
        self.assertEqual(value.amount, 120.0)
        self._assert_money_unchanged(before)

    def test_preview_undo_split_does_not_persist(self):
        """RED/GREEN: undo-split preview leaves both split parts stored."""
        receipt_a = self._create_receipt(self.scenario["allocation_a"], "invoice")
        receipt_b = self._create_receipt(self.scenario["allocation_b"], "invoice")
        keep = self._create_value(receipt_a, self.scenario["voucher_a"], 200.0)
        other = self._create_value(receipt_b, self.scenario["voucher_a"], 100.0)
        before = self._snapshot_money()
        preview = self.Sheet.preview_proposal_undo_split(
            sheet_id=self.sheet.id,
            voucher_id=self.scenario["voucher_a"].id,
            keep_value_id=keep.id,
        )
        self.assertTrue(preview)
        self.assertTrue(keep.exists())
        self.assertTrue(other.exists())
        self.assertEqual(keep.amount, 200.0)
        self.assertEqual(other.amount, 100.0)
        self._assert_money_unchanged(before)

    def test_preview_impute_does_not_persist(self):
        """RED/GREEN: impute preview describes FIFO and does not write applied."""
        receipt = self._create_receipt(self.scenario["allocation_a"], "invoice")
        self._create_value(receipt, self.scenario["voucher_a"], 200.0)
        before = self._snapshot_money()
        preview = self.Sheet.preview_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.scenario["allocation_a"].id,
            document_kind="invoice",
        )
        self.assertEqual(set(preview), _PREVIEW_KEYS)
        self.assertEqual(preview["allocation_id"], self.scenario["allocation_a"].id)
        self.assertEqual(preview["document_kind"], "invoice")
        self.assertEqual(preview["budget"], 200.0)
        self.assertTrue(preview["changes"])
        self.assertEqual(
            {(item["number"], item["from"], item["to"]) for item in preview["changes"]},
            {("FA-0001", 0.0, 100.0), ("FA-0002", 0.0, 100.0)},
        )
        self._assert_money_unchanged(before)
        self.scenario["allocation_a"]._proposal_recompute("invoice")
        aligned = self._snapshot_money()
        second = self.Sheet.preview_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.scenario["allocation_a"].id,
            document_kind="invoice",
        )
        self.assertEqual(second["changes"], [])
        self._assert_money_unchanged(aligned)

    def _replaced_cash_setup(self, cash_amount=100.0, replace_amount=100.0):
        sheet = self._create_sheet(force_new=True)
        partner = self._partner("REPL-POOL")
        cash = self._create_voucher(
            partner, sheet, amount=cash_amount, document_type="cash"
        )
        # Confirm validates every sheet voucher, so the U5b write-hook
        # replaces cash by this deposit amount. Size it to the intended
        # replace; a post-confirm _cash_replace would double-count.
        deposit = self._create_seller_deposit(sheet, amount=replace_amount)
        allocation = self._create_allocation(
            sheet,
            partner,
            vouchers=cash,
            lines=[self._line_vals(invoice_balance=cash_amount)],
        )
        receipt = self._create_receipt(allocation, "invoice")
        cash_value = self._create_value(receipt, cash, cash_amount)
        self._confirm(sheet)
        return sheet, cash, deposit, allocation, receipt, cash_value

    def test_replaced_cash_leaves_the_pool(self):
        """A cash voucher whose replaced_amount equals amount MUST leave the pool."""
        sheet, cash, _deposit, _allocation, _receipt, _cash_value = (
            self._replaced_cash_setup(cash_amount=100.0, replace_amount=100.0)
        )
        cash.invalidate_recordset()
        self.assertAlmostEqual(cash.replaced_amount, 100.0, places=2)
        self.assertAlmostEqual(cash.proposal_assigned_amount, 0.0, places=2)
        self.assertAlmostEqual(cash.proposal_free_amount, 0.0, places=2)
        board = self.Sheet.get_proposal_board(sheet.id)
        pool_ids = {item["voucher_id"] for item in board["pool"]}
        self.assertNotIn(cash.id, pool_ids)

    def test_partial_replace_remains_only_for_the_free_remainder(self):
        """Amount 100, assigned 0, replaced 40 MUST appear in the pool only for 60."""
        sheet, cash, _deposit, _allocation, receipt, _cash_value = (
            self._replaced_cash_setup(cash_amount=100.0, replace_amount=40.0)
        )
        remaining = receipt.value_ids.filtered(lambda value: value.voucher_id == cash)
        self.assertTrue(remaining, "partial replace must leave a cash remainder")
        remaining.unlink()
        cash.invalidate_recordset()
        self.assertAlmostEqual(cash.replaced_amount, 40.0, places=2)
        self.assertAlmostEqual(cash.proposal_assigned_amount, 0.0, places=2)
        self.assertAlmostEqual(cash.proposal_free_amount, 60.0, places=2)
        board = self.Sheet.get_proposal_board(sheet.id)
        pool = {item["voucher_id"]: item for item in board["pool"]}
        self.assertIn(cash.id, pool)
        self.assertAlmostEqual(pool[cash.id]["free_amount"], 60.0, places=2)

    def test_excess_deposit_is_not_a_pool_card(self):
        """Unassigned seller_deposit MUST NOT appear in the unassigned pool."""
        sheet = self._create_sheet(force_new=True)
        partner = self._partner("EXCESS-DEP")
        deposit = self._create_seller_deposit(sheet, amount=80.0)
        self._create_allocation(
            sheet, partner, lines=[self._line_vals(invoice_balance=80.0)]
        )
        self._confirm(sheet)
        self.assertGreater(deposit.proposal_free_amount, 0.0)
        board = self.Sheet.get_proposal_board(sheet.id)
        pool_ids = {item["voucher_id"] for item in board["pool"]}
        self.assertNotIn(deposit.id, pool_ids)
