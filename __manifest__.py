# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Collection Receipt Proposal",
    "version": "19.0.1.5.0",
    "category": "Sales/CRM",
    "summary": "Drag-and-drop reconciliation board for collection sheets",
    "author": "Seedian",
    "website": "https://seedian.ai",
    "depends": ["collection"],
    "data": [
        "security/collection_receipt_proposal_security.xml",
        "security/ir.model.access.csv",
        "views/collection_receipt_proposal_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "collection_receipt_proposal/static/src/receipt_proposal/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}
