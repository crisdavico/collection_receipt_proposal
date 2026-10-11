# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.tests import TransactionCase

from odoo.addons.collection.models.collection_common import privileged
from odoo.addons.collection_receipt_proposal.models.collection_allocation import (
    PROPOSAL_CLOSE_SCOPE,
)

from .common import ReceiptProposalCommon


def _force_closed(allocation):
    """Mark the customer closed without the board's note and event rules."""
    with privileged(PROPOSAL_CLOSE_SCOPE):
        allocation.proposal_closed = True


class TestReceiptProposalFifo(ReceiptProposalCommon, TransactionCase):
    """RED/GREEN: FIFO plan, preview, recompute and their invariants."""

    def setUp(self):
        super().setUp()
        self.scenario = self._board_scenario()
        self.sheet = self.scenario["sheet"]
        self.allocation = self.scenario["allocation_a"]
        self.voucher = self.scenario["voucher_a"]

    def _fund(self, allocation, voucher, amount, document_kind="invoice"):
        receipt = allocation._proposal_receipt(document_kind) or self._create_receipt(
            allocation, document_kind
        )
        self._create_value(receipt, voucher, amount)
        return receipt

    def _applied(self, allocation, document_kind="invoice"):
        return [
            (line.invoice_number, line.amount_applied)
            for line in allocation._proposal_kind_lines(document_kind)
        ]

    def test_plan_fills_oldest_first_and_splits_the_last_document(self):
        """RED/GREEN: FIFO fills the oldest due date first, partial on the last."""
        self._fund(self.allocation, self.voucher, 150.0)
        self.allocation._proposal_recompute("invoice")
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 100.0), ("FA-0002", 50.0)],
        )

    def test_recompute_is_idempotent(self):
        """RED/GREEN: recomputing twice changes nothing the second time."""
        self._fund(self.allocation, self.voucher, 150.0)
        self.allocation._proposal_recompute("invoice")
        second = self.allocation._proposal_recompute("invoice")
        self.assertEqual(second["changes"], [])
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 100.0), ("FA-0002", 50.0)],
        )

    def test_ceiling_is_invoice_balance_not_invoice_amount(self):
        """RED/GREEN: each document absorbs up to `invoice_balance` only."""
        oldest = self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0001"
        )
        oldest.write({"invoice_amount": 1000.0, "invoice_balance": 40.0})
        self._fund(self.allocation, self.voucher, 100.0)
        self.allocation._proposal_recompute("invoice")
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 40.0), ("FA-0002", 60.0)],
        )

    def test_ceiling_spec_amounts_ignore_invoice_amount(self):
        """RED/GREEN: budget 100, amount 80/balance 50, next balance 60 → 50+50."""
        oldest = self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0001"
        )
        newest = self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0002"
        )
        oldest.write({"invoice_amount": 80.0, "invoice_balance": 50.0})
        newest.write({"invoice_balance": 60.0})
        self._fund(self.allocation, self.voucher, 100.0)
        self.allocation._proposal_recompute("invoice")
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 50.0), ("FA-0002", 50.0)],
        )

    def test_partial_fill_on_a_single_document(self):
        """RED/GREEN: budget below one document's balance fills that doc partially."""
        allocation = self.scenario["allocation_b"]
        self._fund(allocation, self.scenario["voucher_b"], 30.0)
        allocation._proposal_recompute("invoice")
        self.assertEqual(self._applied(allocation), [("FB-0001", 30.0)])

    def test_undated_documents_sort_last(self):
        """RED/GREEN: a document without a due date is served last."""
        self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0001"
        ).due_date = False
        self._fund(self.allocation, self.voucher, 120.0)
        self.allocation._proposal_recompute("invoice")
        applied = dict(self._applied(self.allocation))
        self.assertEqual(applied["FA-0002"], 100.0)
        self.assertEqual(applied["FA-0001"], 20.0)

    def test_surplus_is_reported_and_stays_on_account(self):
        """RED/GREEN: money the documents cannot absorb becomes surplus."""
        self._fund(self.allocation, self.voucher, 300.0)
        preview = self.allocation._proposal_recompute("invoice")
        self.assertEqual(preview["surplus"], 100.0)
        self.assertEqual(preview["applied"], 200.0)
        receipt = self.allocation._proposal_receipt("invoice")
        self.assertEqual(receipt.amount_on_account, 100.0)

    def test_surplus_when_budget_exceeds_all_balances(self):
        """RED/GREEN: budget 80 against balances totaling 50 leaves surplus 30."""
        oldest = self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0001"
        )
        newest = self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0002"
        )
        oldest.invoice_balance = 30.0
        newest.invoice_balance = 20.0
        self._fund(self.allocation, self.voucher, 80.0)
        preview = self.allocation._proposal_recompute("invoice")
        self.assertEqual(preview["applied"], 50.0)
        self.assertEqual(preview["surplus"], 30.0)
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 30.0), ("FA-0002", 20.0)],
        )

    def test_no_documents_is_flagged(self):
        """RED/GREEN: collected money with no documents flags `no_documents`."""
        allocation = self.scenario["allocation_b"]
        self._fund(
            allocation, self.scenario["voucher_b"], 60.0, document_kind="quotation"
        )
        preview = allocation._proposal_preview("quotation")
        self.assertTrue(preview["no_documents"])
        self.assertEqual(preview["applied"], 0.0)
        self.assertEqual(preview["surplus"], 60.0)
        written = allocation._proposal_recompute("quotation")
        self.assertEqual(written["applied"], 0.0)
        self.assertEqual(written["surplus"], 60.0)

    def test_closed_allocation_is_frozen(self):
        """RED/GREEN: a closed column never recomputes and never writes."""
        self._fund(self.allocation, self.voucher, 150.0)
        self.allocation._proposal_recompute("invoice")
        self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0001"
        ).amount_applied = 10.0
        _force_closed(self.allocation)
        before = self._applied(self.allocation)
        self.assertIsNone(self.allocation._proposal_recompute("invoice"))
        self.assertEqual(self._applied(self.allocation), before)
        self.assertEqual(dict(before)["FA-0001"], 10.0)

    def test_manual_edits_do_not_survive_a_recompute(self):
        """RED/GREEN: the plan depends only on collected, due dates, balances."""
        self._fund(self.allocation, self.voucher, 150.0)
        self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0002"
        ).amount_applied = 90.0
        self.allocation._proposal_recompute("invoice")
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 100.0), ("FA-0002", 50.0)],
        )

    def test_circuit_overdraft_self_heals(self):
        """RED/GREEN: applying above the circuit's collected money is undone."""
        self._fund(self.allocation, self.voucher, 100.0)
        self.allocation.line_ids.filtered(
            lambda line: line.document_kind == "quotation"
        ).amount_applied = 50.0
        self.assertEqual(self.allocation.proposal_status, "cruce")
        self.allocation._proposal_recompute("quotation")
        self.assertEqual(
            self._applied(self.allocation, "quotation"), [("PRE-0001", 0.0)]
        )

    def test_status_ladder_mirrors_the_mockup(self):
        """RED/GREEN: sin_iniciar, parcial, conciliado, a_favor, deuda, cerrado."""
        self.assertEqual(self.allocation.proposal_status, "sin_iniciar")
        self._fund(self.allocation, self.voucher, 150.0)
        self.allocation._proposal_recompute("invoice")
        self.assertEqual(self.allocation.proposal_status, "deuda")
        allocation_b = self.scenario["allocation_b"]
        self._fund(allocation_b, self.scenario["voucher_b"], 80.0)
        allocation_b._proposal_recompute("invoice")
        self.assertEqual(allocation_b.proposal_status, "conciliado")
        _force_closed(allocation_b)
        self.assertEqual(allocation_b.proposal_status, "cerrado")
        self.assertEqual(allocation_b.state, "draft")

    def test_cerrado_does_not_reuse_allocation_state(self):
        """RED/GREEN: freeze uses proposal_status cerrado; state stays draft."""
        self.assertEqual(self.allocation.state, "draft")
        _force_closed(self.allocation)
        self.assertEqual(self.allocation.proposal_status, "cerrado")
        self.assertEqual(self.allocation.state, "draft")
        self.assertNotEqual(self.allocation.state, self.allocation.proposal_status)

    def test_credit_balance_when_documents_are_covered(self):
        """RED/GREEN: money left over on a covered customer reads `a_favor`."""
        allocation = self.scenario["allocation_b"]
        self._fund(allocation, self.scenario["voucher_b"], 100.0)
        allocation._proposal_recompute("invoice")
        self.assertEqual(allocation.proposal_status, "a_favor")
        self.assertEqual(allocation.proposal_available_invoice, 20.0)

    def test_plan_respects_a_zero_balance_document(self):
        """RED/GREEN: a fully paid document absorbs nothing and spills over."""
        self.allocation.line_ids.filtered(
            lambda line: line.invoice_number == "FA-0001"
        ).invoice_balance = 0.0
        self._fund(self.allocation, self.voucher, 60.0)
        self.allocation._proposal_recompute("invoice")
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 0.0), ("FA-0002", 60.0)],
        )

    def test_preview_does_not_write(self):
        """RED/GREEN: `_proposal_preview` is non-mutating."""
        self._fund(self.allocation, self.voucher, 150.0)
        preview = self.allocation._proposal_preview("invoice")
        self.assertEqual(len(preview["changes"]), 2)
        self.assertEqual(
            self._applied(self.allocation),
            [("FA-0001", 0.0), ("FA-0002", 0.0)],
        )

    def test_preview_accepts_a_hypothetical_budget(self):
        """RED/GREEN: an explicit budget drives the simulated plan."""
        preview = self.allocation._proposal_preview("invoice", budget=250.0)
        self.assertEqual(
            [(change["number"], change["to"]) for change in preview["changes"]],
            [("FA-0001", 100.0), ("FA-0002", 100.0)],
        )
        self.assertEqual(preview["surplus"], 50.0)

    def test_fifo_key_handles_missing_values(self):
        """RED/GREEN: undated / unnumbered lines fall back to date.max and ''."""
        line = self.allocation.line_ids[0]
        line.write({"due_date": False, "invoice_number": False})
        self.assertEqual(
            self.env["collection.allocation"]._proposal_fifo_key(line),
            (date.max, ""),
        )

    def test_recompute_writes_are_sql_safe_for_receipt_totals(self):
        """RED/GREEN: FIFO amount_applied writes must not trip line_ids SQL."""
        receipt = self._fund(self.allocation, self.voucher, 150.0)
        self.allocation._proposal_recompute("invoice")
        self.assertEqual(receipt.total_values, 150.0)
        self.assertEqual(receipt.total_applied, 150.0)
        self.assertEqual(receipt.amount_on_account, 0.0)
