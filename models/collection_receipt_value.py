# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class CollectionReceiptValue(models.Model):
    _inherit = "collection.receipt.value"

    @api.constrains("voucher_id", "receipt_id")
    def _check_same_allocation(self):
        """Relax the base allocation boundary to the sheet boundary.

        The board splits one voucher across several customers of the same
        collection sheet, so `voucher.allocation_id` becomes a primary-owner
        hint instead of a hard boundary. Crossing sheets stays forbidden.
        """
        for value in self:
            if not value.voucher_id or not value.receipt_id:
                continue
            voucher_sheet = value.voucher_id.sheet_id
            receipt_sheet = value.receipt_id.sheet_id
            if not voucher_sheet or voucher_sheet != receipt_sheet:
                raise ValidationError(
                    _(
                        "Receipt values must use vouchers from the same "
                        "collection sheet."
                    )
                )

    @api.constrains("amount", "voucher_id", "receipt_id")
    def _check_voucher_split_cap(self):
        """Cap every voucher sheet-wide, not per allocation.

        Widening `_check_same_allocation` without widening this search would
        let a voucher be over-split across customers.
        """
        for voucher in self.mapped("voucher_id"):
            if not voucher:
                continue
            values = self.env["collection.receipt.value"].search(
                [("voucher_id", "=", voucher.id)]
            )
            total = sum(value.amount or 0.0 for value in values)
            currency = voucher.currency_id or values[:1].currency_id
            amount = voucher.amount or 0.0
            over = (
                currency.compare_amounts(total, amount) > 0
                if currency
                else total > amount
            )
            if over:
                raise ValidationError(
                    _("Receipt values for a voucher cannot exceed the voucher amount.")
                )

    @api.private
    def _proposal_card_payload(self, split_parts):
        """One board card: this voucher share under its receipt's circuit."""
        self.ensure_one()
        voucher = self.voucher_id
        label = voucher._proposal_card_label()
        return {
            "value_id": self.id,
            "voucher_id": voucher.id,
            "voucher_name": voucher.name or "",
            "method": label["method"],
            "reference": label["reference"],
            "date": voucher.voucher_date and str(voucher.voucher_date) or "",
            "amount": self.amount or 0.0,
            "voucher_amount": voucher.amount or 0.0,
            "document_kind": self.receipt_id.document_kind,
            "split_parts": split_parts.get(voucher.id, 1),
            "free_amount": voucher.proposal_free_amount,
        }
