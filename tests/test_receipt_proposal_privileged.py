# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Board events and close fields trust an in-process scope, not context keys.

JSON-RPC and muk_mcp both merge a caller-supplied ``context``, so a forged key
must not let a Collections User write the audit trail or the close fields.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon

_EVENT_MODEL = "collection.receipt.proposal.event"
_CLOSE_GUARD_MESSAGE = (
    "Customers can only be closed or reopened from the receipt proposal board."
)
_EVENT_GUARD_MESSAGE = (
    "Proposal events can only be created by the receipt proposal board."
)
_CLOSE_FIELD_WRITES = (
    {"proposal_closed": True},
    {"proposal_note": "Forged note"},
    {"proposal_closed_date": "2020-01-01 00:00:00"},
)


class TestReceiptProposalPrivileged(ReceiptProposalCommon, TransactionCase):
    """Forged keys MUST NOT write board events or per-customer close fields."""

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

    def _sheet_events(self):
        return self.env[_EVENT_MODEL].search([("sheet_id", "=", self.sheet.id)])

    def test_forged_event_key_cannot_write_the_audit_trail(self):
        before = self._sheet_events()
        Event = (
            self.env[_EVENT_MODEL]
            .with_user(self.operator)
            .with_context(collection_receipt_proposal_event=True)
        )
        with self.assertRaises(UserError) as error:
            Event.create(
                {
                    "sheet_id": self.sheet.id,
                    "allocation_id": self.allocation.id,
                    "event_type": "close",
                    "name": "Forged close",
                    "user_id": self.other.id,
                    "event_date": "2020-01-01 00:00:00",
                }
            )
        self.assertIs(type(error.exception), UserError)
        self.assertEqual(str(error.exception), _EVENT_GUARD_MESSAGE)
        self.assertEqual(self._sheet_events(), before)

    def test_board_events_ignore_forged_default_context_keys(self):
        """A legitimate board call MUST NOT log under a caller-chosen author."""
        before = self._sheet_events()
        self.allocation.with_user(self.operator).with_context(
            default_user_id=self.other.id,
            default_event_date="2020-01-01 00:00:00",
            default_description="Forged description",
        ).action_proposal_close(note="Checked")
        event = self._sheet_events() - before
        self.assertEqual(len(event), 1)
        self.assertEqual(event.event_type, "close")
        self.assertEqual(event.user_id, self.operator)
        self.assertEqual(event.description, "Checked")
        self.assertGreater(event.event_date.year, 2020)

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

    def test_board_close_and_reopen_still_write_and_log(self):
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
        events = self._sheet_events().filtered(
            lambda event: event.event_type in ("close", "reopen")
            and event.allocation_id == self.allocation
        )
        self.assertEqual(set(events.mapped("event_type")), {"close", "reopen"})
        self.assertEqual(events.user_id, self.operator)
