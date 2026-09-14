# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


def _local_datetime(record, value):
    """Naive datetime in the reader's timezone; xlsxwriter refuses tz-aware."""
    if not value:
        return False
    return fields.Datetime.context_timestamp(record, value).replace(tzinfo=None)


class CollectionVoucher(models.Model):
    _inherit = "collection.voucher"

    proposal_value_ids = fields.One2many(
        comodel_name="collection.receipt.value",
        inverse_name="voucher_id",
        string="Receipt Values",
        readonly=True,
    )
    proposal_assigned_amount = fields.Monetary(
        compute="_compute_proposal_amounts",
        currency_field="currency_id",
    )
    proposal_free_amount = fields.Monetary(
        compute="_compute_proposal_amounts",
        currency_field="currency_id",
    )
    proposal_is_split = fields.Boolean(compute="_compute_proposal_amounts")

    @api.depends("amount", "proposal_value_ids.amount", "replaced_amount")
    def _compute_proposal_amounts(self):
        for voucher in self:
            values = voucher.proposal_value_ids
            assigned = sum(value.amount or 0.0 for value in values)
            voucher.proposal_assigned_amount = assigned
            voucher.proposal_free_amount = (
                (voucher.amount or 0.0) - assigned - (voucher.replaced_amount or 0.0)
            )
            voucher.proposal_is_split = len(values) > 1

    @api.constrains("partner_id", "allocation_id")
    def _check_voucher_allocation_partner(self):
        """Allow a same-sheet largest-share owner that is another customer."""
        for voucher in self:
            allocation = voucher.allocation_id
            if allocation and not voucher._proposal_allocation_owner_ok(allocation):
                raise UserError(
                    _("Voucher customer must match the allocation customer.")
                )

    @api.private
    def _proposal_allocation_owner_ok(self, allocation):
        """True when partners match, or this voucher has a same-sheet share there."""
        self.ensure_one()
        if not allocation:
            return True
        if self.partner_id == allocation.partner_id:
            return True
        if not self.sheet_id or self.sheet_id != allocation.sheet_id:
            return False
        return bool(
            self.env["collection.receipt.value"].search_count(
                [
                    ("voucher_id", "=", self.id),
                    ("receipt_id.allocation_id", "=", allocation.id),
                ]
            )
        )

    @api.private
    def _proposal_card_label(self):
        """Return the board card's payment method and reference strings."""
        self.ensure_one()
        labels = dict(
            self._fields["document_type"]._description_selection(self.env) or []
        )
        method = labels.get(self.document_type) or self.document_type or ""
        if self.document_type == "check":
            reference = " ".join(
                part for part in (self.check_bank, self.check_number) if part
            )
        else:
            reference = self.voucher_number or self.from_account or ""
        return {
            "method": method,
            "reference": reference or self.name or "",
        }

    @api.private
    def _proposal_pool_payload(self):
        """A synthetic 'Sin asignar' card: the voucher's unassigned amount."""
        self.ensure_one()
        label = self._proposal_card_label()
        return {
            "voucher_id": self.id,
            "voucher_name": self.name or "",
            "method": label["method"],
            "document_type": self.document_type or "",
            "reference": label["reference"],
            "date": self.voucher_date and str(self.voucher_date) or "",
            "amount": self.amount or 0.0,
            "free_amount": self.proposal_free_amount,
            "partner_id": self.partner_id.id,
            "partner_name": self.partner_id.display_name or "",
        }

    @api.private
    def _receipt_assignment_value_row(
        self, currency, labels, applied, partner_name=None
    ):
        """The Asignaciones fields for one voucher, with ``applied`` as its money.

        ``applied`` is whatever the workbook's applied column must show for this
        row: the receipt value's share inside a receipt, the still-free amount
        in the unassigned section. Labels arrive already resolved, so no
        selection dictionary is rebuilt per row -- which is why this does not
        reuse `_proposal_card_label`, whose concatenated reference is a board
        card concern anyway.
        """
        self.ensure_one()
        amount = self.amount or 0.0
        is_check = self.document_type == "check"
        return {
            "reference": self.name or "",
            "document_id": self.document_id or "",
            "partner_name": (
                partner_name
                if partner_name is not None
                else (self.partner_id.display_name or "")
            ),
            "type_label": labels["types"].get(self.document_type)
            or self.document_type
            or "",
            "date": self.voucher_date
            or (fields.Date.to_date(self.create_date) if self.create_date else False),
            "number": self.voucher_number or self.check_number or "",
            "voucher_amount": amount,
            "applied_amount": applied,
            "state_label": labels["states"].get(self.state) or self.state or "",
            "check_bank": (self.check_bank or "") if is_check else "",
            "check_type_label": (
                (labels["checks"].get(self.check_type) or "") if is_check else ""
            ),
            "check_issue_date": (self.check_issue_date or False) if is_check else False,
            "check_payment_date": (
                (self.check_payment_date or False) if is_check else False
            ),
            "from_account": self.from_account or "",
            "to_account": self.to_account or "",
            "retention_label": labels["retentions"].get(self.retention_kind) or "",
            "reviewed_by": self.reviewed_by.display_name or "",
            "reviewed_at": _local_datetime(self, self.reviewed_at),
            "is_partial": bool(currency.compare_amounts(applied, amount)),
        }
