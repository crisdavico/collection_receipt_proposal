# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

from ..models.collection_sheet import CLOSE_CONFIRM_KEY


class CollectionSheetCloseConfirm(models.TransientModel):
    """Last look at an unfinished board before a manager closes the sheet.

    Opened by the sheet form's Close button when the receipt proposal board
    still holds money in the unassigned pool or customers not closed on it.
    It warns and lets the manager go on; it guards nothing -- Close itself
    re-checks the Collections Manager role and its own gates.
    """

    _name = "collection.sheet.close.confirm"
    _description = "Collection Sheet Close Confirmation"

    sheet_id = fields.Many2one(
        comodel_name="collection.sheet",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_pending",
    )
    pool_amount = fields.Monetary(
        string="Unassigned Money",
        currency_field="currency_id",
        compute="_compute_pending",
    )
    pool_count = fields.Integer(
        string="Unassigned Vouchers",
        compute="_compute_pending",
    )
    open_customer_count = fields.Integer(
        string="Customers Still Open",
        compute="_compute_pending",
    )
    open_customer_names = fields.Text(
        string="Open Customers",
        compute="_compute_pending",
    )

    @api.depends("sheet_id")
    def _compute_pending(self):
        for wizard in self:
            pending = wizard.sheet_id._proposal_close_pending()
            customers = pending["open_allocations"].partner_id.mapped("display_name")
            wizard.currency_id = pending["currency"]
            wizard.pool_amount = pending["pool_amount"]
            wizard.pool_count = len(pending["pool_vouchers"])
            wizard.open_customer_count = len(pending["open_allocations"])
            wizard.open_customer_names = "\n".join(sorted(customers))

    def action_confirm_close(self):
        self.ensure_one()
        self.sheet_id.with_context(**{CLOSE_CONFIRM_KEY: False}).action_close()
        return {"type": "ir.actions.act_window_close"}
