# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon


class TestReceiptProposalRetention(ReceiptProposalCommon, TransactionCase):
    """A retention certificate stays with the customer who withheld it.

    It is tax that customer withheld on their own documents, so the board may
    move it between that customer's two circuits but never onto another
    customer and never back to the unassigned pool -- server-side, for drags
    as well as for the board-wide reset that already leaves it in place.
    """

    def setUp(self):
        super().setUp()
        self.env.company.write(
            {
                "allowed_document_type_ids": [
                    Command.link(
                        self.env.ref(
                            "collection.document_type_retention_certificate"
                        ).id
                    )
                ]
            }
        )
        self.Sheet = self.env["collection.sheet"]
        self.sheet = self._create_sheet(force_new=True)
        self.partner_a = self._partner("RET-A")
        self.partner_b = self._partner("RET-B")
        self.retention = self._create_voucher(
            self.partner_a,
            self.sheet,
            amount=40.0,
            document_type="retention_certificate",
            retention_kind="iva",
        )
        self.transfer = self._create_voucher(self.partner_a, self.sheet, amount=60.0)
        self.voucher_b = self._create_voucher(self.partner_b, self.sheet, amount=100.0)
        self.allocation_a = self._create_allocation(
            self.sheet,
            self.partner_a,
            vouchers=self.retention | self.transfer,
            lines=[
                self._line_vals(invoice_balance=100.0),
                self._line_vals(
                    external_invoice_id="RET-QUO",
                    invoice_number="PRE-RET",
                    invoice_balance=50.0,
                    document_kind="quotation",
                ),
            ],
        )
        self.allocation_b = self._create_allocation(
            self.sheet,
            self.partner_b,
            vouchers=self.voucher_b,
            lines=[
                self._line_vals(external_invoice_id="RET-B", invoice_number="FB-RET")
            ],
        )
        self._confirm(self.sheet)

    def _transfer(self, **kwargs):
        return self.Sheet.action_proposal_transfer(sheet_id=self.sheet.id, **kwargs)

    def _assign_retention(self, document_kind="invoice"):
        self._transfer(
            voucher_id=self.retention.id,
            to_allocation_id=self.allocation_a.id,
            document_kind=document_kind,
            amount=40.0,
        )
        return self.retention.proposal_value_ids

    def test_a_retention_moves_between_its_own_customer_circuits(self):
        value = self._assign_retention()
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 40.0)
        self._transfer(
            value_id=value.id,
            to_allocation_id=self.allocation_a.id,
            document_kind="quotation",
            amount=15.0,
        )
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 25.0)
        self.assertEqual(self.allocation_a.proposal_collected_quotation, 15.0)
        quotation = self.retention.proposal_value_ids.filtered(
            lambda part: part.receipt_id.document_kind == "quotation"
        )
        self.Sheet.action_proposal_set_circuit(
            sheet_id=self.sheet.id, value_id=quotation.id, document_kind="invoice"
        )
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 40.0)

    def test_a_retention_in_the_pool_goes_only_to_its_customer(self):
        with self.assertRaisesRegex(UserError, "retention certificate"):
            self._transfer(
                voucher_id=self.retention.id,
                to_allocation_id=self.allocation_b.id,
                document_kind="invoice",
                amount=40.0,
            )
        self.assertFalse(self.retention.proposal_value_ids)

    def test_a_retention_card_never_moves_to_another_customer(self):
        value = self._assign_retention()
        for amount in (40.0, 10.0):
            with self.assertRaisesRegex(UserError, "retention certificate"):
                self._transfer(
                    value_id=value.id,
                    to_allocation_id=self.allocation_b.id,
                    document_kind="invoice",
                    amount=amount,
                )
        self.assertEqual(value.receipt_id.allocation_id, self.allocation_a)
        self.assertEqual(value.amount, 40.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 0.0)

    def test_a_retention_card_never_returns_to_the_pool(self):
        value = self._assign_retention()
        with self.assertRaisesRegex(UserError, "unassigned pool"):
            self._transfer(value_id=value.id, to_allocation_id=None, amount=40.0)
        self.assertEqual(value.amount, 40.0)

    def test_the_preview_refuses_what_the_move_would_refuse(self):
        value = self._assign_retention()
        with self.assertRaisesRegex(UserError, "retention certificate"):
            self.Sheet.preview_proposal_transfer(
                sheet_id=self.sheet.id,
                value_id=value.id,
                to_allocation_id=self.allocation_b.id,
                document_kind="invoice",
                amount=40.0,
            )

    def test_merging_a_retention_split_keeps_it_on_its_customer(self):
        """A split that predates the rule merges back only onto its customer."""
        receipt_a = self.allocation_a._receipt_get_or_create("invoice")
        receipt_b = self.allocation_b._receipt_get_or_create("invoice")
        part_a = self._create_value(receipt_a, self.retention, 25.0)
        part_b = self._create_value(receipt_b, self.retention, 15.0)
        with self.assertRaisesRegex(UserError, "retention certificate"):
            self.Sheet.action_proposal_undo_split(
                sheet_id=self.sheet.id,
                voucher_id=self.retention.id,
                keep_value_id=part_b.id,
            )
        self.Sheet.action_proposal_undo_split(
            sheet_id=self.sheet.id,
            voucher_id=self.retention.id,
            keep_value_id=part_a.id,
        )
        self.assertEqual(self.retention.proposal_value_ids, part_a)
        self.assertEqual(part_a.amount, 40.0)

    def test_other_payment_types_still_move_between_customers(self):
        self._transfer(
            voucher_id=self.transfer.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=60.0,
        )
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 60.0)
