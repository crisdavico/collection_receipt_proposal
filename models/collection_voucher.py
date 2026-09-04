# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


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

    @api.depends("amount", "proposal_value_ids.amount")
    def _compute_proposal_amounts(self):
        for voucher in self:
            values = voucher.proposal_value_ids
            assigned = sum(value.amount or 0.0 for value in values)
            voucher.proposal_assigned_amount = assigned
            voucher.proposal_free_amount = (voucher.amount or 0.0) - assigned
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
            "reference": label["reference"],
            "date": self.voucher_date and str(self.voucher_date) or "",
            "amount": self.amount or 0.0,
            "free_amount": self.proposal_free_amount,
            "partner_id": self.partner_id.id,
            "partner_name": self.partner_id.display_name or "",
        }
