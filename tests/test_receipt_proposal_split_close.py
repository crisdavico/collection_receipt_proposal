# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""A board that splits money across customers MUST still close and print right.

The board points ``voucher.allocation_id`` at the largest share only, and never
at a remittance, so core reads collected money from receipt values instead.
"""

from datetime import date

from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon


class TestReceiptProposalSplitClose(ReceiptProposalCommon, TransactionCase):
    def setUp(self):
        super().setUp()
        self.Sheet = self.env["collection.sheet"]
        sheet = self._create_sheet(force_new=True)
        self.partner_a = self._partner("SPLIT-CLOSE-A")
        self.partner_b = self._partner("SPLIT-CLOSE-B")
        self.partner_c = self._partner("SPLIT-CLOSE-C")
        self.voucher = self._create_voucher(self.partner_a, sheet, amount=100.0)
        # No cash on the sheet, so approval replaces nothing: the whole
        # remittance stays free and lands in the unassigned pool.
        self.deposit = self._create_seller_deposit(sheet, amount=30.0)
        self.allocation_a = self._create_allocation(
            sheet,
            self.partner_a,
            vouchers=self.voucher,
            lines=[self._customer_line("SC-A")],
        )
        self.allocation_b = self._create_allocation(
            sheet, self.partner_b, lines=[self._customer_line("SC-B")]
        )
        self.allocation_c = self._create_allocation(
            sheet, self.partner_c, lines=[self._customer_line("SC-C")]
        )
        self.sheet = self._confirm(sheet)

    def _customer_line(self, number):
        return self._line_vals(
            external_invoice_id=number,
            invoice_number=number,
            due_date=date(2026, 1, 15),
            invoice_balance=100.0,
        )

    def _transfer(self, **kwargs):
        return self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id, document_kind="invoice", **kwargs
        )

    def _split_on_the_board(self):
        self._transfer(
            voucher_id=self.voucher.id,
            to_allocation_id=self.allocation_a.id,
            amount=100.0,
        )
        self._transfer(
            value_id=self.voucher.proposal_value_ids.id,
            to_allocation_id=self.allocation_b.id,
            amount=40.0,
        )
        self._transfer(
            voucher_id=self.deposit.id,
            to_allocation_id=self.allocation_c.id,
            amount=30.0,
        )

    def test_board_split_applies_each_share(self):
        self._split_on_the_board()
        self.assertEqual(self.allocation_a.total_applied, 60.0)
        self.assertEqual(self.allocation_b.total_applied, 40.0)
        self.assertEqual(self.allocation_c.total_applied, 30.0)
        self.assertEqual(self.voucher.allocation_id, self.allocation_a)
        self.assertFalse(self.deposit.allocation_id)

    def test_board_split_sheet_closes(self):
        self._split_on_the_board()
        self.sheet.action_close()
        self.assertEqual(self.sheet.state, "closed")

    def test_planilla_prints_each_customer_share_after_close(self):
        self._split_on_the_board()
        self.sheet.action_close()
        collected = {
            row["name"]: row["collected"]
            for row in self.sheet._collection_report_data()["customers"]
        }
        self.assertEqual(
            collected,
            {"SPLIT-CLOSE-A": 60.0, "SPLIT-CLOSE-B": 40.0, "SPLIT-CLOSE-C": 30.0},
        )
