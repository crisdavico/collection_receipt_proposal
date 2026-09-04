# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon


class TestReceiptProposalOrder(ReceiptProposalCommon, TransactionCase):
    """RED/GREEN: `_proposal_fifo_key` never drifts from `_compute_line_ids`."""

    def _allocation_with_mixed_lines(self):
        sheet = self._create_sheet()
        partner = self._partner("PROP-ORDER")
        voucher = self._create_voucher(partner, sheet, amount=500.0)
        lines = [
            self._line_vals(
                external_invoice_id="ORD-1",
                invoice_number="B-0002",
                due_date=date(2026, 3, 1),
                invoice_balance=50.0,
                amount_applied=50.0,
            ),
            self._line_vals(
                external_invoice_id="ORD-2",
                invoice_number="A-0001",
                due_date=date(2026, 3, 1),
                invoice_balance=50.0,
                amount_applied=50.0,
            ),
            self._line_vals(
                external_invoice_id="ORD-3",
                invoice_number=False,
                due_date=date(2026, 1, 15),
                invoice_balance=50.0,
                amount_applied=50.0,
            ),
            self._line_vals(
                external_invoice_id="ORD-4",
                invoice_number="Z-9999",
                due_date=False,
                invoice_balance=50.0,
                amount_applied=50.0,
            ),
            self._line_vals(
                external_invoice_id="ORD-5",
                invoice_number="M-0500",
                due_date=date(2026, 2, 1),
                invoice_balance=50.0,
                amount_applied=50.0,
            ),
        ]
        allocation = self._create_allocation(sheet, partner, lines=lines)
        self._confirm(sheet)
        return allocation, voucher, sheet

    def test_fifo_key_matches_receipt_line_ids_order(self):
        """RED/GREEN: FIFO order equals the receipt's rendered `line_ids` order."""
        allocation, voucher, _sheet = self._allocation_with_mixed_lines()
        receipt = self._create_receipt(allocation, "invoice")
        self._create_value(receipt, voucher, 250.0)
        self.assertEqual(
            allocation._proposal_kind_lines("invoice").ids,
            receipt.line_ids.ids,
            "FIFO order must be byte-identical to collection.receipt line_ids",
        )

    def test_document_numbers_string_follows_the_same_order(self):
        """RED/GREEN: the stored summary names documents in FIFO order."""
        allocation, voucher, _sheet = self._allocation_with_mixed_lines()
        receipt = self._create_receipt(allocation, "invoice")
        self._create_value(receipt, voucher, 250.0)
        expected = ", ".join(
            line.invoice_number or line.external_invoice_id
            for line in allocation._proposal_kind_lines("invoice")
        )
        self.assertEqual(receipt.document_numbers, expected)

    def test_undated_line_sorts_after_every_dated_line(self):
        """RED/GREEN: `due_date or date.max` puts undated documents last."""
        allocation, _voucher, _sheet = self._allocation_with_mixed_lines()
        ordered = allocation._proposal_kind_lines("invoice")
        self.assertFalse(ordered[-1].due_date)
        self.assertEqual(ordered[-1].external_invoice_id, "ORD-4")

    def test_equal_due_dates_break_on_invoice_number(self):
        """RED/GREEN: same due date orders by `invoice_number or ''`."""
        allocation, _voucher, _sheet = self._allocation_with_mixed_lines()
        numbers = [
            line.invoice_number
            for line in allocation._proposal_kind_lines("invoice")
            if line.due_date == date(2026, 3, 1)
        ]
        self.assertEqual(numbers, ["A-0001", "B-0002"])

    def test_blank_invoice_number_sorts_before_named_ones(self):
        """RED/GREEN: `invoice_number or ''` keeps unnumbered lines first."""
        allocation, _voucher, _sheet = self._allocation_with_mixed_lines()
        key = self.env["collection.allocation"]._proposal_fifo_key
        blank = allocation.line_ids.filtered(
            lambda line: line.external_invoice_id == "ORD-3"
        )
        self.assertEqual(key(blank), (date(2026, 1, 15), ""))

    def test_same_due_date_empty_number_matches_compute_line_ids(self):
        """RED/GREEN: False invoice_number is '' and matches `_compute_line_ids`."""
        sheet = self._create_sheet()
        partner = self._partner("PROP-EMPTY")
        voucher = self._create_voucher(partner, sheet, amount=100.0)
        due = date(2026, 4, 1)
        lines = [
            self._line_vals(
                external_invoice_id="EMP-A",
                invoice_number="A",
                due_date=due,
                invoice_balance=50.0,
                amount_applied=50.0,
            ),
            self._line_vals(
                external_invoice_id="EMP-BLANK",
                invoice_number=False,
                due_date=due,
                invoice_balance=50.0,
                amount_applied=50.0,
            ),
        ]
        allocation = self._create_allocation(sheet, partner, lines=lines)
        self._confirm(sheet)
        receipt = self._create_receipt(allocation, "invoice")
        self._create_value(receipt, voucher, 100.0)
        key = self.env["collection.allocation"]._proposal_fifo_key
        blank = allocation.line_ids.filtered(
            lambda line: line.external_invoice_id == "EMP-BLANK"
        )
        named = allocation.line_ids.filtered(
            lambda line: line.external_invoice_id == "EMP-A"
        )
        self.assertEqual(key(blank), (due, ""))
        self.assertEqual(key(named), (due, "A"))
        fifo_ids = allocation._proposal_kind_lines("invoice").ids
        self.assertEqual(fifo_ids, receipt.line_ids.ids)
        self.assertEqual(fifo_ids, [blank.id, named.id])
