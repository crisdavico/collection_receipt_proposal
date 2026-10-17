# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Close fields trust an in-process scope, not context keys.

JSON-RPC and muk_mcp both merge a caller-supplied ``context``, so a forged key
must not let a Collections User write the close fields.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon

_CLOSE_GUARD_MESSAGE = (
    "Customers can only be closed or reopened from the receipt proposal board."
)
_CLOSE_FIELD_WRITES = (
    {"proposal_closed": True},
    {"proposal_note": "Forged note"},
    {"proposal_closed_date": "2020-01-01 00:00:00"},
)


class TestReceiptProposalPrivileged(ReceiptProposalCommon, TransactionCase):
    """Forged keys MUST NOT write per-customer close fields."""

    def setUp(self):
        super().setUp()
        self.scenario = self._board_scenario()
        self.sheet = self.scenario["sheet"]
        self.allocation = self.scenario["allocation_a"]
        self.operator = self._create_user(
            "prop_scope_operator", "collection.group_collection_user"
        )
        self.other = self._create_user(
            "prop_scope_other", "collection.group_collection_user"
        )

    def _assert_close_guard(self, error):
        """The board's own guard refused, not an ACL or a field-groups check.

        ``AccessError`` and ``ValidationError`` subclass ``UserError``, so
        ``assertRaises(UserError)`` alone would pass on either of them.
        """
        self.assertIs(type(error.exception), UserError)
        self.assertEqual(str(error.exception), _CLOSE_GUARD_MESSAGE)

    def test_close_fields_are_writable_only_through_the_board_actions(self):
        writes = _CLOSE_FIELD_WRITES + ({"proposal_closed_uid": self.other.id},)
        allocation = self.allocation.with_user(self.operator)
        for vals in writes:
            for context in ({}, {"collection_receipt_proposal_close": True}):
                with self.subTest(vals=vals, context=context):
                    with self.assertRaises(UserError) as error:
                        allocation.with_context(**context).write(vals)
                    self._assert_close_guard(error)
        self.assertFalse(self.allocation.proposal_closed)
        self.assertFalse(self.allocation.proposal_note)
        self.assertFalse(self.allocation.proposal_closed_uid)
        self.assertFalse(self.allocation.proposal_closed_date)

    def test_allocation_cannot_be_created_already_closed(self):
        Allocation = self.env["collection.allocation"].with_user(self.operator)
        for index, vals in enumerate(_CLOSE_FIELD_WRITES):
            partner = self._partner(f"PROP-SCOPE-NEW-{index}")
            with self.subTest(vals=vals):
                with self.assertRaises(UserError) as error:
                    Allocation.create(
                        {
                            "sheet_id": self.sheet.id,
                            "partner_id": partner.id,
                            "line_ids": [],
                            **vals,
                        }
                    )
                self._assert_close_guard(error)
                self.assertFalse(
                    Allocation.search(
                        [
                            ("sheet_id", "=", self.sheet.id),
                            ("partner_id", "=", partner.id),
                        ]
                    )
                )

    def test_copying_a_closed_customer_does_not_trip_the_guard(self):
        """The close fields are ``copy=False``: a copy starts open."""
        self.allocation.with_user(self.operator).action_proposal_close(note="Done")
        self.assertTrue(self.allocation.proposal_closed)
        partner = self._partner("PROP-SCOPE-COPY")
        copy = self.allocation.with_user(self.operator).copy({"partner_id": partner.id})
        self.assertEqual(copy.sheet_id, self.sheet)
        self.assertFalse(copy.proposal_closed)
        self.assertFalse(copy.proposal_note)
        self.assertFalse(copy.proposal_closed_uid)
        self.assertFalse(copy.proposal_closed_date)

    def test_board_close_and_reopen_still_write(self):
        allocation = self.allocation.with_user(self.operator)
        allocation.action_proposal_close(note="Checked with the seller")
        self.assertTrue(self.allocation.proposal_closed)
        self.assertEqual(self.allocation.proposal_note, "Checked with the seller")
        self.assertEqual(self.allocation.proposal_closed_uid, self.operator)
        self.assertTrue(self.allocation.proposal_closed_date)
        allocation.action_proposal_reopen()
        self.assertFalse(self.allocation.proposal_closed)
        self.assertFalse(self.allocation.proposal_closed_uid)
        self.assertFalse(self.allocation.proposal_closed_date)
