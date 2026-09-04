# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger

from .common import ReceiptProposalCommon


class TestReceiptProposalSplit(ReceiptProposalCommon, TransactionCase):
    """RED/GREEN: cross-customer splits, the sheet-wide cap, unify, undo."""

    def setUp(self):
        super().setUp()
        self.scenario = self._board_scenario()
        self.sheet = self.scenario["sheet"]
        self.voucher = self.scenario["voucher_a"]
        self.allocation_a = self.scenario["allocation_a"]
        self.allocation_b = self.scenario["allocation_b"]

    def test_cross_customer_split_is_accepted_within_a_sheet(self):
        """RED/GREEN: one voucher may back two customers of the same sheet."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        value_a = self._create_value(receipt_a, self.voucher, 200.0)
        value_b = self._create_value(receipt_b, self.voucher, 100.0)
        self.assertTrue(value_a.exists())
        self.assertTrue(value_b.exists())
        self.assertEqual(value_a.receipt_id.sheet_id, self.sheet)
        self.assertEqual(value_b.receipt_id.sheet_id, self.sheet)
        self.assertEqual(value_a.voucher_id.sheet_id, self.sheet)
        self.assertNotEqual(
            value_a.receipt_id.allocation_id, value_b.receipt_id.allocation_id
        )
        self.assertEqual(self.voucher.proposal_assigned_amount, 300.0)
        self.assertEqual(self.voucher.proposal_free_amount, 0.0)
        self.assertTrue(self.voucher.proposal_is_split)

    def test_split_across_sheets_is_rejected(self):
        """RED/GREEN: the boundary moves from allocation to sheet, not further."""
        other_sheet = self._create_sheet(force_new=True, company_id=self.env.company.id)
        partner = self._partner("PROP-OTHER")
        other_voucher = self._create_voucher(partner, other_sheet, amount=100.0)
        receipt = self._create_receipt(self.allocation_a, "invoice")
        Value = self.env["collection.receipt.value"]
        before_ids = set(Value.search([]).ids)
        with self.assertRaises(ValidationError):
            self._create_value(receipt, other_voucher, 50.0)
        self.assertEqual(set(Value.search([]).ids), before_ids)
        self.assertFalse(Value.search([("voucher_id", "=", other_voucher.id)]))

    def test_unique_receipt_voucher_still_holds(self):
        """RED/GREEN: UNIQUE(receipt, voucher) still refuses a second row."""
        receipt = self._create_receipt(self.allocation_a, "invoice")
        first = self._create_value(receipt, self.voucher, 40.0)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self._create_value(receipt, self.voucher, 10.0)
        self.assertEqual(first.amount, 40.0)
        self.assertEqual(
            len(
                self.env["collection.receipt.value"].search(
                    [
                        ("receipt_id", "=", receipt.id),
                        ("voucher_id", "=", self.voucher.id),
                    ]
                )
            ),
            1,
        )

    def test_zero_and_negative_amount_are_rejected(self):
        """RED/GREEN: amount > 0 still holds after the sheet-scope split relax."""
        invoice = self._create_receipt(self.allocation_a, "invoice")
        quotation = self._create_receipt(self.allocation_a, "quotation")
        kept = self._create_value(invoice, self.voucher, 40.0)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self._create_value(quotation, self.voucher, 0.0)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self._create_value(quotation, self.voucher, -5.0)
        self.assertEqual(kept.amount, 40.0)
        self.assertFalse(quotation.value_ids)

    def test_sheet_wide_split_cap_is_enforced(self):
        """RED/GREEN: a voucher cannot be over-split across customers."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        first = self._create_value(receipt_a, self.voucher, 200.0)
        with self.assertRaises(ValidationError):
            self._create_value(receipt_b, self.voucher, 150.0)
        self.assertEqual(first.amount, 200.0)
        self.assertFalse(
            self.env["collection.receipt.value"].search(
                [
                    ("receipt_id", "=", receipt_b.id),
                    ("voucher_id", "=", self.voucher.id),
                ]
            )
        )

    def test_at_cap_across_customers_persists(self):
        """RED/GREEN: summing to the voucher amount across customers is allowed."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        value_a = self._create_value(receipt_a, self.voucher, 120.0)
        value_b = self._create_value(receipt_b, self.voucher, 180.0)
        self.assertEqual(value_a.amount, 120.0)
        self.assertEqual(value_b.amount, 180.0)
        self.assertEqual(self.voucher.proposal_assigned_amount, 300.0)
        self.assertEqual(self.voucher.proposal_free_amount, 0.0)

    def test_over_cap_across_three_customers_is_refused(self):
        """RED/GREEN: the cap sums every value of the voucher, not one allocation."""
        voucher = self.scenario["voucher_b"]
        partner_c = self._partner("PROP-C")
        allocation_c = self._create_allocation(
            self.sheet,
            partner_c,
            lines=[
                self._line_vals(
                    external_invoice_id="C-ONE",
                    invoice_number="FC-0001",
                    invoice_balance=50.0,
                )
            ],
        )
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        receipt_c = self._create_receipt(allocation_c, "invoice")
        first = self._create_value(receipt_a, voucher, 40.0)
        second = self._create_value(receipt_b, voucher, 50.0)
        with self.assertRaises(ValidationError):
            self._create_value(receipt_c, voucher, 20.0)
        self.assertEqual(first.amount, 40.0)
        self.assertEqual(second.amount, 50.0)
        self.assertFalse(
            self.env["collection.receipt.value"].search(
                [("receipt_id", "=", receipt_c.id)]
            )
        )

    def test_proposal_amounts_unassigned_partial_and_split(self):
        """RED/GREEN: assigned, free, and is_split follow the voucher's value rows."""
        self.assertEqual(self.voucher.proposal_assigned_amount, 0.0)
        self.assertEqual(self.voucher.proposal_free_amount, 300.0)
        self.assertFalse(self.voucher.proposal_is_split)
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        self._create_value(receipt_a, self.voucher, 120.0)
        self.assertEqual(self.voucher.proposal_assigned_amount, 120.0)
        self.assertEqual(self.voucher.proposal_free_amount, 180.0)
        self.assertFalse(self.voucher.proposal_is_split)
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        self._create_value(receipt_b, self.voucher, 80.0)
        self.assertEqual(self.voucher.proposal_assigned_amount, 200.0)
        self.assertEqual(self.voucher.proposal_free_amount, 100.0)
        self.assertTrue(self.voucher.proposal_is_split)

    def test_proposal_card_label_for_transfer_and_check(self):
        """RED/GREEN: card labels use the type selection plus the type-specific ref."""
        open_sheet = self._create_sheet(force_new=True)
        partner = self._partner("PROP-LABEL")
        transfer = self._create_voucher(
            partner,
            open_sheet,
            amount=50.0,
            voucher_number="TR-99",
        )
        label = transfer._proposal_card_label()
        self.assertEqual(label["method"], "Bank Transfer")
        self.assertEqual(label["reference"], "TR-99")
        transfer.voucher_number = False
        transfer.from_account = "ACC-1"
        label = transfer._proposal_card_label()
        self.assertEqual(label["method"], "Bank Transfer")
        self.assertEqual(label["reference"], "ACC-1")
        check = self._create_voucher(
            partner,
            open_sheet,
            amount=50.0,
            document_type="check",
            check_bank="Banco Nación",
            check_number="12345",
        )
        label = check._proposal_card_label()
        self.assertEqual(label["method"], "Check")
        self.assertEqual(label["reference"], "Banco Nación 12345")
        unnamed_ref = self._create_voucher(partner, open_sheet, amount=10.0)
        label = unnamed_ref._proposal_card_label()
        self.assertEqual(label["reference"], unnamed_ref.name)

    def test_split_cap_also_guards_a_later_amount_write(self):
        """RED/GREEN: raising an existing card past the voucher total raises."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        first = self._create_value(receipt_a, self.voucher, 200.0)
        self._create_value(receipt_b, self.voucher, 100.0)
        with self.assertRaises(ValidationError):
            first.amount = 250.0

    def test_split_across_the_two_circuits_of_one_customer(self):
        """RED/GREEN: the same voucher may fund both circuits of a customer."""
        invoice = self._create_receipt(self.allocation_a, "invoice")
        quotation = self._create_receipt(self.allocation_a, "quotation")
        self._create_value(invoice, self.voucher, 200.0)
        self._create_value(quotation, self.voucher, 100.0)
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 200.0)
        self.assertEqual(self.allocation_a.proposal_collected_quotation, 100.0)

    def test_transfer_splits_a_card_between_two_customers(self):
        """RED/GREEN: the board's transfer keeps the sheet-wide total intact."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        value = self._create_value(receipt_a, self.voucher, 300.0)
        self.env["collection.sheet"].action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=100.0,
        )
        self.assertEqual(self.voucher.proposal_assigned_amount, 300.0)
        self.assertEqual(len(self.voucher.proposal_value_ids), 2)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 100.0)

    def test_transfer_above_the_card_amount_is_refused(self):
        """RED/GREEN: the transferred amount is capped at the source card."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        value = self._create_value(receipt_a, self.voucher, 300.0)
        with self.assertRaises(UserError):
            self.env["collection.sheet"].action_proposal_transfer(
                sheet_id=self.sheet.id,
                value_id=value.id,
                to_allocation_id=self.allocation_b.id,
                document_kind="invoice",
                amount=400.0,
            )

    def test_transfer_merges_into_an_existing_card(self):
        """RED/GREEN: `unify` collapses two parts back into one card."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        source = self._create_value(receipt_a, self.voucher, 200.0)
        self._create_value(receipt_b, self.voucher, 100.0)
        self.env["collection.sheet"].action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=source.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            unify=True,
        )
        self.assertEqual(len(self.voucher.proposal_value_ids), 1)
        self.assertEqual(self.voucher.proposal_assigned_amount, 300.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 300.0)

    def test_undo_split_reunifies_on_the_kept_card(self):
        """RED/GREEN: undo split leaves one card holding the whole share."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        keep = self._create_value(receipt_a, self.voucher, 200.0)
        self._create_value(receipt_b, self.voucher, 100.0)
        self.env["collection.sheet"].action_proposal_undo_split(
            sheet_id=self.sheet.id,
            voucher_id=self.voucher.id,
            keep_value_id=keep.id,
        )
        self.assertEqual(len(self.voucher.proposal_value_ids), 1)
        self.assertEqual(keep.amount, 300.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 0.0)

    def test_undo_split_refuses_an_unsplit_voucher(self):
        """RED/GREEN: undo split needs at least two parts."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        keep = self._create_value(receipt_a, self.voucher, 300.0)
        with self.assertRaises(UserError):
            self.env["collection.sheet"].action_proposal_undo_split(
                sheet_id=self.sheet.id,
                voucher_id=self.voucher.id,
                keep_value_id=keep.id,
            )

    def test_voucher_owner_follows_overall_largest_share(self):
        """RED/GREEN: 30 on A then 70 on B re-points `allocation_id` to B."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        receipt_b = self._create_receipt(self.allocation_b, "invoice")
        self.voucher.allocation_id = False
        self._create_value(receipt_a, self.voucher, 30.0)
        self.sheet._proposal_sync_voucher_owner(self.voucher)
        self.assertEqual(self.voucher.allocation_id, self.allocation_a)
        self._create_value(receipt_b, self.voucher, 70.0)
        self.sheet._proposal_sync_voucher_owner(self.voucher)
        self.assertEqual(self.voucher.allocation_id, self.allocation_b)

    def test_pool_reports_the_unassigned_remainder(self):
        """RED/GREEN: the pool card carries the voucher's free amount."""
        receipt_a = self._create_receipt(self.allocation_a, "invoice")
        self._create_value(receipt_a, self.voucher, 120.0)
        board = self.env["collection.sheet"].get_proposal_board(self.sheet.id)
        pool = {item["voucher_id"]: item for item in board["pool"]}
        self.assertIn(self.voucher.id, pool)
        self.assertEqual(pool[self.voucher.id]["free_amount"], 180.0)
