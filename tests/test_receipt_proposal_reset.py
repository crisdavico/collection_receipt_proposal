# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon


class TestReceiptProposalReset(ReceiptProposalCommon, TransactionCase):
    """Reset to Open reopens the customers closed on the board."""

    def test_reset_to_open_reopens_board_closures(self):
        scenario = self._board_scenario()
        sheet = scenario["sheet"]
        allocation = scenario["allocation_b"]
        Sheet = self.env["collection.sheet"]
        Sheet.action_proposal_transfer(
            sheet_id=sheet.id,
            voucher_id=scenario["voucher_b"].id,
            to_allocation_id=allocation.id,
            document_kind="invoice",
            amount=80.0,
        )
        Sheet.action_proposal_close_customer(
            sheet_id=sheet.id, allocation_id=allocation.id
        )
        self.assertTrue(allocation.proposal_closed)
        sheet.action_reset_to_open()
        self.assertEqual(sheet.state, "open")
        self.assertFalse(allocation.proposal_closed)
        self.assertFalse(allocation.proposal_closed_uid)
        self.assertFalse(allocation.proposal_closed_date)
