# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import math

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import SQL
from odoo.tools.translate import _

from odoo.addons.collection.models.collection_common import privileged

from .collection_allocation import DOCUMENT_KINDS, PROPOSAL_CLOSE_SCOPE

_PROPOSAL_STATE = "proposal"
_SELLER_DEPOSIT = "seller_deposit"
_RETENTION = "retention_certificate"
#: Set by the sheet form's Close button (and only there) to ask for the
#: unfinished-board confirmation. A UX step, not a guard: without it Close
#: behaves exactly as in `collection`, which raw state writes rely on.
CLOSE_CONFIRM_KEY = "receipt_proposal_confirm_close"


class CollectionSheet(models.Model):
    _inherit = "collection.sheet"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def action_open_receipt_proposal(self):
        self.ensure_one()
        self._ensure_saved_sheet()
        self._proposal_ensure_board_state()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "collection_receipt_proposal.action_collection_receipt_proposal"
        )
        action["params"] = dict(action.get("params") or {}, sheet_id=self.id)
        return action

    # ------------------------------------------------------------------
    # Server-side re-validation (never trust the injected params)
    # ------------------------------------------------------------------

    @api.model
    @api.private
    def _require_proposal_sheet(self, sheet_id):
        if isinstance(sheet_id, bool) or not isinstance(sheet_id, int) or sheet_id <= 0:
            raise UserError(self._proposal_sheet_error())
        sheet = self.browse(sheet_id)
        if not sheet.exists():
            raise UserError(self._proposal_sheet_error())
        # `exists()` is a raw SELECT: it answers "is there a row?", never "may
        # this user see it?". Every other gate below reads a field, and a field
        # already in the transaction's cache is served without touching the DB
        # -- so on a warm cache an other-company sheet walked straight past the
        # `ir.rule`. Ask for read access explicitly instead of relying on a
        # query happening to fire.
        sheet.check_access("read")
        sheet._proposal_ensure_board_state()
        return sheet

    @api.model
    @api.private
    def _proposal_sheet_error(self):
        return _("A valid collection sheet is required for the receipt proposal board.")

    @api.private
    def _proposal_ensure_board_state(self):
        """The board exists only between Confirm and Close.

        Every entry point asks the same question, so the message lives here
        once: the sheet form button, the RPC re-validation, and the two
        per-customer actions on `collection.allocation`.
        """
        self.ensure_one()
        if self.state != _PROPOSAL_STATE:
            raise UserError(
                _(
                    "The receipt proposal board is only available on collection "
                    "sheets in proposal."
                )
            )

    @api.private
    def _proposal_allocation(self, allocation_id, required=True):
        self.ensure_one()
        if not allocation_id:
            if required:
                raise UserError(_("A valid customer column is required."))
            return self.env["collection.allocation"]
        if (
            isinstance(allocation_id, bool)
            or not isinstance(allocation_id, int)
            or allocation_id <= 0
        ):
            raise UserError(_("A valid customer column is required."))
        allocation = self.env["collection.allocation"].browse(allocation_id)
        if not allocation.exists() or allocation.sheet_id != self:
            raise UserError(_("A valid customer column is required."))
        return allocation

    @api.private
    def _proposal_value(self, value_id):
        self.ensure_one()
        if isinstance(value_id, bool) or not isinstance(value_id, int) or value_id <= 0:
            raise UserError(_("A valid board card is required."))
        value = self.env["collection.receipt.value"].browse(value_id)
        if not value.exists() or value.receipt_id.sheet_id != self:
            raise UserError(_("A valid board card is required."))
        return value

    @api.private
    def _proposal_voucher(self, voucher_id):
        self.ensure_one()
        if (
            isinstance(voucher_id, bool)
            or not isinstance(voucher_id, int)
            or voucher_id <= 0
        ):
            raise UserError(_("A valid payment voucher is required."))
        voucher = self.env["collection.voucher"].browse(voucher_id)
        if not voucher.exists() or voucher.sheet_id != self:
            raise UserError(_("A valid payment voucher is required."))
        return voucher

    @api.model
    @api.private
    def _proposal_kind(self, document_kind):
        if document_kind not in DOCUMENT_KINDS:
            raise UserError(_("A valid circuit is required."))
        return document_kind

    @api.private
    def _proposal_currency(self):
        self.ensure_one()
        return self.company_id.currency_id or self.env.company.currency_id

    @api.private
    @api.model
    @api.private
    def _proposal_parse_amount(self, amount, currency):
        """A finite float rounded to the currency, or `A valid amount`.

        Shared by the transfer gate and the imputation grid: they differ in
        what they accept afterwards (zero is a legal imputation, never a legal
        transfer), never in how the number is read.
        """
        try:
            value = float(amount)
        except (TypeError, ValueError) as error:
            raise UserError(_("A valid amount is required.")) from error
        if math.isnan(value) or math.isinf(value):
            raise UserError(_("A valid amount is required."))
        return currency.round(value)

    @api.private
    def _proposal_amount(self, amount, maximum):
        self.ensure_one()
        currency = self._proposal_currency()
        value = self._proposal_parse_amount(amount, currency)
        if currency.compare_amounts(value, 0.0) <= 0:
            raise UserError(_("The amount must be greater than zero."))
        if currency.compare_amounts(value, maximum) > 0:
            raise UserError(
                _(
                    "The amount cannot exceed %(maximum)s.",
                    maximum=currency.round(maximum),
                )
            )
        return value

    @api.private
    def _proposal_ensure_column_open(self, allocation):
        self.ensure_one()
        if allocation and allocation.proposal_closed:
            raise UserError(_("This customer is closed on the board. Reopen it first."))

    @api.private
    def _proposal_ensure_retention_stays(self, voucher, target):
        """A retention certificate moves only between its customer's circuits.

        It is tax the customer withheld on their own documents, so it is that
        customer's money by construction: the reset never returns it to the
        pool, and a drag may not hand it to the pool or to another customer
        either. Invoices and quotations of the same customer stay open to it.
        """
        self.ensure_one()
        if voucher.document_type != _RETENTION:
            return
        if not target:
            raise UserError(
                _(
                    "A retention certificate stays with its customer: it cannot "
                    "return to the unassigned pool."
                )
            )
        if target.partner_id != voucher.partner_id:
            raise UserError(
                _(
                    "A retention certificate can only move between the circuits "
                    "of its own customer, %(customer)s.",
                    customer=voucher.partner_id.display_name or "",
                )
            )

    # ------------------------------------------------------------------
    # Concurrency: two operators on one board
    # ------------------------------------------------------------------

    @api.private
    def _proposal_lock(self, vouchers=None, allocations=None):
        """Lock the vouchers and customer columns a move touches, then re-read.

        Each transaction checks the sheet-wide split cap and the circuit
        budget against its own snapshot, so two operators moving the free part
        of the same voucher at the same moment could both pass and both
        commit. Every mutating RPC therefore locks what it is about to touch
        before it validates anything: the vouchers whose money moves and the
        allocations whose circuits are redistributed (a manual imputation and
        a drop on the same circuit share only the column). The caller does
        read first, but only to find those rows (``action_proposal_undo_split``
        reads the voucher's current parts to know their columns); every check
        and every figure comes from what is re-read after the lock. A part
        another operator adds meanwhile still moves money on the same voucher,
        so the voucher row serializes the two. Rows are locked in id order,
        vouchers before allocations, so two moves never deadlock.

        The lock alone is not enough under Odoo's REPEATABLE READ: a
        transaction that took its snapshot before the first one committed
        would wait, then still read the old assignments. The no-op UPDATE
        leaves each row updated by this transaction, so PostgreSQL refuses a
        concurrent one with a serialization failure and Odoo's RPC layer
        retries it on a fresh snapshot -- where the plan sees the money
        already moved and refuses with its normal error. The cache is dropped
        so nothing checked afterwards was read before the lock.
        """
        self.ensure_one()
        self.env.flush_all()
        for table, records in (
            ("collection_voucher", vouchers),
            ("collection_allocation", allocations),
        ):
            ids = tuple(sorted(set(records.ids))) if records else ()
            if not ids:
                continue
            self.env.cr.execute(
                SQL(
                    "SELECT id FROM %s WHERE id IN %s ORDER BY id FOR UPDATE",
                    SQL.identifier(table),
                    ids,
                )
            )
            self.env.cr.execute(
                SQL(
                    "UPDATE %s SET write_date = write_date WHERE id IN %s",
                    SQL.identifier(table),
                    ids,
                )
            )
        self.env.invalidate_all(flush=False)

    @api.private
    def _proposal_lock_card(self, value_id=None, voucher_id=None, allocation_id=None):
        """Lock a board card (or a pool voucher) plus a destination column."""
        self.ensure_one()
        if value_id:
            value = self._proposal_value(value_id)
            vouchers = value.voucher_id
            allocations = value.receipt_id.allocation_id
        else:
            vouchers = self._proposal_voucher(voucher_id)
            allocations = self.env["collection.allocation"]
        allocations |= self._proposal_allocation(allocation_id, required=False)
        self._proposal_lock(vouchers, allocations)

    # ------------------------------------------------------------------
    # Read surface
    # ------------------------------------------------------------------

    @api.model
    def get_proposal_board(self, sheet_id=None):
        sheet = self._require_proposal_sheet(sheet_id)
        return sheet._proposal_board_payload()

    @api.private
    def _proposal_board_payload(self):
        self.ensure_one()
        currency = self._proposal_currency()
        vouchers = self.voucher_ids
        allocations = self.allocation_ids.sorted(
            key=lambda allocation: (allocation.partner_id.display_name or "").lower()
        )
        parts = {}
        for voucher in vouchers:
            parts[voucher.id] = len(voucher.proposal_value_ids)
        return {
            "sheet": {
                "id": self.id,
                "name": self.name,
                "state": self.state,
                "currency": {
                    "id": currency.id,
                    "symbol": currency.symbol or "",
                    "position": currency.position or "before",
                    "decimal_places": currency.decimal_places,
                },
                "editable": self.state == _PROPOSAL_STATE,
            },
            "columns": [
                allocation._proposal_column_payload(parts) for allocation in allocations
            ],
            "pool": self._proposal_pool_cards(currency),
            "document_types": self._proposal_document_types(),
        }

    @api.private
    def _proposal_document_types(self):
        """Every voucher type the company allows, for the board's type filter.

        The filter used to offer only the types the pool held at that moment,
        so assigning the last cheque took the ``check`` option -- and the
        filter set on it -- away under the operator's cursor. The catalog is
        the stable list, and it is read through ``fields_get`` so the labels
        come back translated exactly as ``_selection_document_type`` resolves
        them.
        """
        self.ensure_one()
        selection = self.env["collection.voucher"].fields_get(["document_type"])
        return [
            {"code": code, "label": label}
            for code, label in selection["document_type"]["selection"]
        ]

    @api.private
    def _proposal_pool_cards(self, currency):
        """The unassigned pool, grouped by the voucher's own payment type.

        `Restablecer` empties every circuit into this one column at once, and
        forty cards in sheet order are unreadable -- so the pool is always
        ordered by type, under the same translated label the type filter
        lists its options by, then by date and reference inside each type.
        """
        self.ensure_one()
        cards = [
            voucher._proposal_pool_payload()
            for voucher in self._proposal_pool_vouchers(currency)
        ]
        cards.sort(
            key=lambda card: (
                card["method"].casefold(),
                card["date"],
                card["voucher_name"],
            )
        )
        return cards

    @api.private
    def _proposal_pool_vouchers(self, currency):
        """The vouchers the unassigned pool shows: money not on any card yet.

        One predicate for the pool column and the Close confirmation, so the
        dialog never counts money the operator cannot see on the board.
        """
        self.ensure_one()
        return self.voucher_ids.filtered(
            lambda voucher: currency.compare_amounts(voucher.proposal_free_amount, 0.0)
            > 0
        )

    # ------------------------------------------------------------------
    # Close: warn about an unfinished board (decision D7, warn only)
    # ------------------------------------------------------------------

    @api.private
    def _proposal_close_pending(self):
        """What the board still has open: pool money and unclosed customers."""
        self.ensure_one()
        currency = self._proposal_currency()
        pool = self._proposal_pool_vouchers(currency)
        return {
            "currency": currency,
            "pool_vouchers": pool,
            "pool_amount": currency.round(
                sum(voucher.proposal_free_amount for voucher in pool)
            ),
            "open_allocations": self.allocation_ids.filtered(
                lambda allocation: not allocation.proposal_closed
            ),
        }

    def action_close(self):
        """Close; from the form button, confirm first while the board is open.

        The sheet form's Close button sets `CLOSE_CONFIRM_KEY`. With money
        still in the unassigned pool or customers not closed on the board, it
        gets the confirmation dialog instead, after the same role check and
        the same hard gate Close runs, so the dialog never offers a close that
        would fail. Without the key -- raw state writes, scripts, other
        modules -- Close is exactly `collection`'s.
        """
        if (
            self.env.context.get(CLOSE_CONFIRM_KEY)
            and len(self) == 1
            and self.state == _PROPOSAL_STATE
        ):
            self._check_collection_manager()
            self._raise_if_allocations_over_applied()
            pending = self._proposal_close_pending()
            if pending["pool_vouchers"] or pending["open_allocations"]:
                wizard = self.env["collection.sheet.close.confirm"].create(
                    {"sheet_id": self.id}
                )
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Close Collection Sheet"),
                    "res_model": wizard._name,
                    "res_id": wizard.id,
                    "view_mode": "form",
                    "views": [(False, "form")],
                    "target": "new",
                }
        return super().action_close()

    def action_reset_to_open(self):
        """Reset to Open also reopens every customer closed on the board."""
        closed = self.allocation_ids.filtered("proposal_closed")
        result = super().action_reset_to_open()
        if closed:
            with privileged(PROPOSAL_CLOSE_SCOPE):
                closed.write(
                    {
                        "proposal_closed": False,
                        "proposal_closed_uid": False,
                        "proposal_closed_date": False,
                    }
                )
        return result

    # ------------------------------------------------------------------
    # Preview surface (FIFO has exactly one implementation, in Python)
    # ------------------------------------------------------------------

    @api.private
    def _proposal_preview_deltas(self, deltas):
        """Run `_proposal_preview` on every (allocation, kind) budget delta."""
        self.ensure_one()
        previews = []
        Allocation = self.env["collection.allocation"]
        live = set(Allocation.browse({key[0] for key in deltas}).exists().ids)
        for (allocation_id, kind), delta in deltas.items():
            if allocation_id not in live:
                continue
            allocation = Allocation.browse(allocation_id)
            if allocation.proposal_closed:
                continue
            budget = allocation._proposal_budget(kind) + delta
            preview = allocation._proposal_preview(kind, budget=max(budget, 0.0))
            preview["partner_name"] = allocation.partner_id.display_name or ""
            previews.append(preview)
        return previews

    @api.model
    def preview_proposal_transfer(
        self,
        sheet_id=None,
        value_id=None,
        voucher_id=None,
        to_allocation_id=None,
        document_kind=None,
        amount=None,
        unify=False,
        lines=None,
        changes=None,
    ):
        # Accepted and thrown away on purpose: a stale or hostile client may
        # still post its own FIFO rows, and only the typed amount is trusted.
        # `tests/test_receipt_proposal_actions.py` pins that they are ignored.
        del lines, changes
        sheet = self._require_proposal_sheet(sheet_id)
        plan = sheet._proposal_transfer_plan(
            value_id=value_id,
            voucher_id=voucher_id,
            to_allocation_id=to_allocation_id,
            document_kind=document_kind,
            amount=amount,
            unify=unify,
        )
        return sheet._proposal_preview_deltas(plan["deltas"])

    @api.model
    def preview_proposal_circuit(
        self, sheet_id=None, value_id=None, document_kind=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
        plan = sheet._proposal_circuit_plan(value_id, document_kind)
        return sheet._proposal_preview_deltas(plan["deltas"])

    @api.model
    def preview_proposal_impute(
        self, sheet_id=None, allocation_id=None, document_kind=None
    ):
        """FIFO plan for the manual modal's *Distribuir por antiguedad* button.

        Keeps the board with a single FIFO implementation: the manual modal
        asks the server for the same plan `_proposal_recompute` would apply.
        """
        sheet = self._require_proposal_sheet(sheet_id)
        allocation = sheet._proposal_allocation(allocation_id)
        kind = sheet._proposal_kind(document_kind)
        preview = allocation._proposal_preview(kind)
        preview["partner_name"] = allocation.partner_id.display_name or ""
        return preview

    @api.model
    def preview_proposal_undo_split(
        self, sheet_id=None, voucher_id=None, keep_value_id=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
        plan = sheet._proposal_undo_split_plan(voucher_id, keep_value_id)
        return sheet._proposal_preview_deltas(plan["deltas"])

    # ------------------------------------------------------------------
    # Mutating surface
    # ------------------------------------------------------------------

    @api.private
    def _proposal_transfer_plan(
        self,
        value_id=None,
        voucher_id=None,
        to_allocation_id=None,
        document_kind=None,
        amount=None,
        unify=False,
    ):
        """Validate a transfer and return its budget deltas, without writing."""
        self.ensure_one()
        currency = self._proposal_currency()
        source_value = self._proposal_value(value_id) if value_id else None
        if source_value:
            voucher = source_value.voucher_id
            maximum = source_value.amount or 0.0
            source_allocation = source_value.receipt_id.allocation_id
            source_kind = source_value.receipt_id.document_kind
            self._proposal_ensure_column_open(source_allocation)
        else:
            voucher = self._proposal_voucher(voucher_id)
            maximum = voucher.proposal_free_amount
            source_allocation = self.env["collection.allocation"]
            source_kind = False
            if currency.compare_amounts(maximum, 0.0) <= 0:
                raise UserError(
                    _("This payment voucher has no unassigned amount left.")
                )
        target = self._proposal_allocation(to_allocation_id, required=False)
        if target:
            self._proposal_ensure_column_open(target)
            kind = self._proposal_kind(document_kind)
        else:
            if not source_value:
                raise UserError(_("A valid customer column is required."))
            kind = False
        self._proposal_ensure_retention_stays(voucher, target)
        if target and source_allocation == target and source_kind == kind:
            raise UserError(_("This card is already in that circuit."))
        moved = (
            currency.round(maximum) if unify else self._proposal_amount(amount, maximum)
        )
        deltas = {}
        if source_allocation and source_kind:
            deltas[(source_allocation.id, source_kind)] = -moved
        if target:
            key = (target.id, kind)
            deltas[key] = deltas.get(key, 0.0) + moved
        return {
            "voucher": voucher,
            "source_value": source_value,
            "source_allocation": source_allocation,
            "source_kind": source_kind,
            "target": target,
            "kind": kind,
            "amount": moved,
            "maximum": maximum,
            "deltas": deltas,
        }

    @api.model
    def action_proposal_transfer(
        self,
        sheet_id=None,
        value_id=None,
        voucher_id=None,
        to_allocation_id=None,
        document_kind=None,
        amount=None,
        unify=False,
        lines=None,
        changes=None,
    ):
        # Accepted and thrown away on purpose: a stale or hostile client may
        # still post its own FIFO rows, and only the typed amount is trusted.
        # `tests/test_receipt_proposal_actions.py` pins that they are ignored.
        del lines, changes
        sheet = self._require_proposal_sheet(sheet_id)
        sheet._proposal_lock_card(value_id, voucher_id, to_allocation_id)
        plan = sheet._proposal_transfer_plan(
            value_id=value_id,
            voucher_id=voucher_id,
            to_allocation_id=to_allocation_id,
            document_kind=document_kind,
            amount=amount,
            unify=unify,
        )
        moved = plan["amount"]
        # Shrink the source first: growing the destination while the source
        # still holds the money would trip the sheet-wide split cap.
        sheet._proposal_shrink_value(plan["source_value"], moved)
        if plan["target"]:
            sheet._proposal_grow_value(
                plan["target"], plan["kind"], plan["voucher"], moved
            )
        sheet._proposal_sync_voucher_owner(plan["voucher"])
        sheet._proposal_recompute_deltas(plan["deltas"])
        return sheet._proposal_board_payload()

    @api.private
    def _proposal_shrink_value(self, value, amount):
        """Reduce a card by `amount`, unlinking it when nothing is left."""
        self.ensure_one()
        if not value:
            return
        value._shrink_or_unlink(amount)

    @api.private
    def _proposal_grow_value(self, allocation, document_kind, voucher, amount):
        """Add `amount` to the (allocation, kind) card of `voucher`.

        Returns True when the money merged into an existing card.
        """
        self.ensure_one()
        receipt = allocation._receipt_get_or_create(document_kind)
        return self.env["collection.receipt.value"]._grow_voucher_amount(
            receipt, voucher, amount
        )

    @api.private
    def _proposal_sync_voucher_owner(self, voucher):
        """Re-point `voucher.allocation_id` at the largest assigned share.

        While this addon is installed, same-sheet partner mismatch is allowed so
        the owner can be another customer's allocation. Cross-sheet and
        no-share pointers still fail the inherited partner constraints.
        `seller_deposit` is never given an owner here. Replaced cash with no
        remaining values keeps its current `allocation_id`.
        """
        self.ensure_one()
        if voucher.document_type == _SELLER_DEPOSIT:
            return
        values = voucher.proposal_value_ids
        candidates = values.receipt_id.allocation_id
        if not candidates:
            if voucher.allocation_id:
                replaced = voucher.replaced_amount or 0.0
                if voucher.currency_id.compare_amounts(replaced, 0.0) > 0:
                    return
                voucher.allocation_id = False
            return
        # One pass over the values instead of one pass per candidate: the
        # comprehension inside `max(key=...)` re-read `receipt_id.allocation_id`
        # for every (candidate, value) pair.
        shares = dict.fromkeys(candidates.ids, 0.0)
        for value in values:
            allocation_id = value.receipt_id.allocation_id.id
            if allocation_id in shares:
                shares[allocation_id] += value.amount or 0.0
        best = max(
            candidates, key=lambda allocation: (shares[allocation.id], allocation.id)
        )
        if voucher.allocation_id != best:
            voucher.allocation_id = best

    @api.private
    def _proposal_recompute_deltas(self, deltas):
        """Run a full FIFO redistribution on every touched (allocation, kind)."""
        self.ensure_one()
        Allocation = self.env["collection.allocation"]
        pairs = {}
        for allocation_id, kind in deltas:
            pairs.setdefault(allocation_id, []).append(kind)
        # One existence query for the whole batch instead of one per allocation.
        live = set(Allocation.browse(pairs).exists().ids)
        for allocation_id, kinds in pairs.items():
            if allocation_id in live:
                Allocation.browse(allocation_id)._proposal_recompute_kinds(kinds)

    @api.private
    def _proposal_circuit_plan(self, value_id, document_kind):
        self.ensure_one()
        value = self._proposal_value(value_id)
        allocation = value.receipt_id.allocation_id
        self._proposal_ensure_column_open(allocation)
        kind = self._proposal_kind(document_kind)
        source_kind = value.receipt_id.document_kind
        if kind == source_kind:
            raise UserError(_("This card is already in that circuit."))
        amount = value.amount or 0.0
        return {
            "value": value,
            "allocation": allocation,
            "source_kind": source_kind,
            "kind": kind,
            "amount": amount,
            "deltas": {
                (allocation.id, source_kind): -amount,
                (allocation.id, kind): amount,
            },
        }

    @api.model
    def action_proposal_set_circuit(
        self, sheet_id=None, value_id=None, document_kind=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
        sheet._proposal_lock_card(value_id=value_id)
        plan = sheet._proposal_circuit_plan(value_id, document_kind)
        voucher = plan["value"].voucher_id
        sheet._proposal_shrink_value(plan["value"], plan["amount"])
        sheet._proposal_grow_value(
            plan["allocation"], plan["kind"], voucher, plan["amount"]
        )
        sheet._proposal_sync_voucher_owner(voucher)
        sheet._proposal_recompute_deltas(plan["deltas"])
        return sheet._proposal_board_payload()

    @api.private
    def _proposal_undo_split_plan(self, voucher_id, keep_value_id):
        self.ensure_one()
        voucher = self._proposal_voucher(voucher_id)
        values = voucher.proposal_value_ids
        if len(values) < 2:
            raise UserError(_("This payment voucher is not split."))
        keep = self._proposal_value(keep_value_id)
        if keep not in values:
            raise UserError(_("A valid board card is required."))
        self._proposal_ensure_retention_stays(voucher, keep.receipt_id.allocation_id)
        deltas = {}
        for value in values:
            allocation = value.receipt_id.allocation_id
            self._proposal_ensure_column_open(allocation)
            key = (allocation.id, value.receipt_id.document_kind)
            deltas[key] = deltas.get(key, 0.0) - (value.amount or 0.0)
        total = sum(value.amount or 0.0 for value in values)
        keep_key = (keep.receipt_id.allocation_id.id, keep.receipt_id.document_kind)
        deltas[keep_key] = deltas.get(keep_key, 0.0) + total
        return {
            "voucher": voucher,
            "values": values,
            "keep": keep,
            "total": total,
            "deltas": deltas,
        }

    @api.model
    def action_proposal_undo_split(
        self, sheet_id=None, voucher_id=None, keep_value_id=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
        voucher = sheet._proposal_voucher(voucher_id)
        sheet._proposal_lock(
            voucher, voucher.proposal_value_ids.receipt_id.allocation_id
        )
        plan = sheet._proposal_undo_split_plan(voucher_id, keep_value_id)
        keep = plan["keep"]
        # Drop the other parts first so the sheet-wide cap never sees a
        # transient total above the voucher amount.
        (plan["values"] - keep).unlink()
        keep.amount = plan["total"]
        sheet._proposal_sync_voucher_owner(plan["voucher"])
        sheet._proposal_recompute_deltas(plan["deltas"])
        return sheet._proposal_board_payload()

    @api.model
    def action_proposal_impute(
        self, sheet_id=None, allocation_id=None, document_kind=None, lines=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
        sheet._proposal_lock(allocations=sheet._proposal_allocation(allocation_id))
        allocation = sheet._proposal_allocation(allocation_id)
        sheet._proposal_ensure_column_open(allocation)
        kind = sheet._proposal_kind(document_kind)
        currency = sheet._proposal_currency()
        circuit_lines = allocation._proposal_kind_lines(kind)
        by_id = {line.id: line for line in circuit_lines}
        requested = {}
        for item in lines or []:
            line_id = (item or {}).get("line_id")
            if line_id not in by_id:
                raise UserError(_("A valid document is required."))
            line = by_id[line_id]
            value = sheet._proposal_parse_amount(
                (item or {}).get("amount") or 0.0, currency
            )
            if currency.compare_amounts(value, 0.0) < 0:
                raise UserError(_("Applied amounts cannot be negative."))
            if currency.compare_amounts(value, line.invoice_balance or 0.0) > 0:
                raise UserError(
                    _("A document cannot be applied above its outstanding balance.")
                )
            requested[line_id] = value
        if not requested:
            raise UserError(_("A valid document is required."))
        after = sum(
            requested.get(line.id, line.amount_applied or 0.0) for line in circuit_lines
        )
        budget = allocation._proposal_budget(kind)
        if currency.compare_amounts(after, budget) > 0:
            raise UserError(
                _("The circuit cannot apply more than its collected amount.")
            )
        # Falling documents first: the end state fits the budget, and core
        # refuses an intermediate write that raises the circuit past it.
        for line_id, value in sorted(
            requested.items(),
            key=lambda item: currency.compare_amounts(
                item[1], by_id[item[0]].amount_applied or 0.0
            )
            > 0,
        ):
            by_id[line_id].amount_applied = value
        return sheet._proposal_board_payload()

    # ------------------------------------------------------------------
    # Reset: every assignable card back to the unassigned pool
    # ------------------------------------------------------------------

    @api.private
    def _proposal_reset_plan(self):
        """Every returnable card on this sheet, with its budget deltas.

        `retention_certificate` is the one type that never goes back: a
        retention is tax the customer withheld on their own documents, so it
        is that customer's money by construction and a board-wide button MUST
        NOT offer it to anybody else. Everything else returns, remittance
        included -- a `seller_deposit` holding free money is a pool card like
        any other, and the cash it replaced stays off the pool on its own
        `replaced_amount`, so the pool total never double-counts the move.
        Resetting is a board-wide action, so a closed customer blocks it by
        name rather than being silently skipped: a partial reset would leave
        the operator with a pool that does not hold what the button promised.
        """
        self.ensure_one()
        Value = self.env["collection.receipt.value"]
        values = Value.browse()
        deltas = {}
        customers = set()
        closed = []
        for allocation in self.allocation_ids:
            movable = allocation.receipt_ids.value_ids.filtered(
                lambda value: value.voucher_id.document_type != _RETENTION
            )
            if not movable:
                continue
            if allocation.proposal_closed:
                closed.append(allocation.partner_id.display_name or "")
                continue
            customers.add(allocation.id)
            values |= movable
            for value in movable:
                key = (allocation.id, value.receipt_id.document_kind)
                deltas[key] = deltas.get(key, 0.0) - (value.amount or 0.0)
        if closed:
            raise UserError(
                _(
                    "Reopen these customers before resetting the board: %(names)s",
                    names=", ".join(sorted(closed)),
                )
            )
        return {
            "values": values,
            "vouchers": values.voucher_id,
            "customers": len(customers),
            "deltas": deltas,
            "amount": sum(value.amount or 0.0 for value in values),
        }

    @api.model
    def action_proposal_reset_vouchers(self, sheet_id=None):
        sheet = self._require_proposal_sheet(sheet_id)
        sheet._proposal_lock(sheet.voucher_ids, sheet.allocation_ids)
        plan = sheet._proposal_reset_plan()
        values = plan["values"]
        if not values:
            raise UserError(
                _(
                    "Every payment voucher that can be returned is already in "
                    "the unassigned pool."
                )
            )
        vouchers = plan["vouchers"]
        # Nothing grows here, so the sheet-wide split cap only ever sees the
        # assigned total going down -- the same order every mutation keeps.
        values.unlink()
        for voucher in vouchers:
            sheet._proposal_sync_voucher_owner(voucher)
        # Emptied circuits still have to be redistributed: FIFO on a budget of
        # zero is what clears `amount_applied` off every document.
        sheet._proposal_recompute_deltas(plan["deltas"])
        return sheet._proposal_board_payload()

    @api.model
    def action_proposal_close_customer(
        self, sheet_id=None, allocation_id=None, note=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
        sheet._proposal_lock(allocations=sheet._proposal_allocation(allocation_id))
        allocation = sheet._proposal_allocation(allocation_id)
        allocation.action_proposal_close(note=note)
        return sheet._proposal_board_payload()

    @api.model
    def action_proposal_reopen_customer(self, sheet_id=None, allocation_id=None):
        sheet = self._require_proposal_sheet(sheet_id)
        sheet._proposal_lock(allocations=sheet._proposal_allocation(allocation_id))
        allocation = sheet._proposal_allocation(allocation_id)
        allocation.action_proposal_reopen()
        return sheet._proposal_board_payload()
