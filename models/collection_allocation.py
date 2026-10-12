# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from odoo.addons.collection.models.collection_common import is_privileged, privileged

DOCUMENT_KINDS = ("invoice", "quotation")
KIND_LABELS = {"invoice": "Invoices", "quotation": "Quotations"}
# Per-customer close state. Only the board's close/reopen actions write it,
# inside this privileged scope, so the note rule and the event log always run.
PROPOSAL_CLOSE_SCOPE = "collection_receipt_proposal_close"
PROPOSAL_CLOSE_FIELDS = frozenset(
    {
        "proposal_closed",
        "proposal_note",
        "proposal_closed_uid",
        "proposal_closed_date",
    }
)


class CollectionAllocation(models.Model):
    _inherit = "collection.allocation"

    proposal_closed = fields.Boolean(copy=False)
    proposal_note = fields.Text(copy=False)
    proposal_closed_uid = fields.Many2one(
        comodel_name="res.users",
        string="Closed By",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    proposal_closed_date = fields.Datetime(readonly=True, copy=False)

    proposal_collected_invoice = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_collected_quotation = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_applied_invoice = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_applied_quotation = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_available_invoice = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_available_quotation = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_total_invoice = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_total_quotation = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_pending_invoice = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_pending_quotation = fields.Monetary(
        compute="_compute_proposal_figures",
        currency_field="currency_id",
    )
    proposal_status = fields.Selection(
        selection=[
            ("sin_iniciar", "Not started"),
            ("parcial", "Partial"),
            ("conciliado", "Reconciled"),
            ("a_favor", "Credit balance"),
            ("deuda", "Outstanding debt"),
            ("cruce", "Circuit overdraft"),
            ("cerrado", "Closed"),
        ],
        compute="_compute_proposal_figures",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not is_privileged(PROPOSAL_CLOSE_SCOPE) and any(
            vals.get(name) for vals in vals_list for name in PROPOSAL_CLOSE_FIELDS
        ):
            raise self._proposal_close_fields_error()
        return super().create(vals_list)

    def write(self, vals):
        if PROPOSAL_CLOSE_FIELDS & set(vals) and not is_privileged(
            PROPOSAL_CLOSE_SCOPE
        ):
            raise self._proposal_close_fields_error()
        return super().write(vals)

    @api.model
    @api.private
    def _proposal_close_fields_error(self):
        return UserError(
            _(
                "Customers can only be closed or reopened from the receipt "
                "proposal board."
            )
        )

    @api.depends(
        "proposal_closed",
        "currency_id",
        "receipt_ids.document_kind",
        "receipt_ids.value_ids.amount",
        "line_ids.document_kind",
        "line_ids.amount_applied",
        "line_ids.invoice_balance",
    )
    def _compute_proposal_figures(self):
        for allocation in self:
            figures = {}
            for kind in DOCUMENT_KINDS:
                figures[kind] = allocation._proposal_kind_figures(kind)
            for kind in DOCUMENT_KINDS:
                data = figures[kind]
                allocation[f"proposal_collected_{kind}"] = data["collected"]
                allocation[f"proposal_applied_{kind}"] = data["applied"]
                allocation[f"proposal_available_{kind}"] = data["available"]
                allocation[f"proposal_total_{kind}"] = data["total"]
                allocation[f"proposal_pending_{kind}"] = data["pending"]
            allocation.proposal_status = allocation._proposal_status_value(figures)

    @api.private
    def _proposal_kind_figures(self, document_kind, lines=None):
        """Collected / applied / available / total / pending for one circuit.

        `lines` lets a caller that already sorted this circuit's documents hand
        them over; the board payload needs both the figures and the rows, and
        `_proposal_kind_lines` filters and sorts on every call.
        """
        self.ensure_one()
        collected = self._proposal_budget(document_kind)
        applied = 0.0
        total = 0.0
        if lines is None:
            lines = self._proposal_kind_lines(document_kind)
        for line in lines:
            applied += line.amount_applied or 0.0
            total += line.invoice_balance or 0.0
        return {
            "collected": collected,
            "applied": applied,
            "available": collected - applied,
            "total": total,
            "pending": total - applied,
        }

    @api.private
    def _proposal_status_value(self, figures):
        """Mirror the mockup's `calc()` status ladder."""
        self.ensure_one()
        if self.proposal_closed:
            return "cerrado"
        currency = self.currency_id
        applied = sum(figures[kind]["applied"] for kind in DOCUMENT_KINDS)
        available = sum(figures[kind]["available"] for kind in DOCUMENT_KINDS)
        debt = figures["invoice"]["pending"]
        overdraft = any(
            self._proposal_compare(currency, figures[kind]["available"], 0.0) < 0
            for kind in DOCUMENT_KINDS
        )
        if not self._proposal_compare(currency, applied, 0.0):
            return "sin_iniciar"
        if overdraft:
            return "cruce"
        available_sign = self._proposal_compare(currency, available, 0.0)
        debt_sign = self._proposal_compare(currency, debt, 0.0)
        if available_sign > 0 and debt_sign <= 0:
            return "a_favor"
        if available_sign <= 0 and debt_sign > 0:
            return "deuda"
        if available_sign == 0 and debt_sign == 0:
            return "conciliado"
        return "parcial"

    @api.private
    def _proposal_kind_status(self, document_kind, figures=None):
        """`_proposal_status_value`'s ladder restricted to a single circuit.

        The allocation-level status answers "is this customer done?"; a report
        that lists one row per circuit needs the same verdict per circuit. Debt
        here is that circuit's own `pending`, not only the invoice one.
        """
        self.ensure_one()
        if self.proposal_closed:
            return "cerrado"
        if figures is None:
            figures = self._proposal_kind_figures(document_kind)
        currency = self.currency_id
        applied = self._proposal_compare(currency, figures["applied"], 0.0)
        available = self._proposal_compare(currency, figures["available"], 0.0)
        pending = self._proposal_compare(currency, figures["pending"], 0.0)
        if not applied:
            return "sin_iniciar"
        if available < 0:
            return "cruce"
        if available > 0 and pending <= 0:
            return "a_favor"
        if available <= 0 and pending > 0:
            return "deuda"
        if available == 0 and pending == 0:
            return "conciliado"
        return "parcial"

    @api.model
    @api.private
    def _proposal_compare(self, currency, first, second):
        if currency:
            return currency.compare_amounts(first, second)
        return (first > second) - (first < second)

    # ------------------------------------------------------------------
    # FIFO engine
    # ------------------------------------------------------------------

    @api.model
    @api.private
    def _proposal_fifo_key(self, line):
        """MUST mirror `collection.receipt._compute_line_ids` exactly."""
        return (line.due_date or date.max, line.invoice_number or "")

    @api.private
    def _proposal_kind_lines(self, document_kind):
        """This allocation's documents of one circuit, oldest due date first."""
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line, kind=document_kind: line.document_kind == kind
        )
        return lines.sorted(key=self._proposal_fifo_key)

    @api.private
    def _proposal_receipt(self, document_kind):
        self.ensure_one()
        return self.receipt_ids.filtered(
            lambda receipt, kind=document_kind: receipt.document_kind == kind
        )[:1]

    @api.private
    def _proposal_budget(self, document_kind):
        """The circuit's collected money: its receipt `total_values`."""
        self.ensure_one()
        receipt = self._proposal_receipt(document_kind)
        return receipt.total_values if receipt else 0.0

    @api.private
    def _proposal_fifo_plan(self, document_kind, budget):
        """`{line_id: amount}` plus the surplus the documents could not absorb.

        Oldest due date first, each document capped at `invoice_balance`,
        partial fill on the last document reached.
        """
        self.ensure_one()
        currency = self.currency_id
        rest = currency.round(budget) if currency else budget
        plan = {}
        for line in self._proposal_kind_lines(document_kind):
            ceiling = max(line.invoice_balance or 0.0, 0.0)
            use = max(0.0, min(rest, ceiling))
            if currency:
                use = currency.round(use)
            plan[line.id] = use
            rest -= use
            if currency:
                rest = currency.round(rest)
        return plan, max(rest, 0.0)

    @api.private
    def _proposal_preview(self, document_kind, budget=None):
        """Non-mutating FIFO simulation for one (allocation, circuit) pair."""
        self.ensure_one()
        if budget is None:
            budget = self._proposal_budget(document_kind)
        currency = self.currency_id
        lines = self._proposal_kind_lines(document_kind)
        plan, surplus = self._proposal_fifo_plan(document_kind, budget)
        applied = 0.0
        pending = 0.0
        changes = []
        for line in lines:
            target = plan.get(line.id, 0.0)
            current = line.amount_applied or 0.0
            applied += target
            pending += max((line.invoice_balance or 0.0) - target, 0.0)
            if self._proposal_compare(currency, target, current):
                changes.append(
                    {
                        "line_id": line.id,
                        "number": line.invoice_number or line.external_invoice_id or "",
                        "date": line.due_date and str(line.due_date) or "",
                        "from": current,
                        "to": target,
                    }
                )
        return {
            "allocation_id": self.id,
            "document_kind": document_kind,
            "budget": budget,
            "surplus": surplus,
            "applied": applied,
            "pending": pending,
            "no_documents": not lines
            and self._proposal_compare(currency, budget, 0.0) > 0,
            "changes": changes,
        }

    @api.private
    def _proposal_recompute(self, document_kind):
        """Apply the FIFO plan to `line.amount_applied`; closed columns freeze."""
        self.ensure_one()
        if self.proposal_closed:
            return None
        preview = self._proposal_preview(document_kind)
        if not preview["changes"]:
            return preview
        Line = self.env["collection.allocation.line"]
        # Group by the value written: lines landing on the same amount go out
        # as one UPDATE instead of one per document.
        by_amount = {}
        for change in preview["changes"]:
            by_amount.setdefault(change["to"], []).append(change["line_id"])
        for amount, line_ids in by_amount.items():
            Line.browse(line_ids).amount_applied = amount
        self._proposal_log_recompute(document_kind, preview)
        return preview

    @api.private
    def _proposal_log_recompute(self, document_kind, preview):
        self.ensure_one()
        moved = len(preview["changes"])
        self.env["collection.receipt.proposal.event"]._proposal_log(
            self.sheet_id,
            "auto_impute",
            _(
                "Automatic imputation to %(kind)s (oldest debt first)",
                kind=KIND_LABELS[document_kind],
            ),
            allocation_id=self,
            description=_(
                "%(partner)s - %(count)s document(s)",
                partner=self.partner_id.display_name,
                count=moved,
            ),
            value_from=sum(change["from"] for change in preview["changes"]),
            value_to=sum(change["to"] for change in preview["changes"]),
        )

    @api.private
    def _proposal_recompute_kinds(self, document_kinds):
        """Recompute a set of circuits on this allocation, ignoring blanks."""
        self.ensure_one()
        results = []
        for kind in dict.fromkeys(
            kind for kind in document_kinds if kind in DOCUMENT_KINDS
        ):
            result = self._proposal_recompute(kind)
            if result:
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # Per-customer close
    # ------------------------------------------------------------------

    @api.private
    def _proposal_has_differences(self):
        """Whether any circuit still shows money unapplied, overdrawn or owed.

        Closing with a difference is allowed, but only with a note, and that
        is the one question asked of this: the caller never named a figure.
        """
        self.ensure_one()
        currency = self.currency_id
        for kind in DOCUMENT_KINDS:
            figures = self._proposal_kind_figures(kind)
            if self._proposal_compare(currency, figures["available"], 0.0) != 0:
                return True
            if self._proposal_compare(currency, figures["pending"], 0.0) > 0:
                return True
        return False

    def action_proposal_close(self, note=None):
        self.ensure_one()
        self.sheet_id._proposal_ensure_board_state()
        if self.proposal_closed:
            raise UserError(_("This customer is already closed on the board."))
        note = (note or "").strip()
        if self._proposal_has_differences() and not note:
            raise UserError(_("Closing a customer with differences requires a note."))
        with privileged(PROPOSAL_CLOSE_SCOPE):
            self.write(
                {
                    "proposal_closed": True,
                    "proposal_note": note,
                    "proposal_closed_uid": self.env.user.id,
                    "proposal_closed_date": fields.Datetime.now(),
                }
            )
        self.env["collection.receipt.proposal.event"]._proposal_log(
            self.sheet_id,
            "close",
            _("Customer closed on the board"),
            allocation_id=self,
            description=note or self.partner_id.display_name,
            value_from="open",
            value_to="closed",
        )
        return True

    def action_proposal_reopen(self):
        self.ensure_one()
        self.sheet_id._proposal_ensure_board_state()
        if not self.proposal_closed:
            raise UserError(_("This customer is not closed on the board."))
        with privileged(PROPOSAL_CLOSE_SCOPE):
            self.write(
                {
                    "proposal_closed": False,
                    "proposal_closed_uid": False,
                    "proposal_closed_date": False,
                }
            )
        self.env["collection.receipt.proposal.event"]._proposal_log(
            self.sheet_id,
            "reopen",
            _("Customer reopened on the board"),
            allocation_id=self,
            description=self.partner_id.display_name,
            value_from="closed",
            value_to="open",
        )
        return True

    # ------------------------------------------------------------------
    # Board payload
    # ------------------------------------------------------------------

    @api.private
    def _proposal_column_payload(self, split_parts):
        """One board column: figures, cards and documents for this customer."""
        self.ensure_one()
        cards = []
        lines_by_kind = {
            kind: self._proposal_kind_lines(kind) for kind in DOCUMENT_KINDS
        }
        for kind in DOCUMENT_KINDS:
            receipt = self._proposal_receipt(kind)
            for value in receipt.value_ids:
                cards.append(value._proposal_card_payload(split_parts))
        return {
            "allocation_id": self.id,
            "partner_id": self.partner_id.id,
            "partner_name": self.partner_id.display_name or "",
            "partner_vat": self.partner_id.vat or "",
            "closed": self.proposal_closed,
            "note": self.proposal_note or "",
            "closed_by": self.proposal_closed_uid.display_name or "",
            "closed_date": self.proposal_closed_date
            and str(self.proposal_closed_date)
            or "",
            "status": self.proposal_status,
            "circuits": {
                kind: self._proposal_kind_figures(kind, lines=lines_by_kind[kind])
                for kind in DOCUMENT_KINDS
            },
            "cards": cards,
            "documents": {
                kind: [
                    {
                        "line_id": line.id,
                        "number": line.invoice_number or line.external_invoice_id or "",
                        "issue_date": line.issue_date and str(line.issue_date) or "",
                        "due_date": line.due_date and str(line.due_date) or "",
                        "amount": line.invoice_amount or 0.0,
                        "balance": line.invoice_balance or 0.0,
                        "applied": line.amount_applied or 0.0,
                    }
                    for line in lines_by_kind[kind]
                ]
                for kind in DOCUMENT_KINDS
            },
        }

    @api.constrains("partner_id", "voucher_ids")
    def _check_voucher_partners(self):
        """Allow vouchers whose largest-share owner is this allocation."""
        for allocation in self:
            for voucher in allocation.voucher_ids:
                if not voucher._proposal_allocation_owner_ok(allocation):
                    raise ValidationError(
                        _("Allocation vouchers must share the allocation customer.")
                    )
