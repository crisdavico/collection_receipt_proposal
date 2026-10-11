# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase
from odoo.tools import SQL

from .common import ReceiptProposalCommon

_LOCK = re.compile(r'^SELECT id FROM "(\w+)" WHERE id IN %s ORDER BY id FOR UPDATE$')
_MARK = re.compile(r'^UPDATE "(\w+)" SET write_date = write_date WHERE id IN %s$')


class TestReceiptProposalConcurrency(ReceiptProposalCommon, TransactionCase):
    """Two operators on one board: every move locks the money it touches.

    Each transaction checks the split cap and the circuit budget against its
    own snapshot, so two operators moving the free part of the same voucher
    at the same moment could both commit and over-assign it. A real race
    needs two committed transactions and cannot run deterministically inside
    a test transaction, so these tests pin the parts that make it safe: the
    lock is issued on the right rows before the first write, it really
    rewrites them (what makes PostgreSQL refuse the second transaction, which
    Odoo then retries), and what is validated is re-read after the lock.
    """

    def setUp(self):
        super().setUp()
        scenario = self._board_scenario()
        self.sheet = scenario["sheet"]
        self.allocation_a = scenario["allocation_a"]
        self.allocation_b = scenario["allocation_b"]
        self.voucher_a = scenario["voucher_a"]
        self.voucher_b = scenario["voucher_b"]
        self.Sheet = self.env["collection.sheet"]

    def _assign(self, allocation, voucher, amount, document_kind="invoice"):
        return self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            voucher_id=voucher.id,
            to_allocation_id=allocation.id,
            document_kind=document_kind,
            amount=amount,
        )

    def _statements(self, call):
        """Run ``call`` and return every ``(code, params)`` it sent, in order."""
        self.env.flush_all()
        cursor_class = type(self.env.cr)
        original = cursor_class.execute
        statements = []

        def spy(cr, query, params=None, log_exceptions=True):
            if isinstance(query, SQL):
                statements.append((query.code, query.params))
            else:
                statements.append((str(query), params))
            return original(cr, query, params, log_exceptions)

        with patch.object(cursor_class, "execute", spy):
            call()
            # Writes the ORM still holds belong to this call too.
            self.env.flush_all()
        return statements

    def _locked(self, statements, pattern):
        """``{table: (index of first lock, ids)}`` for one statement pattern."""
        found = {}
        for index, (code, params) in enumerate(statements):
            match = pattern.match(" ".join(code.split()))
            if match and match.group(1) not in found:
                found[match.group(1)] = (index, set(params[0]))
        return found

    def _first_write(self, statements, table):
        writes = re.compile(rf'^(INSERT INTO|UPDATE|DELETE FROM) "{table}"')
        for index, (code, _params) in enumerate(statements):
            if writes.match(code.strip()):
                return index
        self.fail(f"no write on {table} was issued")

    def _assert_locked_before(self, statements, write_table, vouchers, allocations):
        locks = self._locked(statements, _LOCK)
        marks = self._locked(statements, _MARK)
        first_write = self._first_write(statements, write_table)
        for table, records in (
            ("collection_voucher", vouchers),
            ("collection_allocation", allocations),
        ):
            if not records:
                continue
            self.assertIn(table, locks, f"{table} rows must be locked")
            self.assertIn(table, marks, f"{table} rows must be rewritten")
            self.assertEqual(locks[table][1], set(records.ids))
            self.assertEqual(marks[table][1], set(records.ids))
            self.assertLess(
                locks[table][0], first_write, f"{table} must be locked first"
            )
            self.assertLess(marks[table][0], first_write)

    def test_assigning_from_the_pool_locks_the_voucher_and_its_column(self):
        statements = self._statements(
            lambda: self._assign(self.allocation_a, self.voucher_a, 150.0)
        )
        self._assert_locked_before(
            statements,
            "collection_receipt_value",
            self.voucher_a,
            self.allocation_a,
        )

    def test_a_split_locks_the_voucher_and_both_customers(self):
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        statements = self._statements(
            lambda: self.Sheet.action_proposal_transfer(
                sheet_id=self.sheet.id,
                value_id=value.id,
                to_allocation_id=self.allocation_b.id,
                document_kind="invoice",
                amount=80.0,
            )
        )
        self._assert_locked_before(
            statements,
            "collection_receipt_value",
            self.voucher_a,
            self.allocation_a | self.allocation_b,
        )

    def test_returning_a_card_to_the_pool_locks_its_voucher_and_column(self):
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        statements = self._statements(
            lambda: self.Sheet.action_proposal_transfer(
                sheet_id=self.sheet.id,
                value_id=value.id,
                to_allocation_id=None,
                amount=50.0,
            )
        )
        self._assert_locked_before(
            statements,
            "collection_receipt_value",
            self.voucher_a,
            self.allocation_a,
        )

    def test_changing_the_circuit_locks_the_voucher_and_its_column(self):
        self._assign(self.allocation_a, self.voucher_a, 120.0)
        value = self.voucher_a.proposal_value_ids
        statements = self._statements(
            lambda: self.Sheet.action_proposal_set_circuit(
                sheet_id=self.sheet.id,
                value_id=value.id,
                document_kind="quotation",
            )
        )
        self._assert_locked_before(
            statements,
            "collection_receipt_value",
            self.voucher_a,
            self.allocation_a,
        )

    def test_merging_a_split_locks_the_voucher_and_every_part(self):
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        self.Sheet.action_proposal_transfer(
            sheet_id=self.sheet.id,
            value_id=value.id,
            to_allocation_id=self.allocation_b.id,
            document_kind="invoice",
            amount=80.0,
        )
        statements = self._statements(
            lambda: self.Sheet.action_proposal_undo_split(
                sheet_id=self.sheet.id,
                voucher_id=self.voucher_a.id,
                keep_value_id=value.id,
            )
        )
        self._assert_locked_before(
            statements,
            "collection_receipt_value",
            self.voucher_a,
            self.allocation_a | self.allocation_b,
        )

    def test_imputing_locks_its_column(self):
        """Every move that changes a circuit's budget locks its column."""
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        lines = self.allocation_a._proposal_kind_lines("invoice")
        statements = self._statements(
            lambda: self.Sheet.action_proposal_impute(
                sheet_id=self.sheet.id,
                allocation_id=self.allocation_a.id,
                document_kind="invoice",
                lines=[
                    {"line_id": lines[0].id, "amount": 60.0},
                    {"line_id": lines[1].id, "amount": 100.0},
                ],
            )
        )
        self._assert_locked_before(
            statements,
            "collection_allocation_line",
            self.env["collection.voucher"],
            self.allocation_a,
        )

    def test_reset_locks_every_voucher_and_column_of_the_sheet(self):
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        self._assign(self.allocation_b, self.voucher_b, 100.0)
        statements = self._statements(
            lambda: self.Sheet.action_proposal_reset_vouchers(sheet_id=self.sheet.id)
        )
        self._assert_locked_before(
            statements,
            "collection_receipt_value",
            self.sheet.voucher_ids,
            self.sheet.allocation_ids,
        )

    def test_the_lock_rewrites_the_rows_it_locks(self):
        """A lock alone lets a REPEATABLE READ waiter go on with stale data.

        PostgreSQL only refuses the second transaction when the first one
        actually updated the row, so the lock must leave a new row version
        behind -- a new ``ctid`` -- on every voucher and column it holds.
        """

        def ctid(table, record):
            self.env.cr.execute(
                SQL(
                    "SELECT ctid FROM %s WHERE id = %s",
                    SQL.identifier(table),
                    record.id,
                )
            )
            return self.env.cr.fetchone()[0]

        self.env.flush_all()
        before = (
            ctid("collection_voucher", self.voucher_a),
            ctid("collection_allocation", self.allocation_a),
        )
        self.sheet._proposal_lock(self.voucher_a, self.allocation_a)
        after = (
            ctid("collection_voucher", self.voucher_a),
            ctid("collection_allocation", self.allocation_a),
        )
        self.assertNotEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])

    def test_a_stale_view_is_re_read_after_the_lock_and_refused(self):
        """The second operator's move is validated on fresh rows.

        Operator 1 already put the rest of the voucher on customer A; this
        transaction still holds the free amount it read before. After the
        lock the plan re-reads the voucher, finds nothing left, and refuses
        instead of over-assigning it to customer B.
        """
        self._assign(self.allocation_a, self.voucher_a, 200.0)
        value = self.voucher_a.proposal_value_ids
        self.assertEqual(self.voucher_a.proposal_free_amount, 100.0)
        self.env.flush_all()
        # The other operator's committed move, invisible to this cache.
        self.env.cr.execute(
            "UPDATE collection_receipt_value SET amount = 300 WHERE id = %s",
            [value.id],
        )
        with self.assertRaisesRegex(UserError, "no unassigned amount left"):
            self._assign(self.allocation_b, self.voucher_a, 100.0)
