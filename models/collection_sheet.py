# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import math

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .collection_allocation import DOCUMENT_KINDS, KIND_LABELS

_PROPOSAL_STATE = "proposal"
_SELLER_DEPOSIT = "seller_deposit"
_EVENT_LIMIT = 200


class CollectionSheet(models.Model):
    _inherit = "collection.sheet"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def action_open_receipt_proposal(self):
        self.ensure_one()
        self._ensure_saved_sheet()
        if self.state != _PROPOSAL_STATE:
            raise UserError(
                _(
                    "The receipt proposal board is only available on collection "
                    "sheets in proposal."
                )
            )
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
        if sheet.state != _PROPOSAL_STATE:
            raise UserError(
                _(
                    "The receipt proposal board is only available on collection "
                    "sheets in proposal."
                )
            )
        return sheet

    @api.model
    @api.private
    def _proposal_sheet_error(self):
        return _("A valid collection sheet is required for the receipt proposal board.")

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
    def _proposal_amount(self, amount, maximum):
        self.ensure_one()
        currency = self._proposal_currency()
        try:
            value = float(amount)
        except (TypeError, ValueError) as error:
            raise UserError(_("A valid amount is required.")) from error
        if math.isnan(value) or math.isinf(value):
            raise UserError(_("A valid amount is required."))
        value = currency.round(value)
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
            "pool": [
                voucher._proposal_pool_payload()
                for voucher in vouchers
                if voucher.document_type != _SELLER_DEPOSIT
                and currency.compare_amounts(voucher.proposal_free_amount, 0.0) > 0
            ],
            "events": self._proposal_event_payload(),
        }

    @api.private
    def _proposal_event_payload(self):
        self.ensure_one()
        events = self.env["collection.receipt.proposal.event"].search(
            [("sheet_id", "=", self.id)], limit=_EVENT_LIMIT
        )
        return [
            {
                "id": event.id,
                "allocation_id": event.allocation_id.id or False,
                "voucher_id": event.voucher_id.id or False,
                "event_type": event.event_type,
                "name": event.name or "",
                "description": event.description or "",
                "value_from": event.value_from or "",
                "value_to": event.value_to or "",
                "user_name": event.user_id.display_name or "",
                "event_date": event.event_date and str(event.event_date) or "",
            }
            for event in events
        ]

    # ------------------------------------------------------------------
    # Preview surface (FIFO has exactly one implementation, in Python)
    # ------------------------------------------------------------------

    @api.private
    def _proposal_preview_deltas(self, deltas):
        """Run `_proposal_preview` on every (allocation, kind) budget delta."""
        self.ensure_one()
        previews = []
        Allocation = self.env["collection.allocation"]
        for (allocation_id, kind), delta in deltas.items():
            allocation = Allocation.browse(allocation_id)
            if not allocation.exists() or allocation.proposal_closed:
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
    ):
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
            if voucher.document_type == _SELLER_DEPOSIT:
                raise UserError(
                    _("Seller deposits cannot be assigned from the unassigned pool.")
                )
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
        # Only the typed amount is trusted; client-sent FIFO rows are ignored.
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
        moved = plan["amount"]
        # Shrink the source first: growing the destination while the source
        # still holds the money would trip the sheet-wide split cap.
        sheet._proposal_shrink_value(plan["source_value"], moved)
        merged = False
        if plan["target"]:
            merged = sheet._proposal_grow_value(
                plan["target"], plan["kind"], plan["voucher"], moved
            )
        sheet._proposal_sync_voucher_owner(plan["voucher"])
        sheet._proposal_recompute_deltas(plan["deltas"])
        sheet._proposal_log_transfer(plan, merged)
        return sheet._proposal_board_payload()

    @api.private
    def _proposal_log_transfer(self, plan, merged):
        self.ensure_one()
        voucher = plan["voucher"]
        target = plan["target"]
        source = plan["source_allocation"]
        if not target:
            event_type = "transfer"
            name = _("Card returned to the unassigned pool")
            allocation = source
        elif merged:
            event_type = "unify"
            name = _("Card merged into an existing card")
            allocation = target
        elif source and source == target:
            event_type = "circuit"
            name = _("Card moved to another circuit")
            allocation = target
        elif source:
            partial = (
                self._proposal_currency().compare_amounts(
                    plan["amount"], plan["maximum"]
                )
                < 0
            )
            event_type = "split" if partial else "transfer"
            name = _("Card transferred to another customer")
            allocation = target
        else:
            event_type = "assign"
            name = _("Payment voucher assigned from the pool")
            allocation = target
        self.env["collection.receipt.proposal.event"]._proposal_log(
            self,
            event_type,
            name,
            allocation_id=allocation,
            voucher_id=voucher,
            description=self._proposal_transfer_description(plan),
            value_from=plan["maximum"],
            value_to=plan["amount"],
        )

    @api.private
    def _proposal_transfer_description(self, plan):
        self.ensure_one()
        source = plan["source_allocation"]
        target = plan["target"]
        return "{} -> {}".format(
            self._proposal_pair_label(source, plan["source_kind"]),
            self._proposal_pair_label(target, plan["kind"]),
        )

    @api.model
    @api.private
    def _proposal_pair_label(self, allocation, document_kind):
        if not allocation:
            return _("Unassigned")
        partner = allocation.partner_id.display_name or ""
        if not document_kind:
            return partner
        return f"{partner} / {KIND_LABELS[document_kind]}"

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
        receipt = allocation._proposal_receipt_get_or_create(document_kind)
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
        best = max(
            candidates,
            key=lambda allocation: (
                sum(
                    value.amount or 0.0
                    for value in values
                    if value.receipt_id.allocation_id == allocation
                ),
                allocation.id,
            ),
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
        for allocation_id, kinds in pairs.items():
            allocation = Allocation.browse(allocation_id)
            if allocation.exists():
                allocation._proposal_recompute_kinds(kinds)

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
        plan = sheet._proposal_circuit_plan(value_id, document_kind)
        voucher = plan["value"].voucher_id
        sheet._proposal_shrink_value(plan["value"], plan["amount"])
        sheet._proposal_grow_value(
            plan["allocation"], plan["kind"], voucher, plan["amount"]
        )
        sheet._proposal_sync_voucher_owner(voucher)
        sheet._proposal_recompute_deltas(plan["deltas"])
        sheet.env["collection.receipt.proposal.event"]._proposal_log(
            sheet,
            "circuit",
            _("Card moved to another circuit"),
            allocation_id=plan["allocation"],
            voucher_id=voucher,
            description=plan["allocation"].partner_id.display_name,
            value_from=KIND_LABELS[plan["source_kind"]],
            value_to=KIND_LABELS[plan["kind"]],
        )
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
        plan = sheet._proposal_undo_split_plan(voucher_id, keep_value_id)
        keep = plan["keep"]
        # Drop the other parts first so the sheet-wide cap never sees a
        # transient total above the voucher amount.
        (plan["values"] - keep).unlink()
        keep.amount = plan["total"]
        sheet._proposal_sync_voucher_owner(plan["voucher"])
        sheet._proposal_recompute_deltas(plan["deltas"])
        sheet.env["collection.receipt.proposal.event"]._proposal_log(
            sheet,
            "unify",
            _("Split undone"),
            allocation_id=keep.receipt_id.allocation_id,
            voucher_id=plan["voucher"],
            description=sheet._proposal_pair_label(
                keep.receipt_id.allocation_id, keep.receipt_id.document_kind
            ),
            value_from=len(plan["values"]),
            value_to=1,
        )
        return sheet._proposal_board_payload()

    @api.model
    def action_proposal_impute(
        self, sheet_id=None, allocation_id=None, document_kind=None, lines=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
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
            try:
                value = currency.round(float((item or {}).get("amount") or 0.0))
            except (TypeError, ValueError) as error:
                raise UserError(_("A valid amount is required.")) from error
            if math.isnan(value) or math.isinf(value):
                raise UserError(_("A valid amount is required."))
            if currency.compare_amounts(value, 0.0) < 0:
                raise UserError(_("Applied amounts cannot be negative."))
            if currency.compare_amounts(value, line.invoice_balance or 0.0) > 0:
                raise UserError(
                    _("A document cannot be applied above its outstanding balance.")
                )
            requested[line_id] = value
        if not requested:
            raise UserError(_("A valid document is required."))
        before = sum(line.amount_applied or 0.0 for line in circuit_lines)
        after = sum(
            requested.get(line.id, line.amount_applied or 0.0) for line in circuit_lines
        )
        budget = allocation._proposal_budget(kind)
        if currency.compare_amounts(after, budget) > 0:
            raise UserError(
                _("The circuit cannot apply more than its collected amount.")
            )
        for line_id, value in requested.items():
            by_id[line_id].amount_applied = value
        sheet.env["collection.receipt.proposal.event"]._proposal_log(
            sheet,
            "impute",
            _("Manual imputation to %(kind)s", kind=KIND_LABELS[kind]),
            allocation_id=allocation,
            description=allocation.partner_id.display_name,
            value_from=before,
            value_to=after,
        )
        return sheet._proposal_board_payload()

    @api.model
    def action_proposal_close_customer(
        self, sheet_id=None, allocation_id=None, note=None
    ):
        sheet = self._require_proposal_sheet(sheet_id)
        allocation = sheet._proposal_allocation(allocation_id)
        allocation.action_proposal_close(note=note)
        return sheet._proposal_board_payload()

    @api.model
    def action_proposal_reopen_customer(self, sheet_id=None, allocation_id=None):
        sheet = self._require_proposal_sheet(sheet_id)
        allocation = sheet._proposal_allocation(allocation_id)
        allocation.action_proposal_reopen()
        return sheet._proposal_board_payload()
