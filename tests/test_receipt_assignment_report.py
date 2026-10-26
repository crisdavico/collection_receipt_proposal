# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from odoo.addons.collection.models.collection_common import privileged
from odoo.addons.collection.tests.test_collection_payment import (
    second_active_currency,
)

from .common import ReceiptProposalCommon

MONEY_KEYS = ("collected", "applied", "on_account", "debt_total", "pending")
XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class TestReceiptAssignmentReport(ReceiptProposalCommon, TransactionCase):
    """RED/GREEN: the Asignaciones payload, its gating and its attachment."""

    def setUp(self):
        super().setUp()
        self.scenario = self._board_scenario()
        self.sheet = self.scenario["sheet"]
        self.allocation_a = self.scenario["allocation_a"]
        self.allocation_b = self.scenario["allocation_b"]
        self.voucher_a = self.scenario["voucher_a"]
        self.voucher_b = self.scenario["voucher_b"]
        self.name_a = self.allocation_a.partner_id.display_name
        self.name_b = self.allocation_b.partner_id.display_name

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fund(self, allocation, voucher, amount, document_kind="invoice"):
        receipt = allocation._proposal_receipt(document_kind) or self._create_receipt(
            allocation, document_kind
        )
        self._create_value(receipt, voucher, amount)
        allocation._proposal_recompute(document_kind)
        return receipt

    def _payload(self):
        return self.sheet._receipt_assignment_report_data()

    def _summary(self, payload=None):
        payload = payload or self._payload()
        return {(row["name"], row["kind"]): row for row in payload["summary_rows"]}

    def _customer(self, payload, name):
        blocks = [
            block for block in payload["customer_blocks"] if block["name"] == name
        ]
        self.assertEqual(len(blocks), 1, f"one customer block expected for {name}")
        return blocks[0]

    def _block(self, payload, name, kind):
        """The circuit block of one customer — the simulated receipt."""
        circuits = [
            circuit
            for circuit in self._customer(payload, name)["circuits"]
            if circuit["kind"] == kind
        ]
        self.assertEqual(len(circuits), 1, f"one {kind} circuit expected for {name}")
        return circuits[0]

    def _blocks(self, payload=None):
        payload = payload or self._payload()
        return {
            (customer["name"], circuit["kind"]): circuit
            for customer in payload["customer_blocks"]
            for circuit in customer["circuits"]
        }

    def _value_rows(self, circuit):
        """Every voucher row of a circuit, across its per-type blocks."""
        return [row for block in circuit["voucher_blocks"] for row in block["rows"]]

    def _own_sheet(self, label):
        """A fresh unconfirmed sheet and customer for this test alone.

        `_board_scenario`'s sheet is already in `proposal`, where voucher
        membership is frozen, so a test needing another voucher has to build
        and confirm its own sheet.
        """
        return self._create_sheet(force_new=True), self._partner(label)

    def _own_payload(self, sheet):
        return sheet._receipt_assignment_report_data()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def test_summary_row_mirrors_the_board_figures(self):
        """RED/GREEN: every summary amount comes from `_proposal_kind_figures`."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        row = self._summary()[(self.name_a, "invoice")]
        figures = self.allocation_a._proposal_kind_figures("invoice")
        self.assertEqual(row["collected"], figures["collected"])
        self.assertEqual(row["applied"], figures["applied"])
        self.assertEqual(row["on_account"], figures["available"])
        self.assertEqual(row["debt_total"], figures["total"])
        self.assertEqual(row["pending"], figures["pending"])
        self.assertEqual(row["kind_label"], "Facturas")
        self.assertEqual(row["code"], "")

    def test_rows_are_ordered_by_customer_then_circuit(self):
        """RED/GREEN: customer order, then invoice before quotation."""
        payload = self._payload()
        self.assertEqual(
            [(row["name"], row["kind"]) for row in payload["summary_rows"]],
            [
                (self.name_a, "invoice"),
                (self.name_a, "quotation"),
                (self.name_b, "invoice"),
            ],
        )
        self.assertEqual(payload["customer_count"], 2)

    def test_circuit_without_money_or_documents_is_skipped(self):
        """RED/GREEN: customer B works no quotation, so it carries no row."""
        summary = self._summary()
        self.assertNotIn((self.name_b, "quotation"), summary)
        self.assertIn((self.name_b, "invoice"), summary)

    def test_circuit_with_money_but_no_documents_still_shows(self):
        """RED/GREEN: money with nowhere to go MUST stay visible."""
        self._fund(self.allocation_b, self.voucher_b, 40.0, document_kind="quotation")
        row = self._summary()[(self.name_b, "quotation")]
        self.assertEqual(row["collected"], 40.0)
        self.assertEqual(row["applied"], 0.0)
        self.assertEqual(row["on_account"], 40.0)
        self.assertEqual(row["debt_total"], 0.0)

    def test_totals_add_up_per_circuit_and_overall(self):
        """RED/GREEN: `summary_totals` and `kind_totals` equal the row sums."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self._fund(self.allocation_b, self.voucher_b, 80.0)
        payload = self._payload()
        rows = payload["summary_rows"]
        for key in MONEY_KEYS:
            self.assertAlmostEqual(
                payload["summary_totals"][key], sum(row[key] for row in rows)
            )
            for kind in ("invoice", "quotation"):
                self.assertAlmostEqual(
                    payload["kind_totals"][kind][key],
                    sum(row[key] for row in rows if row["kind"] == kind),
                )

    def test_header_carries_the_sheet_context(self):
        """RED/GREEN: membrete fields come from the sheet, state label in Spanish."""
        payload = self._payload()
        self.assertEqual(payload["reference"], self.sheet.name)
        self.assertEqual(payload["state_label"], "Propuesta")
        self.assertEqual(payload["seller_name"], self.sheet.seller_id.name)
        self.assertEqual(
            payload["currency_name"], self.sheet.company_id.currency_id.name
        )
        self.assertEqual(payload["company"], self.sheet.company_id.name)

    # ------------------------------------------------------------------
    # Documents inside a receipt
    # ------------------------------------------------------------------

    def test_document_rows_keep_fifo_and_drop_unapplied_documents(self):
        """RED/GREEN: the block lists imputed documents in the money's own order."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        payload = self._payload()
        block = self._block(payload, self.name_a, "invoice")
        expected = [
            (line.invoice_number, line.amount_applied)
            for line in self.allocation_a._proposal_kind_lines("invoice")
            if line.amount_applied
        ]
        rows = block["document_rows"]
        self.assertEqual(
            [(row["number"], row["amount_applied"]) for row in rows], expected
        )
        self.assertEqual([row["number"] for row in rows], ["FA-0001", "FA-0002"])
        self.assertEqual(block["subtotal_amount_applied"], 150.0)
        self.assertEqual(rows[0]["invoice_state_label"], "Vigente")
        self.assertEqual(rows[0]["external_id"], "A-OLD")

    def test_circuit_without_a_receipt_has_a_row_but_no_block(self):
        """RED/GREEN: an untouched circuit is summarised, never simulated."""
        payload = self._payload()
        self.assertIn((self.name_a, "invoice"), self._summary(payload))
        self.assertEqual(payload["customer_blocks"], [])
        self.assertEqual(payload["customer_totals"]["total_applied"], 0.0)

    def test_customer_totals_add_up(self):
        """RED/GREEN: customer totals sum their circuits; the sheet sums those."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self._fund(self.allocation_a, self.voucher_a, 50.0, document_kind="quotation")
        self._fund(self.allocation_b, self.voucher_b, 80.0)
        payload = self._payload()
        customer = self._customer(payload, self.name_a)
        self.assertEqual(
            customer["total_applied"],
            sum(circuit["total_applied"] for circuit in customer["circuits"]),
        )
        self.assertEqual(customer["total_applied"], 200.0)
        self.assertEqual(
            payload["customer_totals"]["total_applied"],
            sum(block["total_applied"] for block in payload["customer_blocks"]),
        )
        self.assertEqual(payload["customer_totals"]["total_applied"], 280.0)
        self.assertEqual(payload["customer_totals"]["total_collected"], 280.0)

    def test_customer_carries_its_circuits_invoice_first(self):
        """RED/GREEN: circuits nest under one customer, in the report's order."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self._fund(self.allocation_a, self.voucher_a, 50.0, document_kind="quotation")
        customer = self._customer(self._payload(), self.name_a)
        self.assertEqual(
            [circuit["kind"] for circuit in customer["circuits"]],
            ["invoice", "quotation"],
        )

    # ------------------------------------------------------------------
    # The simulated receipt
    # ------------------------------------------------------------------

    def test_circuit_carries_the_receipt_band(self):
        """RED/GREEN: the band identifies the receipt and echoes its own totals."""
        receipt = self._fund(self.allocation_a, self.voucher_a, 150.0)
        block = self._block(self._payload(), self.name_a, "invoice")
        self.assertEqual(block["receipt_reference"], str(receipt.id))
        self.assertEqual(block["receipt_state"], "draft")
        self.assertEqual(block["receipt_state_label"], "Borrador")
        self.assertEqual(block["total_values"], receipt.total_values)
        self.assertEqual(block["total_applied"], receipt.total_applied)
        self.assertEqual(block["amount_on_account"], receipt.amount_on_account)

    def test_receipt_reference_prefers_the_external_id(self):
        """RED/GREEN: an issued receipt is named by the ERP, not by its rowid."""
        receipt = self._fund(self.allocation_a, self.voucher_a, 150.0)
        with privileged("collection_receipt_audited_state"):
            receipt.external_receipt_id = "REC-0009"
        block = self._block(self._payload(), self.name_a, "invoice")
        self.assertEqual(block["receipt_reference"], "REC-0009")

    def test_customer_blocks_follow_the_summary_row_order(self):
        """RED/GREEN: Clientes block *n* is the same pair as Resumen row *n*."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self._fund(self.allocation_a, self.voucher_a, 50.0, document_kind="quotation")
        self._fund(self.allocation_b, self.voucher_b, 80.0)
        payload = self._payload()
        summary_order = [(row["name"], row["kind"]) for row in payload["summary_rows"]]
        block_order = [
            (customer["name"], circuit["kind"])
            for customer in payload["customer_blocks"]
            for circuit in customer["circuits"]
        ]
        remaining = iter(summary_order)
        self.assertTrue(
            all(pair in remaining for pair in block_order),
            f"{block_order} is not a subsequence of {summary_order}",
        )
        self.assertEqual(len(block_order), 3)

    # ------------------------------------------------------------------
    # Vouchers behind a receipt
    # ------------------------------------------------------------------

    def test_value_rows_carry_the_full_voucher_info(self):
        """RED/GREEN: every voucher column the workbook prints is in the payload."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        circuit = self._block(self._payload(), self.name_a, "invoice")
        row = self._value_rows(circuit)[0]
        self.assertEqual(
            set(row),
            {
                "reference",
                "document_id",
                "partner_name",
                "type_label",
                "date",
                "number",
                "voucher_amount",
                "applied_amount",
                "state_label",
                "check_bank",
                "check_type_label",
                "check_issue_date",
                "check_payment_date",
                "from_account",
                "to_account",
                "retention_label",
                "reviewed_by",
                "reviewed_at",
                "is_partial",
            },
        )
        self.assertEqual(row["reference"], self.voucher_a.name)
        self.assertEqual(row["partner_name"], self.name_a)
        self.assertEqual(row["type_label"], "Transferencia bancaria")
        self.assertEqual(row["state_label"], "Validado por cobranzas")
        self.assertEqual(row["voucher_amount"], 300.0)
        self.assertEqual(row["applied_amount"], 150.0)
        self.assertEqual(row["check_bank"], "")
        self.assertEqual(row["check_type_label"], "")
        self.assertIs(row["check_issue_date"], False)

    def test_document_commission_is_on_the_untaxed_share_of_applied(self):
        """RED/GREEN: row commission MUST match the Planilla's untaxed rule."""
        sheet, partner = self._own_sheet("ASG-UNTAXED")
        sheet.write({"commission_percent": 10.0})
        voucher = self._create_voucher(partner, sheet, amount=605.0)
        allocation = self._create_allocation(
            sheet,
            partner,
            vouchers=voucher,
            lines=[
                self._line_vals(
                    external_invoice_id="U-1",
                    invoice_amount=1210.0,
                    invoice_balance=1210.0,
                    invoice_amount_untaxed=1000.0,
                )
            ],
        )
        receipt = self._create_receipt(allocation, "invoice")
        self._create_value(receipt, voucher, 605.0)
        self._confirm(sheet)
        allocation._proposal_recompute("invoice")
        customer = self._own_payload(sheet)["customer_blocks"][0]
        circuit = customer["circuits"][0]
        self.assertEqual(circuit["document_rows"][0]["amount_applied"], 605.0)
        self.assertEqual(circuit["document_rows"][0]["commission"], 50.0)
        self.assertEqual(circuit["subtotal_commission"], 50.0)
        self.assertEqual(customer["total_commission"], sheet.commission_amount)

    def test_check_columns_only_fill_for_a_check(self):
        """RED/GREEN: a cheque carries its bank, type and both dates."""
        sheet, partner = self._own_sheet("ASG-CHECK")
        check = self._create_voucher(
            partner,
            sheet,
            amount=100.0,
            document_type="check",
            check_number="CH-77",
            check_bank="Banco Nación",
            check_type="deferred",
            check_issue_date=date(2026, 9, 1),
            check_payment_date=date(2026, 10, 1),
        )
        allocation = self._create_allocation(
            sheet, partner, vouchers=check, lines=[self._line_vals()]
        )
        receipt = self._create_receipt(allocation, "invoice")
        self._create_value(receipt, check, 100.0)
        self._confirm(sheet)
        allocation._proposal_recompute("invoice")
        customers = self._own_payload(sheet)["customer_blocks"]
        self.assertEqual(len(customers), 1)
        circuit = customers[0]["circuits"][0]
        self.assertEqual(
            [block["code"] for block in circuit["voucher_blocks"]], ["check"]
        )
        row = circuit["voucher_blocks"][0]["rows"][0]
        self.assertEqual(row["number"], "CH-77")
        self.assertEqual(row["check_bank"], "Banco Nación")
        self.assertEqual(row["check_type_label"], "Diferido")
        self.assertEqual(row["check_issue_date"], date(2026, 9, 1))
        self.assertEqual(row["check_payment_date"], date(2026, 10, 1))
        self.assertEqual(row["type_label"], "Cheque")
        self.assertFalse(row["is_partial"])

    def test_value_row_flags_a_split_voucher(self):
        """RED/GREEN: a voucher larger than its share is highlighted, both sides."""
        self._fund(self.allocation_a, self.voucher_a, 200.0)
        quotation = self._fund(
            self.allocation_a, self.voucher_a, 50.0, document_kind="quotation"
        )
        self.assertTrue(quotation)
        payload = self._payload()
        blocks = self._blocks(payload)
        invoice_rows = self._value_rows(blocks[(self.name_a, "invoice")])
        quotation_rows = self._value_rows(blocks[(self.name_a, "quotation")])
        self.assertTrue(invoice_rows[0]["is_partial"])
        self.assertTrue(quotation_rows[0]["is_partial"])
        self.assertEqual(blocks[(self.name_a, "invoice")]["split_count"], 1)
        self.assertEqual(blocks[(self.name_a, "quotation")]["split_count"], 1)

    def test_value_row_is_not_flagged_when_the_voucher_is_consumed_whole(self):
        """RED/GREEN: `is_partial` is about money, not about the number of shares."""
        self._fund(self.allocation_b, self.voucher_b, 100.0)
        circuit = self._block(self._payload(), self.name_b, "invoice")
        row = self._value_rows(circuit)[0]
        self.assertEqual(row["voucher_amount"], row["applied_amount"])
        self.assertFalse(row["is_partial"])

    def test_value_subtotal_sums_the_applied_amount_not_the_voucher_amount(self):
        """RED/GREEN: summing `voucher.amount` would double-count a split."""
        receipt = self._fund(self.allocation_a, self.voucher_a, 200.0)
        circuit = self._block(self._payload(), self.name_a, "invoice")
        self.assertEqual(circuit["subtotal_values_applied"], receipt.total_values)
        self.assertEqual(circuit["subtotal_values_applied"], 200.0)
        self.assertNotEqual(
            circuit["subtotal_values_applied"],
            sum(row["voucher_amount"] for row in self._value_rows(circuit)),
        )

    # ------------------------------------------------------------------
    # Cash replacements
    # ------------------------------------------------------------------

    def _replacement_scenario(self, label="ASG-CASH", amount=60.0):
        """A confirmed sheet whose collected cash a remittance already replaced."""
        sheet, partner = self._own_sheet(label)
        cash = self._create_voucher(partner, sheet, amount=amount, document_type="cash")
        deposit = self._create_seller_deposit(sheet, amount=amount)
        allocation = self._create_allocation(
            sheet,
            partner,
            vouchers=cash,
            lines=[self._line_vals(invoice_balance=100.0)],
        )
        receipt = self._create_receipt(allocation, "invoice")
        self._create_value(receipt, cash, amount)
        # Confirm validates the remittance, which is what runs the replacement.
        self._confirm(sheet)
        allocation._proposal_recompute("invoice")
        return {
            "sheet": sheet,
            "cash": cash,
            "deposit": deposit,
            "allocation": allocation,
            "receipt": receipt,
        }

    def test_replaced_cash_still_reconciles_without_a_ledger(self):
        """RED/GREEN: no ledger rows ride in the block; the recon still closes."""
        scenario = self._replacement_scenario()
        payload = self._own_payload(scenario["sheet"])
        self.assertEqual(len(payload["customer_blocks"]), 1)
        block = payload["customer_blocks"][0]["circuits"][0]
        self.assertNotIn("cash_rows", block)
        self.assertNotIn("subtotal_cash_amount", block)
        self.assertEqual(scenario["cash"].replaced_amount, 60.0)
        self.assertEqual(payload["recon"]["replaced_total"], 60.0)
        self.assertEqual(payload["recon"]["difference"], 0.0)

    # ------------------------------------------------------------------
    # Unassigned money and reconciliation
    # ------------------------------------------------------------------

    def test_unassigned_lists_only_vouchers_with_free_money(self):
        """RED/GREEN: a fully assigned voucher leaves the section; a split stays."""
        self._fund(self.allocation_a, self.voucher_a, 200.0)
        self._fund(self.allocation_b, self.voucher_b, 100.0)
        section = self._payload()["unassigned"]
        rows = {
            row["reference"]: row
            for block in section["blocks"]
            for row in block["rows"]
        }
        self.assertNotIn(self.voucher_b.name, rows)
        self.assertIn(self.voucher_a.name, rows)
        self.assertEqual(
            rows[self.voucher_a.name]["applied_amount"],
            self.voucher_a.proposal_free_amount,
        )
        self.assertEqual(rows[self.voucher_a.name]["applied_amount"], 100.0)
        self.assertEqual(section["subtotal_free_amount"], 100.0)
        self.assertEqual(section["subtotal_voucher_amount"], 300.0)

    def test_unassigned_keeps_a_remittance_holding_free_money(self):
        """RED/GREEN: unlike the board pool, the section must reconcile the sheet."""
        sheet, partner = self._own_sheet("ASG-REM")
        transfer = self._create_voucher(partner, sheet, amount=100.0)
        deposit = self._create_seller_deposit(sheet, amount=70.0)
        self._create_allocation(
            sheet, partner, vouchers=transfer, lines=[self._line_vals()]
        )
        self._confirm(sheet)
        section = self._own_payload(sheet)["unassigned"]
        rows = {
            row["reference"]: row
            for block in section["blocks"]
            for row in block["rows"]
        }
        self.assertIn(deposit.name, rows)
        self.assertEqual(rows[deposit.name]["applied_amount"], 70.0)
        self.assertEqual(section["subtotal_free_amount"], 170.0)

    def test_unassigned_is_grouped_by_type_and_sorted_inside_each_block(self):
        """RED/GREEN: per-type blocks, each in the report's one sort order."""
        section = self._payload()["unassigned"]
        self.assertEqual(
            [block["code"] for block in section["blocks"]], ["bank_transfer"]
        )
        for block in section["blocks"]:
            names = [row["partner_name"] for row in block["rows"]]
            self.assertEqual(names, sorted(names))

    def test_recon_closes_against_the_sheet_voucher_total(self):
        """RED/GREEN: assigned + free + replaced MUST equal the sheet's own total."""
        self._fund(self.allocation_a, self.voucher_a, 200.0)
        recon = self._payload()["recon"]
        self.assertEqual(
            recon["computed_total"],
            recon["assigned_total"]
            + recon["unassigned_total"]
            + recon["replaced_total"],
        )
        self.assertEqual(recon["sheet_total"], 400.0)
        self.assertEqual(recon["difference"], 0.0)
        self.assertEqual(recon["status"], "balanced")

    def test_recon_still_closes_after_a_cash_replacement(self):
        """RED/GREEN: replaced cash is why the third component exists."""
        scenario = self._replacement_scenario()
        recon = self._own_payload(scenario["sheet"])["recon"]
        self.assertEqual(recon["replaced_total"], 60.0)
        self.assertEqual(recon["assigned_total"], 60.0)
        self.assertEqual(recon["unassigned_total"], 0.0)
        self.assertEqual(recon["sheet_total"], 120.0)
        self.assertEqual(recon["difference"], 0.0)

    # ------------------------------------------------------------------
    # Per-circuit status
    # ------------------------------------------------------------------

    def test_kind_status_not_started_when_nothing_is_applied(self):
        self.assertEqual(
            self.allocation_a._proposal_kind_status("invoice"), "sin_iniciar"
        )

    def test_kind_status_outstanding_debt_when_documents_remain(self):
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self.assertEqual(self.allocation_a._proposal_kind_status("invoice"), "deuda")

    def test_kind_status_reconciled_when_the_circuit_closes_flat(self):
        self._fund(self.allocation_a, self.voucher_a, 200.0)
        self.assertEqual(
            self.allocation_a._proposal_kind_status("invoice"), "conciliado"
        )

    def test_kind_status_credit_when_money_outlives_the_documents(self):
        self._fund(self.allocation_a, self.voucher_a, 250.0)
        self.assertEqual(self.allocation_a._proposal_kind_status("invoice"), "a_favor")

    def test_kind_status_overdraft_when_applied_exceeds_collected(self):
        # Core refuses raising applications past the values, so the overdraft
        # comes the way the board can produce it: the values shrink first.
        receipt = self._fund(self.allocation_a, self.voucher_a, 200.0)
        receipt.value_ids.amount = 100.0
        self.assertEqual(self.allocation_a._proposal_kind_status("invoice"), "cruce")

    def test_kind_status_partial_when_money_and_debt_both_remain(self):
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self.allocation_a._proposal_kind_lines("invoice")[0].amount_applied = 50.0
        self.allocation_a._proposal_kind_lines("invoice")[1].amount_applied = 0.0
        self.assertEqual(self.allocation_a._proposal_kind_status("invoice"), "parcial")

    def test_kind_status_closed_wins_over_the_figures(self):
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self.allocation_a.action_proposal_close(note="diferencia aceptada")
        self.assertEqual(self.allocation_a._proposal_kind_status("invoice"), "cerrado")
        row = self._summary()[(self.name_a, "invoice")]
        self.assertEqual(row["kind_status_label"], "Cerrado")
        self.assertTrue(row["closed"])
        self.assertEqual(row["note"], "diferencia aceptada")

    # ------------------------------------------------------------------
    # Gating
    # ------------------------------------------------------------------

    def test_report_refused_before_proposal(self):
        """RED/GREEN: open and submitted sheets have no proposal to report."""
        sheet = self._create_sheet(force_new=True)
        with self.assertRaises(UserError):
            sheet._receipt_assignment_report_data()
        sheet.action_seller_close()
        with self.assertRaises(UserError):
            sheet._receipt_assignment_report_data()

    def test_report_refused_on_cancelled(self):
        self.sheet.action_cancel()
        with self.assertRaises(UserError):
            self.sheet._receipt_assignment_report_data()

    def test_report_available_on_closed(self):
        """RED/GREEN: the export survives the close, for archive and audit."""
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        self.sheet.action_close()
        self.assertEqual(self.sheet.state, "closed")
        payload = self.sheet._receipt_assignment_report_data()
        self.assertEqual(payload["state_label"], "Cerrada")
        self.assertTrue(payload["summary_rows"])

    def test_unsaved_sheet_refused(self):
        with self.assertRaises(UserError):
            self.env["collection.sheet"].new(
                {"seller_id": self.sheet.seller_id.id}
            )._receipt_assignment_report_data()

    def test_mixed_currencies_refused(self):
        # A fresh database ships one active currency, and `search` honours
        # `active_test`: without a second active one `other.id` would be False,
        # the allocation would silently take the default, and this would fail
        # as "UserError not raised". So activate one for this test.
        other = second_active_currency(self.env, self.sheet.company_id.currency_id)
        self.assertTrue(other, "need a second active currency for the mismatch")
        self._create_allocation(
            self.sheet, self._partner("PROP-C"), currency_id=other.id
        )
        with self.assertRaises(UserError):
            self.sheet._receipt_assignment_report_data()

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def test_action_returns_act_url_and_stores_the_attachment(self):
        self._fund(self.allocation_a, self.voucher_a, 150.0)
        action = self.sheet.action_print_receipt_assignment_xlsx()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertEqual(action["target"], "download")
        expected = f"{self.sheet.name.replace('/', '-')}-asignaciones.xlsx"
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "collection.sheet"),
                ("res_id", "=", self.sheet.id),
                ("name", "=", expected),
            ]
        )
        self.assertEqual(len(attachment), 1)
        self.assertEqual(attachment.mimetype, XLSX_MIMETYPE)
        self.assertIn(f"/web/content/{attachment.id}", action["url"])
        self.assertTrue(attachment.raw.startswith(b"PK"))

    def test_action_replaces_its_own_attachment(self):
        self.sheet.action_print_receipt_assignment_xlsx()
        self.sheet.action_print_receipt_assignment_xlsx()
        expected = f"{self.sheet.name.replace('/', '-')}-asignaciones.xlsx"
        self.assertEqual(
            self.env["ir.attachment"].search_count(
                [
                    ("res_model", "=", "collection.sheet"),
                    ("res_id", "=", self.sheet.id),
                    ("name", "=", expected),
                ]
            ),
            1,
        )

    def test_action_does_not_touch_the_planilla_attachment(self):
        """RED/GREEN: the two exports MUST keep separate attachment names."""
        self.sheet.action_print_xlsx()
        self.sheet.action_print_receipt_assignment_xlsx()
        names = set(
            self.env["ir.attachment"]
            .search(
                [
                    ("res_model", "=", "collection.sheet"),
                    ("res_id", "=", self.sheet.id),
                ]
            )
            .mapped("name")
        )
        reference = self.sheet.name.replace("/", "-")
        self.assertIn(f"{reference}.xlsx", names)
        self.assertIn(f"{reference}-asignaciones.xlsx", names)
