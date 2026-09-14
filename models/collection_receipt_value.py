# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class CollectionReceiptValue(models.Model):
    _inherit = "collection.receipt.value"

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
            "document_type": voucher.document_type or "",
            "reference": label["reference"],
            "date": voucher.voucher_date and str(voucher.voucher_date) or "",
            "amount": self.amount or 0.0,
            "voucher_amount": voucher.amount or 0.0,
            "document_kind": self.receipt_id.document_kind,
            "split_parts": split_parts.get(voucher.id, 1),
            "free_amount": voucher.proposal_free_amount,
        }
