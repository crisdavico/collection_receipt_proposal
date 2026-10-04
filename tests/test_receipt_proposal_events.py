# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import inspect
from pathlib import Path

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase

from .common import ReceiptProposalCommon

_EVENT_TYPES = {
    "assign",
    "transfer",
    "split",
    "unify",
    "circuit",
    "impute",
    "auto_impute",
    "reset",
    "close",
    "reopen",
}
_EVENT_MODEL = "collection.receipt.proposal.event"
_EVENT_CONTEXT = "collection_receipt_proposal_event"


class TestReceiptProposalEvents(ReceiptProposalCommon, TransactionCase):
    """RED/GREEN: gated create; write/unlink refuse except cascade; newest-first."""

    def setUp(self):
        super().setUp()
        self.scenario = self._board_scenario()
        self.sheet = self.scenario["sheet"]
        self.Event = self.env[_EVENT_MODEL]

    def _event_vals(self, **extra):
        vals = {
            "sheet_id": self.sheet.id,
            "event_type": "assign",
            "name": "Manual event",
        }
        vals.update(extra)
        return vals

    def _gated_create(self, **extra):
        return self.Event.with_context(**{_EVENT_CONTEXT: True}).create(
            self._event_vals(**extra)
        )

    def test_create_is_gated_on_the_context_key(self):
        """RED/GREEN: a bare create raises; the gated create succeeds."""
        with self.assertRaises(UserError):
            self.Event.create(self._event_vals())
        event = self._gated_create()
        self.assertTrue(event.exists())
        self.assertEqual(event.sheet_id, self.sheet)

    def test_transfer_type_stores_sheet_user_timestamp_and_company(self):
        """RED/GREEN: gated transfer create stamps sheet, type, user, date, company."""
        event = self._gated_create(event_type="transfer", name="Moved card")
        self.assertEqual(event.sheet_id, self.sheet)
        self.assertEqual(event.event_type, "transfer")
        self.assertEqual(event.user_id, self.env.user)
        self.assertTrue(event.event_date)
        self.assertEqual(event.company_id, self.sheet.company_id)
        company_field = self.Event._fields["company_id"]
        self.assertEqual(company_field.related, "sheet_id.company_id")
        self.assertTrue(company_field.store)
        self.assertTrue(company_field.required)
        self.assertTrue(company_field.precompute)
        self.assertTrue(company_field.index)

    def test_event_type_selection_is_closed_and_invalid_refuses(self):
        """RED/GREEN: only the ten coded types persist; anything else refuses."""
        types = {key for key, _label in self.Event._fields["event_type"].selection}
        self.assertEqual(types, _EVENT_TYPES)
        with self.assertRaises(ValueError):
            self._gated_create(event_type="pay")

    def test_write_raises_and_leaves_row_unchanged(self):
        """RED/GREEN: events are immutable; stored fields stay as created."""
        event = self._gated_create(event_type="transfer", name="Keep me")
        with self.assertRaises(UserError):
            event.write({"name": "Rewritten", "event_type": "assign"})
        self.assertEqual(event.name, "Keep me")
        self.assertEqual(event.event_type, "transfer")

    def test_unlink_raises_except_sheet_cascade(self):
        """RED/GREEN: direct unlink refuses; open-sheet cascade removes the rows."""
        event = self._gated_create(name="Keep on proposal")
        event_id = event.id
        with self.assertRaises(UserError):
            event.unlink()
        leftover = self.Event.browse(event_id)
        self.assertTrue(leftover.exists())
        self.assertEqual(leftover.name, "Keep on proposal")

        open_sheet = self._create_sheet(force_new=True)
        cascaded = self.Event.with_context(**{_EVENT_CONTEXT: True}).create(
            {
                "sheet_id": open_sheet.id,
                "event_type": "assign",
                "name": "Will cascade",
            }
        )
        cascaded_id = cascaded.id
        open_sheet.unlink()
        self.assertFalse(self.Event.browse(cascaded_id).exists())
        self.assertTrue(self.Event.browse(event_id).exists())

    def test_order_is_newest_first(self):
        """RED/GREEN: default search returns E2 before E1 on the same sheet."""
        self.assertEqual(self.Event._order, "event_date desc, id desc")
        first = self._gated_create(
            name="E1",
            event_date="2026-01-01 10:00:00",
        )
        second = self._gated_create(
            name="E2",
            event_date="2026-01-01 11:00:00",
        )
        ordered = self.Event.search([("sheet_id", "=", self.sheet.id)])
        self.assertGreaterEqual(len(ordered), 2)
        self.assertEqual(ordered[0], second)
        self.assertEqual(ordered[1], first)
        self.assertEqual(ordered.mapped("name")[:2], ["E2", "E1"])

    def test_access_rights_are_read_and_create_only(self):
        """RED/GREEN: `base.group_user` gets read + create, nothing else."""
        self._assert_acl(_EVENT_MODEL, (1, 0, 1, 0))

    def test_company_rule_is_global_noupdate(self):
        """RED/GREEN: isolation is one global multi-company `ir.rule`."""
        self._assert_global_company_rule(_EVENT_MODEL)
        rule = self.env.ref(
            "collection_receipt_proposal.collection_receipt_proposal_event_company_rule"
        )
        self.assertFalse(rule.groups)
        xmlid = self.env["ir.model.data"].search(
            [
                ("module", "=", "collection_receipt_proposal"),
                ("name", "=", "collection_receipt_proposal_event_company_rule"),
            ]
        )
        self.assertTrue(xmlid)
        self.assertTrue(xmlid.noupdate)

    def test_internal_user_reads_and_creates_without_sudo(self):
        """RED/GREEN: internal users may read and gated-create; unlink ACL deny."""
        internal = self._create_user("prop_evt_internal", "base.group_user")
        Event = self.Event.with_user(internal)
        with self.assertRaises(UserError):
            Event.create(self._event_vals(name="Ungated"))
        event = Event.with_context(**{_EVENT_CONTEXT: True}).create(
            self._event_vals(name="Internal create")
        )
        self.assertTrue(event.exists())
        self.assertEqual(event.user_id, internal)
        read = Event.browse(event.id).read(["name", "event_type"])
        self.assertEqual(read[0]["name"], "Internal create")
        self.assertEqual(read[0]["event_type"], "assign")
        # Immutability raises before ACL; write is refused for every user.
        with self.assertRaises(UserError):
            Event.browse(event.id).write({"name": "nope"})
        self.assertEqual(event.name, "Internal create")
        with self.assertRaises(AccessError):
            Event.browse(event.id).unlink()
        self.assertTrue(event.exists())

    def test_other_company_events_hidden(self):
        """RED/GREEN: events outside company_ids MUST NOT be visible."""
        user = self._create_user("prop_evt_home", "base.group_user")
        self._restrict_user_to_company(user, self.env.company)
        visible = self._gated_create(name="Home event")

        company_b = self._create_company("Proposal Event Hidden Co")
        seller_b = self._create_user("prop_evt_seller_b", "base.group_user")
        sheet_b = self._create_sheet(seller_id=seller_b.id, company_id=company_b.id)
        hidden = self.Event.with_context(**{_EVENT_CONTEXT: True}).create(
            {
                "sheet_id": sheet_b.id,
                "event_type": "transfer",
                "name": "Hidden event",
            }
        )
        self.assertEqual(hidden.company_id, company_b)
        EventHome = self.Event.with_user(user)
        self.assertTrue(EventHome.search([("id", "=", visible.id)]))
        self._assert_hidden_from_user(user, hidden, ["name", "id"])

    def test_no_dedicated_groups_and_never_sudo(self):
        """RED/GREEN: this addon adds no groups and never calls sudo()."""
        self.assertFalse(
            self.env["ir.model.data"].search(
                [
                    ("module", "=", "collection_receipt_proposal"),
                    ("model", "=", "res.groups"),
                ]
            )
        )
        models_root = Path(__file__).resolve().parents[1] / "models"
        sources = [
            path.read_text(encoding="utf-8")
            for path in sorted(models_root.glob("*.py"))
            if path.name != "__init__.py"
        ]
        event_cls = type(self.Event)
        sources.extend(
            [
                inspect.getsource(event_cls.create),
                inspect.getsource(event_cls.write),
                inspect.getsource(event_cls._unlink_forbidden),
                inspect.getsource(event_cls._proposal_log),
            ]
        )
        for source in sources:
            code_lines = [
                line
                for line in source.splitlines()
                if not line.lstrip().startswith("#")
            ]
            code = "\n".join(code_lines)
            self.assertNotIn(".sudo(", code)
            self.assertNotIn("sudo()", code)
