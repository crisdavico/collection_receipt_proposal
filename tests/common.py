# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.exceptions import AccessError
from odoo.fields import Command

from odoo.addons.collection.tests.common_connector import (
    install_bound_test_connector,
)
from odoo.addons.collection.tests.test_collection_payment import (
    create_internal_seller,
    dummy_customer_partner,
    ensure_enabled_seller,
)

__all__ = [
    "ReceiptProposalCommon",
    "create_internal_seller",
    "dummy_customer_partner",
    "ensure_enabled_seller",
    "install_bound_test_connector",
]


class ReceiptProposalCommon:
    """Receipt-shaped fixtures, replicated from `TestCollectionReceipt`.

    Those helpers are methods on `collection`'s own test case, so subclassing
    it would re-run its whole suite; this mixin copies them instead.
    """

    def _seller(self):
        return ensure_enabled_seller(self.env)

    def _partner(self, label="PROP-CUST"):
        return dummy_customer_partner(self.env, customer=label)

    def _autopost_partner_vals(self, name):
        Partner = self.env["res.partner"]
        vals = {"name": name, "email": f"{name}@example.com"}
        if "autopost_bills" in Partner._fields:
            vals["autopost_bills"] = "ask"
        return vals

    def _partner_has_autopost_bills_column(self):
        """The DB column may outlive the `account` module's Python field."""
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = 'res_partner'
               AND column_name = 'autopost_bills'
            """
        )
        return bool(self.env.cr.fetchone())

    def _create_bare_partner(self, name):
        """Create a partner even when `account` columns outlive its fields."""
        Partner = self.env["res.partner"].with_context(
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            mail_create_nosubscribe=True,
        )
        vals = self._autopost_partner_vals(name)
        if "autopost_bills" in vals or not self._partner_has_autopost_bills_column():
            return Partner.create(vals)
        self.env.cr.execute(
            """
            INSERT INTO res_partner (
                name, email, active, complete_name, type, autopost_bills,
                create_uid, write_uid, create_date, write_date
            )
            VALUES (
                %s, %s, true, %s, 'contact', 'ask',
                1, 1,
                (now() AT TIME ZONE 'UTC'),
                (now() AT TIME ZONE 'UTC')
            )
            RETURNING id
            """,
            (name, vals["email"], name),
        )
        return Partner.browse(self.env.cr.fetchone()[0])

    def _create_user(self, login, group_xmlid):
        partner = self._create_bare_partner(login)
        return (
            self.env["res.users"]
            .with_context(no_reset_password=True, tracking_disable=True)
            .create(
                {
                    "name": login,
                    "login": login,
                    "email": partner.email,
                    "partner_id": partner.id,
                    "group_ids": [(6, 0, [self.env.ref(group_xmlid).id])],
                }
            )
        )

    def _install_test_connector(self):
        return install_bound_test_connector(self, self._seller())

    def _create_sheet(self, *, force_new=False, **extra):
        seller = extra.pop("seller_id", None)
        seller = self.env["res.users"].browse(seller) if seller else self._seller()
        company = self.env["res.company"].browse(
            extra.get("company_id") or self.env.company.id
        )
        ensure_enabled_seller(self.env, seller, company=company)
        if not force_new and "company_id" not in extra:
            existing = self.env["collection.sheet"].search(
                [
                    ("seller_id", "=", seller.id),
                    ("company_id", "=", company.id),
                    ("state", "=", "open"),
                ],
                limit=1,
            )
            if existing:
                return existing
        vals = {"seller_id": seller.id, **extra}
        return self.env["collection.sheet"].create(vals)

    def _create_voucher(self, partner, sheet, amount=100.0, **extra):
        ensure_enabled_seller(self.env, sheet.seller_id, company=sheet.company_id)
        vals = {
            "partner_id": partner.id,
            "document_type": "bank_transfer",
            "seller_id": sheet.seller_id.id,
            "sheet_id": sheet.id,
            "company_id": sheet.company_id.id,
            "amount": amount,
        }
        vals.update(extra)
        return self.env["collection.voucher"].create(vals)

    def _line_vals(self, amount_applied=0.0, invoice_balance=100.0, **extra):
        vals = {
            "external_invoice_id": extra.pop("external_invoice_id", "INV-1"),
            "invoice_number": extra.pop("invoice_number", "A-1"),
            "issue_date": extra.pop("issue_date", date(2026, 1, 1)),
            "due_date": extra.pop("due_date", date(2026, 1, 31)),
            "invoice_amount": extra.pop("invoice_amount", invoice_balance),
            "invoice_balance": invoice_balance,
            "invoice_state": extra.pop("invoice_state", "open"),
            "amount_applied": amount_applied,
            "document_kind": extra.pop("document_kind", "invoice"),
        }
        vals.update(extra)
        return vals

    def _create_allocation(self, sheet, partner, vouchers=None, lines=None, **extra):
        vals = {"sheet_id": sheet.id, "partner_id": partner.id}
        if vouchers:
            vals["voucher_ids"] = [Command.set(vouchers.ids)]
        if lines is not None:
            vals["line_ids"] = [Command.create(line) for line in lines]
        vals.update(extra)
        return self.env["collection.allocation"].create(vals)

    def _create_receipt(self, allocation, document_kind="invoice", **extra):
        vals = {"allocation_id": allocation.id, "document_kind": document_kind}
        vals.update(extra)
        return self.env["collection.receipt"].create(vals)

    def _create_value(self, receipt, voucher, amount):
        return self.env["collection.receipt.value"].create(
            {
                "receipt_id": receipt.id,
                "voucher_id": voucher.id,
                "amount": amount,
            }
        )

    def _mark_validated(self, vouchers):
        vouchers.with_context(collection_audited_state=True).write(
            {"state": "validated_collections"}
        )
        return vouchers

    def _confirm(self, sheet):
        """Move a sheet to `proposal`, the only state the board runs in."""
        self._mark_validated(sheet.voucher_ids)
        sheet.action_seller_close()
        collected = sheet._cash_collected_total()
        currency = sheet.company_id.currency_id
        if currency.compare_amounts(collected, 0.0) > 0:
            sheet.action_declare_cash(commission_withheld=0.0)
        sheet.action_confirm()
        return sheet

    def _enable_seller_deposit_type(self, company=None):
        catalog = self.env.ref("collection.document_type_seller_deposit")
        (company or self.env.company).write(
            {"allowed_document_type_ids": [Command.link(catalog.id)]}
        )
        return catalog

    def _create_seller_deposit(self, sheet, amount=100.0, **extra):
        self._enable_seller_deposit_type(sheet.company_id)
        vals = {
            "document_type": "seller_deposit",
            "seller_id": sheet.seller_id.id,
            "sheet_id": sheet.id,
            "company_id": sheet.company_id.id,
            "amount": amount,
            "voucher_number": extra.pop("voucher_number", "SD-PROP"),
            "voucher_date": extra.pop("voucher_date", date(2026, 9, 8)),
        }
        vals.update(extra)
        return self.env["collection.voucher"].create(vals)

    def _cash_replace(self, receipt, cash, deposit, amount):
        return self.env["collection.receipt.value"]._cash_replace(
            receipt, cash, deposit, amount
        )

    def _create_company(self, name):
        """Persist a second company; satisfy partner.autopost_bills when present."""
        Partner = self.env["res.partner"].with_context(
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            mail_create_nosubscribe=True,
        )
        partner_vals = {"name": name, "is_company": True}
        if "autopost_bills" in Partner._fields:
            partner_vals["autopost_bills"] = "ask"
            partner = Partner.create(partner_vals)
        elif self._partner_has_autopost_bills_column():
            self.env.cr.execute(
                """
                INSERT INTO res_partner (
                    name, email, active, complete_name, type, is_company,
                    autopost_bills, create_uid, write_uid, create_date, write_date
                )
                VALUES (
                    %s, %s, true, %s, 'contact', true, 'ask',
                    1, 1,
                    (now() AT TIME ZONE 'UTC'),
                    (now() AT TIME ZONE 'UTC')
                )
                RETURNING id
                """,
                (name, f"{name}@example.com", name),
            )
            partner = Partner.browse(self.env.cr.fetchone()[0])
        else:
            partner = Partner.create(partner_vals)
        # Copy leftover account NOT NULL columns the ORM field set does not
        # know about in this addon's registry (same pattern as collection
        # report/binding tests).
        self.env.cr.execute(
            """
            INSERT INTO res_company (
                name, partner_id, currency_id, active,
                fiscalyear_last_day, fiscalyear_last_month,
                account_price_include, cost_method, horizon_days,
                inventory_period, layout_background, security_lead
            )
            SELECT
                %s, %s, currency_id, true,
                fiscalyear_last_day, fiscalyear_last_month,
                account_price_include, cost_method, horizon_days,
                inventory_period, layout_background, security_lead
            FROM res_company
            WHERE id = %s
            RETURNING id
            """,
            (name, partner.id, self.env.company.id),
        )
        company = self.env["res.company"].browse(self.env.cr.fetchone()[0])
        company.invalidate_recordset()
        company._collection_copy_sequences()
        company._collection_enable_all_document_types()
        return company

    def _restrict_user_to_company(self, user, company):
        user.write({"company_ids": [Command.link(company.id)]})
        user.write({"company_id": company.id})
        user.write({"company_ids": [Command.set([company.id])]})

    def _assert_global_company_rule(self, model_name):
        rules = self.env["ir.rule"].search([("model_id.model", "=", model_name)])
        self.assertEqual(
            len(rules), 1, f"{model_name} must have exactly one record rule"
        )
        self.assertFalse(rules.groups, f"{model_name} company rule must be global")
        compact = "".join(rules.domain_force.split())
        self.assertEqual(
            compact,
            "[('company_id','in',company_ids)]",
            f"{model_name} rule must hide companies outside company_ids",
        )

    def _assert_hidden_from_user(self, user, record, read_fields):
        Model = self.env[record._name].with_user(user)
        self.assertFalse(
            Model.search([("id", "=", record.id)]),
            f"{record._name} {record.id} must not be searchable from the other company",
        )
        with self.assertRaises(AccessError):
            Model.browse(record.id).read(read_fields)
        self.assertEqual(
            Model.search_read([("id", "=", record.id)], read_fields),
            [],
        )

    def _assert_acl(self, model_name, perms):
        acls = self.env["ir.model.access"].search([("model_id.model", "=", model_name)])
        self.assertEqual(len(acls), 1, f"{model_name} must have one ACL row")
        self.assertEqual(acls.group_id, self.env.ref("base.group_user"))
        self.assertEqual(bool(acls.perm_read), perms[0])
        self.assertEqual(bool(acls.perm_write), perms[1])
        self.assertEqual(bool(acls.perm_create), perms[2])
        self.assertEqual(bool(acls.perm_unlink), perms[3])

    # ------------------------------------------------------------------
    # Board scenarios
    # ------------------------------------------------------------------

    def _board_scenario(self, **kwargs):
        """Two customers, one voucher each, invoice + quotation documents."""
        sheet = self._create_sheet()
        first = self._partner("PROP-A")
        second = self._partner("PROP-B")
        voucher_a = self._create_voucher(
            first,
            sheet,
            amount=kwargs.get("amount_a", 300.0),
            **kwargs.get("extra_a", {}),
        )
        voucher_b = self._create_voucher(
            second,
            sheet,
            amount=kwargs.get("amount_b", 100.0),
            **kwargs.get("extra_b", {}),
        )
        allocation_a = self._create_allocation(
            sheet,
            first,
            vouchers=voucher_a,
            lines=[
                self._line_vals(
                    external_invoice_id="A-OLD",
                    invoice_number="FA-0001",
                    due_date=date(2026, 1, 10),
                    invoice_balance=100.0,
                ),
                self._line_vals(
                    external_invoice_id="A-NEW",
                    invoice_number="FA-0002",
                    due_date=date(2026, 2, 10),
                    invoice_balance=100.0,
                ),
                self._line_vals(
                    external_invoice_id="A-QUO",
                    invoice_number="PRE-0001",
                    due_date=date(2026, 1, 20),
                    invoice_balance=50.0,
                    document_kind="quotation",
                ),
            ],
        )
        allocation_b = self._create_allocation(
            sheet,
            second,
            vouchers=voucher_b,
            lines=[
                self._line_vals(
                    external_invoice_id="B-ONE",
                    invoice_number="FB-0001",
                    due_date=date(2026, 1, 5),
                    invoice_balance=80.0,
                )
            ],
        )
        self._confirm(sheet)
        return {
            "sheet": sheet,
            "partner_a": first,
            "partner_b": second,
            "voucher_a": voucher_a,
            "voucher_b": voucher_b,
            "allocation_a": allocation_a,
            "allocation_b": allocation_b,
        }
