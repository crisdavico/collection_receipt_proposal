# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon

CONFIRM_KEY = "receipt_proposal_confirm_close"
WIZARD = "collection.sheet.close.confirm"


class TestReceiptProposalCloseConfirm(ReceiptProposalCommon, TransactionCase):
    """Close warns about an unfinished board, and a manager may go on (D7).

    The sheet form's Close button asks for the confirmation step; it lists
    the money still in the unassigned pool and the customers not closed on
    the board. It is a UX confirmation, not a guard: Close itself still
    requires a Collections Manager, and every other caller of ``action_close``
    (raw state writes, scripts, other modules) closes exactly as before.
    """

    def setUp(self):
        super().setUp()
        scenario = self._board_scenario()
        self.sheet = scenario["sheet"]
        self.allocation_a = scenario["allocation_a"]
        self.allocation_b = scenario["allocation_b"]
        self.partner_a = scenario["partner_a"]
        self.partner_b = scenario["partner_b"]
        self.voucher_a = scenario["voucher_a"]
        self.voucher_b = scenario["voucher_b"]
        self.Sheet = self.env["collection.sheet"]

    def _close_from_the_button(self, sheet=None):
        return (sheet or self.sheet).with_context(**{CONFIRM_KEY: True}).action_close()

    def _assign_everything(self):
        for allocation, voucher in (
            (self.allocation_a, self.voucher_a),
            (self.allocation_b, self.voucher_b),
        ):
            self.Sheet.action_proposal_transfer(
                sheet_id=self.sheet.id,
                voucher_id=voucher.id,
                to_allocation_id=allocation.id,
                document_kind="invoice",
                amount=voucher.amount,
            )

    def _close_customer(self, allocation):
        self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id, allocation_id=allocation.id, note="Checked."
        )

    def _wizard(self, action):
        self.assertIsInstance(action, dict)
        self.assertEqual(action["res_model"], WIZARD)
        self.assertEqual(action["target"], "new")
        return self.env[WIZARD].browse(action["res_id"])

    def test_an_unfinished_board_asks_before_closing(self):
        action = self._close_from_the_button()
        self.assertEqual(self.sheet.state, "proposal")
        wizard = self._wizard(action)
        self.assertEqual(wizard.sheet_id, self.sheet)
        self.assertEqual(wizard.pool_count, 2)
        self.assertAlmostEqual(wizard.pool_amount, 400.0, places=2)
        self.assertEqual(wizard.open_customer_count, 2)
        self.assertIn(self.partner_a.display_name, wizard.open_customer_names)
        self.assertIn(self.partner_b.display_name, wizard.open_customer_names)

    def test_confirming_closes_the_sheet(self):
        wizard = self._wizard(self._close_from_the_button())
        result = wizard.action_confirm_close()
        self.assertEqual(self.sheet.state, "closed")
        self.assertEqual(result, {"type": "ir.actions.act_window_close"})

    def test_a_finished_board_closes_without_asking(self):
        self._assign_everything()
        self._close_customer(self.allocation_a)
        self._close_customer(self.allocation_b)
        result = self._close_from_the_button()
        self.assertIs(result, True)
        self.assertEqual(self.sheet.state, "closed")

    def test_the_summary_lists_only_what_is_still_pending(self):
        self._assign_everything()
        self._close_customer(self.allocation_a)
        wizard = self._wizard(self._close_from_the_button())
        self.assertEqual(wizard.pool_count, 0)
        self.assertAlmostEqual(wizard.pool_amount, 0.0, places=2)
        self.assertEqual(wizard.open_customer_count, 1)
        self.assertIn(self.partner_b.display_name, wizard.open_customer_names)
        self.assertNotIn(self.partner_a.display_name, wizard.open_customer_names)

    def test_money_left_in_the_pool_alone_still_asks(self):
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            voucher_id=self.voucher_a.id,
            to_allocation_id=self.allocation_a.id,
            document_kind="invoice",
            amount=250.0,
        )
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            voucher_id=self.voucher_b.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=100.0,
        )
        self._close_customer(self.allocation_a)
        self._close_customer(self.allocation_b)
        wizard = self._wizard(self._close_from_the_button())
        self.assertEqual(wizard.pool_count, 1)
        self.assertAlmostEqual(wizard.pool_amount, 50.0, places=2)
        self.assertEqual(wizard.open_customer_count, 0)

    def test_close_without_the_button_flag_is_unchanged(self):
        """Raw state writes and other callers never get a dialog back."""
        self.assertIs(self.sheet.action_close(), True)
        self.assertEqual(self.sheet.state, "closed")

    def test_a_user_without_collection_role_is_refused_before_any_summary(self):
        user = self._create_user("close-confirm-plain", "base.group_user")
        with self.assertRaises(AccessError):
            self._close_from_the_button(self.sheet.with_user(user))
        self.assertEqual(self.sheet.state, "proposal")

    def test_a_collections_user_confirms_and_closes(self):
        user = self._create_user(
            "close-confirm-user", "collection.group_collection_user"
        )
        wizard = self._wizard(self._close_from_the_button(self.sheet.with_user(user)))
        self.assertEqual(self.sheet.state, "proposal")
        wizard.with_user(user).action_confirm_close()
        self.assertEqual(self.sheet.state, "closed")

    def test_collections_users_may_open_the_confirmation(self):
        access = self.env["ir.model.access"].search([("model_id.model", "=", WIZARD)])
        self.assertEqual(len(access), 1)
        self.assertEqual(
            access.group_id, self.env.ref("collection.group_collection_user")
        )

    def test_the_sheet_form_close_button_asks_for_the_confirmation(self):
        view = self.env.ref("collection.view_collection_sheet_form")
        arch = self.Sheet.get_view(view.id, "form")["arch"]
        buttons = etree.fromstring(arch).xpath(
            '//header/button[@name="action_close"][@type="object"]'
        )
        self.assertEqual(len(buttons), 1)
        self.assertIn(CONFIRM_KEY, buttons[0].get("context") or "")
