# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tools import SQL


def migrate(cr, version):
    """Drop the board event history table; Odoo keeps removed models' tables."""
    cr.execute(
        SQL(
            "DROP TABLE IF EXISTS %s CASCADE",
            SQL.identifier("collection_receipt_proposal_event"),
        )
    )
