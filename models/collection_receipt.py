# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

_APPLIED_DEPENDS = (
    "document_kind",
    "allocation_id.line_ids.document_kind",
    "allocation_id.line_ids.amount_applied",
)
_VALUES_DEPENDS = ("value_ids.amount",)


class CollectionReceipt(models.Model):
    _inherit = "collection.receipt"

    # The base declares `_compute_totals` with a dependency on
    # `line_ids.amount_applied`,
    # but `line_ids` is a computed, non-stored Many2many with no inverse: Odoo then
    # falls back to `search([("line_ids", "in", ids)])` and raises "Cannot convert
    # collection.receipt.line_ids to SQL" the moment an existing `amount_applied` is
    # written. Overriding the method cannot help — `Field.get_depends` walks the whole
    # MRO and *extends* the dependency list — so the fields carry an explicit `depends`,
    # which short-circuits that walk. Same values, reachable triggers.
    total_values = fields.Monetary(
        compute="_compute_totals",
        currency_field="currency_id",
        depends=_VALUES_DEPENDS,
    )
    total_applied = fields.Monetary(
        compute="_compute_totals",
        currency_field="currency_id",
        depends=_APPLIED_DEPENDS,
    )
    amount_on_account = fields.Monetary(
        compute="_compute_totals",
        currency_field="currency_id",
        depends=_VALUES_DEPENDS + _APPLIED_DEPENDS,
    )
