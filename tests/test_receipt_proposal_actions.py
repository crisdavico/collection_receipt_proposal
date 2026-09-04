# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon


class TestReceiptProposalActions(ReceiptProposalCommon, TransactionCase):
    """RED/GREEN: the board RPC surface and the event each call writes."""

    def setUp(self):
        super().setUp()
        self.scenario = self._board_scenario()
        self.sheet = self.scenario["sheet"]
        self.allocation_a = self.scenario["allocation_a"]
        self.allocation_b = self.scenario["allocation_b"]
        self.voucher_a = self.scenario["voucher_a"]
        self.voucher_b = self.scenario["voucher_b"]
        self.Sheet = self.env["collection.sheet"]

    def _events(self, event_type=None):
        domain = [("sheet_id", "=", self.sheet.id)]
        if event_type:
            domain.append(("event_type", "=", event_type))
        return self.env["collection.receipt.proposal.event"].search(domain)

    def _assign(self, allocation, voucher, amount, document_kind="invoice"):
        return self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            voucher_id=voucher.id,
            to_allocation_id=allocation.id,
            document_kind=document_kind,
            amount=amount,
        )

    def test_assign_from_the_pool_creates_receipt_value_and_event(self):
        """RED/GREEN: a pool drop creates the receipt, the value and an event."""
        board = self._assign(self.allocation_a, self.voucher_a, 150.0)
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 150.0)
        self.assertEqual(len(self.voucher_a.proposal_value_ids), 1)
        self.assertTrue(self._events("assign"))
        self.assertEqual(len(board["columns"]), 2)

    def test_assign_triggers_the_fifo_redistribution(self):
        """RED/GREEN: every collected change redistributes that circuit."""
        self._assign(self.allocation_a, self.voucher_a, 150.0)
        applied = {
            line.invoice_number: line.amount_applied
            for line in self.allocation_a._proposal_kind_lines("invoice")
        }
        self.assertEqual(applied, {"FA-0001": 100.0, "FA-0002": 50.0})
        self.assertTrue(self._events("auto_impute"))

    def test_transfer_between_customers_recomputes_both_circuits(self):
        """RED/GREEN: source and destination are both redistributed."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=80.0,
        )
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 120.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 80.0)
        self.assertEqual(self.allocation_a.proposal_applied_invoice, 120.0)
        self.assertEqual(self.allocation_b.proposal_applied_invoice, 80.0)
        self.assertTrue(self._events("split"))

    def test_transfer_back_to_the_pool_frees_the_amount(self):
        """RED/GREEN: dropping a card on the pool returns money to the voucher."""
        self._assign(self.allocation_a, self.voucher_a, 150.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=None,
            amount=150.0,
        )
        self.assertEqual(self.voucher_a.proposal_free_amount, 300.0)
        self.assertEqual(self.allocation_a.proposal_applied_invoice, 0.0)
        self.assertTrue(self._events("transfer"))

    def test_transfer_refuses_a_no_op(self):
        """RED/GREEN: moving a card onto its own circuit raises."""
        self._assign(self.allocation_a, self.voucher_a, 150.0)
        value = self.voucher_a.proposal_value_ids
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_transfer(
                sheet_id=self.sheet.id,
                value_id=value.id,
                to_allocation_id=self.allocation_a.id,
                document_kind="invoice",
                amount=50.0,
            )

    def test_transfer_refuses_an_invalid_circuit(self):
        """RED/GREEN: `document_kind` must be invoice or quotation."""
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_transfer(
                sheet_id=self.sheet.id,
                voucher_id=self.voucher_a.id,
                to_allocation_id=self.allocation_a.id,
                document_kind="whatever",
                amount=50.0,
            )

    def test_set_circuit_moves_the_whole_card(self):
        """RED/GREEN: *Cambiar circuito* re-parents the card and recomputes."""
        self._assign(self.allocation_a, self.voucher_a, 120.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_set_circuit(
            sheet_id=self.sheet.id,
            value_id=value.id,
            document_kind="quotation",
        )
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 0.0)
        self.assertEqual(self.allocation_a.proposal_collected_quotation, 120.0)
        self.assertEqual(self.allocation_a.proposal_applied_invoice, 0.0)
        self.assertEqual(self.allocation_a.proposal_applied_quotation, 50.0)
        self.assertTrue(self._events("circuit"))

    def test_set_circuit_refuses_the_current_circuit(self):
        """RED/GREEN: the target circuit must differ from the current one."""
        self._assign(self.allocation_a, self.voucher_a, 120.0)
        value = self.voucher_a.proposal_value_ids
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_set_circuit(
                sheet_id=self.sheet.id,
                value_id=value.id,
                document_kind="invoice",
            )

    def test_manual_impute_writes_the_requested_amounts(self):
        """RED/GREEN: *Imputar* writes exactly what the operator typed."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        lines = self.allocation_a._proposal_kind_lines("invoice")
        self.Sheet.action_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            document_kind="invoice",
            lines=[
                {"line_id": lines[0].id, "amount": 60.0},
                {"line_id": lines[1].id, "amount": 40.0},
            ],
        )
        self.assertEqual(lines[0].amount_applied, 60.0)
        self.assertEqual(lines[1].amount_applied, 40.0)
        self.assertTrue(self._events("impute"))

    def test_manual_impute_refuses_above_the_document_balance(self):
        """RED/GREEN: a document never absorbs more than `invoice_balance`."""
        self._assign(self.allocation_a, self.voucher_a, 300.0)
        line = self.allocation_a._proposal_kind_lines("invoice")[0]
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_impute(
                sheet_id=self.sheet.id,
                allocation_id=self.allocation_a.id,
                document_kind="invoice",
                lines=[{"line_id": line.id, "amount": 150.0}],
            )

    def test_manual_impute_refuses_above_the_collected_amount(self):
        """RED/GREEN: a circuit never applies more than it collected."""
        self._assign(self.allocation_a, self.voucher_a, 50.0)
        lines = self.allocation_a._proposal_kind_lines("invoice")
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_impute(
                sheet_id=self.sheet.id,
                allocation_id=self.allocation_a.id,
                document_kind="invoice",
                lines=[
                    {"line_id": lines[0].id, "amount": 100.0},
                    {"line_id": lines[1].id, "amount": 100.0},
                ],
            )

    def test_manual_impute_is_overwritten_by_the_next_fifo_run(self):
        """RED/GREEN: moving a card discards manual `Imputar` edits."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        lines = self.allocation_a._proposal_kind_lines("invoice")
        self.Sheet.action_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            document_kind="invoice",
            lines=[
                {"line_id": lines[0].id, "amount": 50.0},
                {"line_id": lines[1].id, "amount": 50.0},
            ],
        )
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=50.0,
        )
        self.assertEqual(lines[0].amount_applied, 100.0)
        self.assertEqual(lines[1].amount_applied, 50.0)

    def test_close_customer_requires_a_note_when_there_are_differences(self):
        """RED/GREEN: closing with a difference is gated on a note."""
        self._assign(self.allocation_a, self.voucher_a, 150.0)
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_close_customer(
                sheet_id=self.sheet.id,
                allocation_id=self.allocation_a.id,
                note="",
            )
        self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            note="Saldo a favor en la próxima planilla.",
        )
        self.assertTrue(self.allocation_a.proposal_closed)
        self.assertEqual(self.allocation_a.proposal_closed_uid, self.env.user)
        self.assertTrue(self.allocation_a.proposal_closed_date)
        self.assertTrue(self._events("close"))

    def test_close_without_differences_needs_no_note(self):
        """RED/GREEN: a fully reconciled customer closes without a note."""
        self._assign(self.allocation_b, self.voucher_b, 80.0)
        self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_b.id,
        )
        self.assertTrue(self.allocation_b.proposal_closed)

    def test_closed_customer_refuses_further_board_edits(self):
        """RED/GREEN: a closed column is frozen for the board."""
        self._assign(self.allocation_a, self.voucher_a, 150.0)
        self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            note="Cerrado con diferencia.",
        )
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_transfer(
                sheet_id=self.sheet.id,
                voucher_id=self.voucher_b.id,
                to_allocation_id=self.allocation_a.id,
                document_kind="invoice",
                amount=10.0,
            )

    def test_reopen_customer_clears_the_close_stamp(self):
        """RED/GREEN: *Reabrir* unfreezes the column and logs an event."""
        self._assign(self.allocation_b, self.voucher_b, 80.0)
        self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_b.id,
        )
        self.Sheet.action_proposal_reopen_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_b.id,
        )
        self.assertFalse(self.allocation_b.proposal_closed)
        self.assertFalse(self.allocation_b.proposal_closed_uid)
        self.assertTrue(self._events("reopen"))

    def test_previews_do_not_write(self):
        """RED/GREEN: every preview endpoint is read-only."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        before = {line.id: line.amount_applied for line in self.allocation_a.line_ids}
        value = self.voucher_a.proposal_value_ids
        preview = self.Sheet.preview_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=80.0,
        )
        self.assertEqual(len(preview), 2)
        self.Sheet.preview_proposal_circuit(
            sheet_id=self.sheet.id,
            value_id=value.id,
            document_kind="quotation",
        )
        self.Sheet.preview_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            document_kind="invoice",
        )
        self.assertEqual(
            {line.id: line.amount_applied for line in self.allocation_a.line_ids},
            before,
        )

    def _assert_full_board(self, board):
        self.assertEqual(set(board), {"sheet", "columns", "pool", "events"})
        self.assertEqual(board["sheet"]["id"], self.sheet.id)
        self.assertEqual(len(board["columns"]), 2)

    def test_every_mutation_returns_the_full_board(self):
        """RED/GREEN: mutating calls answer with the refreshed payload."""
        board = self._assign(self.allocation_a, self.voucher_a, 150.0)
        self._assert_full_board(board)
        self.assertTrue(board["events"])

    def test_transfer_set_circuit_impute_close_reopen_return_the_full_board(self):
        """RED/GREEN: transfer, circuit, impute, close and reopen return the board."""
        transfer = self._assign(self.allocation_a, self.voucher_a, 150.0)
        self._assert_full_board(transfer)
        value = self.voucher_a.proposal_value_ids
        circuit = self.Sheet.action_proposal_set_circuit(
            sheet_id=self.sheet.id,
            value_id=value.id,
            document_kind="quotation",
        )
        self._assert_full_board(circuit)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_set_circuit(
            sheet_id=self.sheet.id,
            value_id=value.id,
            document_kind="invoice",
        )
        lines = self.allocation_a._proposal_kind_lines("invoice")
        impute = self.Sheet.action_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            document_kind="invoice",
            lines=[{"line_id": lines[0].id, "amount": 60.0}],
        )
        self._assert_full_board(impute)
        close = self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            note="Cerrado con diferencia.",
        )
        self._assert_full_board(close)
        column = next(
            col
            for col in close["columns"]
            if col["allocation_id"] == self.allocation_a.id
        )
        self.assertTrue(column["closed"])
        self.assertEqual(column["status"], "cerrado")
        reopen = self.Sheet.action_proposal_reopen_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
        )
        self._assert_full_board(reopen)
        column = next(
            col
            for col in reopen["columns"]
            if col["allocation_id"] == self.allocation_a.id
        )
        self.assertFalse(column["closed"])

    def test_transfer_ignores_client_supplied_applied_lines(self):
        """RED/GREEN: only the typed amount is accepted; FIFO is server-side."""
        lines = self.allocation_a._proposal_kind_lines("invoice")
        board = self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            voucher_id=self.voucher_a.id,
            to_allocation_id=self.allocation_a.id,
            document_kind="invoice",
            amount=150.0,
            lines=[
                {"line_id": lines[0].id, "amount": 1.0},
                {"line_id": lines[1].id, "amount": 1.0},
            ],
            changes=[{"line_id": lines[0].id, "from": 0.0, "to": 1.0}],
        )
        self._assert_full_board(board)
        applied = {
            line.invoice_number: line.amount_applied
            for line in self.allocation_a._proposal_kind_lines("invoice")
        }
        self.assertEqual(applied, {"FA-0001": 100.0, "FA-0002": 50.0})
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 150.0)

    def test_close_requires_a_note_when_collected_exceeds_applied(self):
        """RED/GREEN: a surplus after Imputar is a difference that needs a note."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        lines = self.allocation_a._proposal_kind_lines("invoice")
        self.Sheet.action_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            document_kind="invoice",
            lines=[
                {"line_id": lines[0].id, "amount": 50.0},
                {"line_id": lines[1].id, "amount": 50.0},
            ],
        )
        with self.assertRaises(UserError):
            self.Sheet.action_proposal_close_customer(
                sheet_id=self.sheet.id,
                allocation_id=self.allocation_a.id,
                note="   ",
            )
        board = self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            note="Saldo a favor.",
        )
        self._assert_full_board(board)
        self.assertTrue(self.allocation_a.proposal_closed)

    def test_unify_merges_parts_into_one_value_and_returns_the_board(self):
        """RED/GREEN: unify collapses a voucher's cards into one destination value."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=80.0,
        )
        source = self.voucher_a.proposal_value_ids.filtered(
            lambda row: row.receipt_id.allocation_id == self.allocation_a
        )
        board = self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=source.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            unify=True,
        )
        self._assert_full_board(board)
        self.assertEqual(len(self.voucher_a.proposal_value_ids), 1)
        self.assertEqual(self.voucher_a.proposal_assigned_amount, 200.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 200.0)
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 0.0)

    def test_undo_split_keeps_the_chosen_card_and_returns_the_board(self):
        """RED/GREEN: undo-split keeps keep_value_id and restores the assigned total."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=80.0,
        )
        keep = self.voucher_a.proposal_value_ids.filtered(
            lambda row: row.receipt_id.allocation_id == self.allocation_a
        )
        board = self.Sheet.action_proposal_undo_split(
            sheet_id=self.sheet.id,
            voucher_id=self.voucher_a.id,
            keep_value_id=keep.id,
        )
        self._assert_full_board(board)
        self.assertEqual(len(self.voucher_a.proposal_value_ids), 1)
        self.assertEqual(keep.amount, 200.0)
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 200.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 0.0)
        self.assertEqual(self.voucher_a.allocation_id, self.allocation_a)

    def test_owner_repoints_to_largest_share_after_split(self):
        """RED/GREEN: 30 on A then 70 on B re-points owner to B."""
        self._assign(self.allocation_a, self.voucher_a, 30.0)
        self._assign(self.allocation_b, self.voucher_a, 70.0)
        self.assertEqual(self.voucher_a.allocation_id, self.allocation_b)
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 30.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 70.0)

    def test_owner_points_at_overall_largest_share(self):
        """RED/GREEN: owner follows the overall largest share, even other customer."""
        self._assign(self.allocation_a, self.voucher_a, 300.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=200.0,
        )
        self.assertEqual(self.allocation_a.proposal_collected_invoice, 100.0)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 200.0)
        self.assertEqual(self.voucher_a.allocation_id, self.allocation_b)

    def test_owner_follows_when_all_shares_move_to_another_customer(self):
        """RED/GREEN: moving every share to B names B as owner."""
        self._assign(self.allocation_a, self.voucher_a, 300.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=300.0,
        )
        self.assertEqual(self.voucher_a.allocation_id, self.allocation_b)
        self.assertEqual(self.allocation_b.proposal_collected_invoice, 300.0)

    def test_partner_write_still_refused_without_a_share_on_the_target(self):
        """RED/GREEN: naming another customer's allocation still needs a share there."""
        self._assign(self.allocation_a, self.voucher_a, 100.0)
        with self.assertRaises(UserError) as err:
            self.voucher_a.allocation_id = self.allocation_b
        self.assertIn("must match the allocation customer", str(err.exception))
        self.assertEqual(self.voucher_a.allocation_id, self.allocation_a)

    def test_mutations_write_the_matching_event_types(self):
        """RED/GREEN: each mutation appends the matching event type."""
        self._assign(self.allocation_a, self.voucher_a, 150.0)
        types = self._events().mapped("event_type")
        self.assertIn("assign", types)
        self.assertIn("auto_impute", types)
        assign = self._events("assign")[:1]
        self.assertEqual(assign.user_id, self.env.user)
        self.assertTrue(assign.event_date)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=50.0,
        )
        self.assertIn("split", self._events().mapped("event_type"))
        remaining = self.voucher_a.proposal_value_ids.filtered(
            lambda row: row.receipt_id.allocation_id == self.allocation_a
        )
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=remaining.id,
            to_allocation_id=None,
            amount=100.0,
        )
        self.assertIn("transfer", self._events().mapped("event_type"))
        self._assign(self.allocation_a, self.voucher_a, 120.0)
        card = self.voucher_a.proposal_value_ids.filtered(
            lambda row: row.receipt_id.allocation_id == self.allocation_a
        )
        self.Sheet.action_proposal_set_circuit(
            sheet_id=self.sheet.id,
            value_id=card.id,
            document_kind="quotation",
        )
        self.assertIn("circuit", self._events().mapped("event_type"))
        self.Sheet.action_proposal_set_circuit(
            sheet_id=self.sheet.id,
            value_id=self.voucher_a.proposal_value_ids.filtered(
                lambda row: row.receipt_id.document_kind == "quotation"
            ).id,
            document_kind="invoice",
        )
        lines = self.allocation_a._proposal_kind_lines("invoice")
        self.Sheet.action_proposal_impute(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            document_kind="invoice",
            lines=[{"line_id": lines[0].id, "amount": 40.0}],
        )
        self.assertIn("impute", self._events().mapped("event_type"))
        self.Sheet.action_proposal_close_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
            note="Cerrado con diferencia.",
        )
        close = self._events("close")[:1]
        self.assertTrue(close)
        self.assertEqual(close.user_id, self.env.user)
        self.assertTrue(close.event_date)
        self.Sheet.action_proposal_reopen_customer(
            sheet_id=self.sheet.id,
            allocation_id=self.allocation_a.id,
        )
        reopen = self._events("reopen")[:1]
        self.assertTrue(reopen)
        self.assertEqual(reopen.user_id, self.env.user)
        self.assertTrue(reopen.event_date)

    def test_auto_impute_is_skipped_when_fifo_already_matches(self):
        """RED/GREEN: FIFO with empty changes must not write auto_impute."""
        self._assign(self.allocation_a, self.voucher_a, 150.0)
        before = self._events("auto_impute")
        self.assertTrue(before)
        preview = self.allocation_a._proposal_recompute("invoice")
        self.assertEqual(preview["changes"], [])
        self.assertEqual(self._events("auto_impute"), before)

    def test_unify_and_undo_split_write_unify_events(self):
        """RED/GREEN: unify transfer and undo-split both persist event_type unify."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=80.0,
        )
        source = self.voucher_a.proposal_value_ids.filtered(
            lambda row: row.receipt_id.allocation_id == self.allocation_a
        )
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=source.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            unify=True,
        )
        self.assertTrue(self._events("unify"))
        keep = self.voucher_a.proposal_value_ids
        self._assign(self.allocation_a, self.voucher_a, 50.0)
        self.Sheet.action_proposal_undo_split(
            sheet_id=self.sheet.id,
            voucher_id=self.voucher_a.id,
            keep_value_id=keep.id,
        )
        self.assertGreaterEqual(len(self._events("unify")), 2)
