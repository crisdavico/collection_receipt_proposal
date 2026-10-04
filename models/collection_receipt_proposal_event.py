# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

EVENT_CONTEXT_KEY = "collection_receipt_proposal_event"

EVENT_TYPE_SELECTION = [
    ("assign", "Assign"),
    ("transfer", "Transfer"),
    ("split", "Split"),
    ("unify", "Unify"),
    ("circuit", "Circuit"),
    ("impute", "Impute"),
    ("auto_impute", "Automatic Imputation"),
    ("reset", "Reset"),
    ("close", "Close"),
    ("reopen", "Reopen"),
]


class CollectionReceiptProposalEvent(models.Model):
    _name = "collection.receipt.proposal.event"
    _description = "Collection Receipt Proposal Event"
    _order = "event_date desc, id desc"

    sheet_id = fields.Many2one(
        comodel_name="collection.sheet",
        required=True,
        ondelete="cascade",
        index=True,
    )
    allocation_id = fields.Many2one(
        comodel_name="collection.allocation",
        ondelete="cascade",
        index=True,
    )
    voucher_id = fields.Many2one(
        comodel_name="collection.voucher",
        ondelete="cascade",
        index=True,
    )
    event_type = fields.Selection(
        selection=EVENT_TYPE_SELECTION,
        required=True,
    )
    name = fields.Char(required=True)
    description = fields.Char()
    value_from = fields.Char()
    value_to = fields.Char()
    user_id = fields.Many2one(
        comodel_name="res.users",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
    )
    event_date = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
    )
    company_id = fields.Many2one(
        related="sheet_id.company_id",
        store=True,
        required=True,
        precompute=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(EVENT_CONTEXT_KEY):
            raise UserError(
                _("Proposal events can only be created by the receipt proposal board.")
            )
        return super().create(vals_list)

    def write(self, vals):
        # An empty recordset write is a legal ORM no-op and the framework does
        # make them; only a write that would actually touch a row refuses.
        if self:
            raise UserError(_("Proposal events cannot be modified."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_forbidden(self):
        if self.env.context.get("collection_sheet_unlinking"):
            return
        raise UserError(_("Proposal events cannot be deleted."))

    @api.model
    @api.private
    def _proposal_log(self, sheet, event_type, name, **extra):
        """Append one immutable proposal event; the only sanctioned writer."""
        vals = {
            "sheet_id": sheet.id,
            "event_type": event_type,
            "name": name,
        }
        for key in ("allocation_id", "voucher_id"):
            record = extra.pop(key, None)
            if record:
                vals[key] = record.id
        for key in ("description", "value_from", "value_to"):
            value = extra.pop(key, None)
            if value not in (None, False, ""):
                vals[key] = str(value)
        return self.with_context(**{EVENT_CONTEXT_KEY: True}).create(vals)
