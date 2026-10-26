# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from odoo.addons.collection.models.collection_sheet_report import (
    _CHECK_TYPE_LABELS,
    _SHEET_STATE_LABELS,
    _VOUCHER_BLOCK_LABELS,
    _VOUCHER_BLOCK_ORDER,
)

from .collection_allocation import DOCUMENT_KINDS

ASSIGNMENT_STATES = frozenset({"proposal", "closed"})
KIND_TITLES = {"invoice": "Facturas", "quotation": "Presupuestos"}
STATUS_TITLES = {
    "sin_iniciar": "Sin iniciar",
    "parcial": "Parcial",
    "conciliado": "Conciliado",
    "a_favor": "A favor",
    "deuda": "Deuda pendiente",
    "cruce": "Cruce",
    "cerrado": "Cerrado",
}
INVOICE_STATE_TITLES = {"open": "Vigente", "overdue": "Vencido"}
RECEIPT_STATE_TITLES = {
    "draft": "Borrador",
    "closed": "Cerrado",
    "issued": "Emitido",
}
VOUCHER_STATE_TITLES = {
    "draft": "Borrador",
    "validated_seller": "Validado por vendedor",
    "validated_collections": "Validado por cobranzas",
}
# The workbook writes these columns in this order; `report/` imports them
# rather than restating them, so producer and consumer cannot drift.
SUMMARY_KEYS = ("collected", "applied", "on_account", "debt_total", "pending")
DOCUMENT_KEYS = ("invoice_balance", "amount_applied", "commission")
_CUSTOMER_KEYS = ("total_collected", "total_applied", "total_on_account")
_XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _label(mapping, value):
    """Spanish label for a stored value; never raise on an unknown one."""
    return mapping.get(value) or value or ""


def _status_title(status):
    """Spanish label for a board status; never raise on an unknown value."""
    return _label(STATUS_TITLES, status)


def _voucher_blocks(grouped, labels):
    """Group voucher rows by document type, in the Planilla's block order.

    ``grouped`` maps a `document_type` to rows already in their final order, so
    grouping never re-sorts them. Block order mirrors
    `_collection_report_voucher_blocks`: the catalog order first, then whatever
    else the sheet carries, alphabetically. Every subtotal sums the applied
    share, never `voucher.amount` — a voucher split across two receipts would
    otherwise be counted twice.
    """
    remaining = sorted(code for code in grouped if code not in _VOUCHER_BLOCK_ORDER)
    blocks = []
    for code in (*_VOUCHER_BLOCK_ORDER, *remaining):
        rows = grouped.get(code)
        if not rows:
            continue
        blocks.append(
            {
                "code": code,
                "label": labels["types"].get(code) or code or "",
                "rows": rows,
                "subtotal_applied": sum(row["applied_amount"] for row in rows),
                "subtotal_voucher_amount": sum(row["voucher_amount"] for row in rows),
                "split_count": sum(1 for row in rows if row["is_partial"]),
            }
        )
    return blocks


class CollectionAllocation(models.Model):
    _inherit = "collection.allocation"

    @api.private
    def _receipt_assignment_entry(
        self, document_kind, code, currency, *, receipt, labels, percent
    ):
        """Summary row plus circuit block for one `(customer, circuit)` pair.

        Returns ``None`` for a circuit with neither collected money nor
        documents, so a customer who only works one circuit does not carry an
        empty row for the other. The circuit block is ``None`` when the circuit
        has no receipt to simulate yet.
        """
        self.ensure_one()
        figures = self._proposal_kind_figures(document_kind)
        lines = self._proposal_kind_lines(document_kind)
        if not lines and not currency.compare_amounts(figures["collected"], 0.0):
            return None
        name = self.partner_id.display_name or ""
        kind_label = KIND_TITLES[document_kind]
        summary = {
            "code": code,
            "name": name,
            "kind": document_kind,
            "kind_label": kind_label,
            "collected": figures["collected"],
            "applied": figures["applied"],
            "on_account": figures["available"],
            "debt_total": figures["total"],
            "pending": figures["pending"],
            "kind_status_label": _status_title(
                self._proposal_kind_status(document_kind, figures=figures)
            ),
            "closed": self.proposal_closed,
            "note": self.proposal_note or "",
        }
        return {
            "summary": summary,
            "circuit": self._receipt_assignment_circuit(
                document_kind,
                kind_label,
                lines,
                receipt,
                currency,
                labels,
                percent,
                name,
            ),
        }

    @api.private
    def _receipt_assignment_circuit(
        self,
        document_kind,
        kind_label,
        lines,
        receipt,
        currency,
        labels,
        percent,
        name,
    ):
        """One simulated receipt: its documents and its vouchers by type.

        The sub-dicts carry disjoint keys, so they flatten into one block. A
        circuit with no receipt, or a receipt with neither values nor imputed
        documents, has nothing to simulate and yields ``None``.
        """
        self.ensure_one()
        documents = self._receipt_assignment_documents(lines, currency, percent)
        blocks = self._receipt_assignment_value_blocks(receipt, currency, labels, name)
        if not receipt or not (blocks or documents["document_rows"]):
            return None
        block = {
            "kind": document_kind,
            "kind_label": kind_label,
            "receipt_reference": receipt.external_receipt_id or str(receipt.id),
            "receipt_state": receipt.state or "",
            "receipt_state_label": _label(RECEIPT_STATE_TITLES, receipt.state),
            "total_values": receipt.total_values or 0.0,
            "total_applied": receipt.total_applied or 0.0,
            "amount_on_account": receipt.amount_on_account or 0.0,
            "voucher_blocks": blocks,
            "subtotal_values_applied": sum(item["subtotal_applied"] for item in blocks),
            "split_count": sum(item["split_count"] for item in blocks),
        }
        block.update(documents)
        return block

    @api.private
    def _receipt_assignment_documents(self, lines, currency, percent):
        """Imputed documents of one circuit, in the FIFO order the money took.

        ``lines`` arrives from `_proposal_kind_lines`, whose ordering mirrors
        `collection.receipt._compute_line_ids`; it is never re-sorted here. An
        empty circuit still carries every key with a ``0.0`` subtotal, so the
        workbook's balance line can reference the subtotal row unconditionally.
        Commission is the Planilla's own per-row figure
        (`_collection_line_commission`: the untaxed share of what was applied
        times ``percent``), rounded per row before summing.
        """
        self.ensure_one()
        rows = []
        for line in lines:
            applied = line.amount_applied or 0.0
            if applied <= 0.0:
                continue
            rows.append(
                {
                    "number": line.invoice_number or line.external_invoice_id or "",
                    "external_id": line.external_invoice_id or "",
                    "issue_date": line.issue_date or False,
                    "due_date": line.due_date or False,
                    "invoice_amount": line.invoice_amount or 0.0,
                    "invoice_balance": line.invoice_balance or 0.0,
                    "amount_applied": applied,
                    "commission": self.env[
                        "collection.sheet"
                    ]._collection_line_commission(line, percent, currency),
                    "invoice_state_label": _label(
                        INVOICE_STATE_TITLES, line.invoice_state
                    ),
                }
            )
        block = {"document_rows": rows}
        for key in DOCUMENT_KEYS:
            block[f"subtotal_{key}"] = sum(row[key] for row in rows)
        return block

    @api.private
    def _receipt_assignment_value_blocks(self, receipt, currency, labels, partner_name):
        """The receipt's vouchers, grouped by document type like the Planilla.

        Rows keep `collection.receipt.value._order`, so the grouping preserves
        the order the money was assigned in.
        """
        self.ensure_one()
        grouped = {}
        for value in receipt.value_ids:
            voucher = value.voucher_id
            grouped.setdefault(voucher.document_type or "", []).append(
                voucher._receipt_assignment_value_row(
                    currency, labels, value.amount or 0.0, partner_name=partner_name
                )
            )
        return _voucher_blocks(grouped, labels)


class CollectionSheet(models.Model):
    _inherit = "collection.sheet"

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------

    @api.private
    def _receipt_assignment_report_data(self):
        """Build the Asignaciones payload (primitives only, no records).

        `Resumen` keeps one summary row per `(allocation, document_kind)` that
        holds money or documents. `Clientes` nests one block per customer, and
        inside it one block per circuit that has a receipt to simulate: the
        documents it imputed, the vouchers that funded it grouped by type, and
        the circuit's balance. Every figure
        comes from the board's own helpers so the workbook can never disagree
        with the screen.
        """
        self.ensure_one()
        self._ensure_saved_sheet()
        self._receipt_assignment_ensure_exportable()
        currency = self._collection_report_currency()
        codes = self._collection_report_customer_codes(
            self.allocation_ids.partner_id | self.voucher_ids.partner_id
        )
        labels = self._receipt_assignment_labels()
        receipt_map = self._receipt_assignment_receipt_map()
        percent = self.commission_percent or 0.0
        empty_receipt = self.env["collection.receipt"]
        entries = []
        for allocation in self.allocation_ids:
            code = codes.get(allocation.partner_id.id, "") or ""
            name = allocation.partner_id.display_name or ""
            sort = self._collection_report_code_sort(code, name)
            summaries = []
            circuits = []
            for index, kind in enumerate(DOCUMENT_KINDS):
                receipt = receipt_map.get((allocation.id, kind)) or empty_receipt
                entry = allocation._receipt_assignment_entry(
                    kind,
                    code,
                    currency,
                    receipt=receipt,
                    labels=labels,
                    percent=percent,
                )
                if not entry:
                    continue
                summaries.append((index, entry["summary"]))
                if entry["circuit"]:
                    circuits.append((index, entry["circuit"]))
            if not summaries:
                continue
            entries.append((sort, allocation, code, name, summaries, circuits))
        entries.sort(key=lambda item: item[0])
        summary_rows = [
            summary
            for _sort, _alloc, _code, _name, summaries, _circuits in entries
            for _index, summary in sorted(summaries, key=lambda item: item[0])
        ]
        customer_blocks = [
            self._receipt_assignment_customer_block(
                allocation, code, name, circuits, currency
            )
            for _sort, allocation, code, name, _summaries, circuits in entries
            if circuits
        ]
        customer_totals = self._receipt_assignment_totals(
            customer_blocks, _CUSTOMER_KEYS
        )
        unassigned = self._receipt_assignment_unassigned(currency, codes, labels)
        return {
            "company": self.company_id.name or "",
            "printed_on": fields.Date.context_today(self),
            "reference": self.name or "",
            "state_label": _label(_SHEET_STATE_LABELS, self.state),
            "seller_name": self.seller_id.name or "",
            "currency_name": currency.name or "",
            "date_from": self.date_from or False,
            "date_to": self.date_to or False,
            "customer_count": len(entries),
            "commission_percent": percent,
            "summary_rows": summary_rows,
            "summary_totals": self._receipt_assignment_totals(
                summary_rows, SUMMARY_KEYS
            ),
            "kind_totals": {
                kind: self._receipt_assignment_totals(
                    [row for row in summary_rows if row["kind"] == kind],
                    SUMMARY_KEYS,
                )
                for kind in DOCUMENT_KINDS
            },
            "customer_blocks": customer_blocks,
            "customer_totals": customer_totals,
            "unassigned": unassigned,
            "recon": self._receipt_assignment_recon(
                currency, customer_totals, unassigned
            ),
        }

    @api.private
    def _receipt_assignment_customer_block(
        self, allocation, code, name, circuits, currency
    ):
        """One customer: their circuits in `invoice` then `quotation` order.

        The customer totals are the sum of their circuits' own receipt figures,
        so a customer line can never disagree with the balance lines above it.
        """
        self.ensure_one()
        ordered = [
            circuit for _index, circuit in sorted(circuits, key=lambda item: item[0])
        ]
        return {
            "code": code,
            "name": name,
            "closed": allocation.proposal_closed,
            "note": allocation.proposal_note or "",
            "circuits": ordered,
            "total_collected": sum(item["total_values"] for item in ordered),
            "total_applied": sum(item["total_applied"] for item in ordered),
            "total_on_account": sum(item["amount_on_account"] for item in ordered),
            "total_commission": sum(item["subtotal_commission"] for item in ordered),
        }

    # ------------------------------------------------------------------
    # Batched lookups
    # ------------------------------------------------------------------

    @api.private
    def _receipt_assignment_labels(self):
        """Every Spanish label the Recibos sheet needs, resolved in one pass.

        One `collection.document.type` search for the whole sheet and the
        selection dictionaries built once, instead of once per voucher row.
        Voucher type precedence mirrors `_collection_report_voucher_blocks`.
        """
        self.ensure_one()
        Voucher = self.env["collection.voucher"]
        catalog = {
            row.code: row.name
            for row in self.env["collection.document.type"].search([])
        }
        selection = dict(
            Voucher._fields["document_type"]._description_selection(self.env) or []
        )
        codes = (
            set(catalog)
            | set(selection)
            | {voucher.document_type for voucher in self.voucher_ids}
        )
        return {
            "types": {
                code: (
                    _VOUCHER_BLOCK_LABELS.get(code)
                    or catalog.get(code)
                    or selection.get(code)
                    or code
                )
                for code in codes
                if code
            },
            "states": dict(VOUCHER_STATE_TITLES),
            "checks": dict(_CHECK_TYPE_LABELS),
            "retentions": dict(
                Voucher._fields["retention_kind"]._description_selection(self.env) or []
            ),
        }

    @api.private
    def _receipt_assignment_receipt_map(self):
        """`{(allocation_id, document_kind): receipt}` from one prefetched recordset.

        Walking `allocation_ids.receipt_ids` once, rather than calling
        `_proposal_receipt` per pair, keeps the prefetch over the whole sheet:
        every later `value_ids` / `voucher_id` read then batches instead of
        firing once per allocation.
        """
        self.ensure_one()
        return {
            (receipt.allocation_id.id, receipt.document_kind): receipt
            for receipt in self.allocation_ids.receipt_ids
        }

    # ------------------------------------------------------------------
    # Unassigned money and reconciliation
    # ------------------------------------------------------------------

    @api.private
    def _receipt_assignment_unassigned(self, currency, codes, labels):
        """Sheet vouchers still holding money no receipt claimed.

        Grouped by document type like the receipt blocks, so the section reads
        in the same column shapes. Rows are sorted before grouping, so each
        block keeps the report's one sort order: coded customers first, then
        code, then name, then voucher reference.

        Unlike the board's pool this keeps `seller_deposit`: the section exists
        to close the reconciliation against the sheet total, so a remittance
        with free money has to appear. Its block names it.
        """
        self.ensure_one()
        entries = []
        for voucher in self.voucher_ids:
            free = voucher.proposal_free_amount or 0.0
            if currency.compare_amounts(free, 0.0) <= 0:
                continue
            partner = voucher.partner_id
            code = codes.get(partner.id, "") or ""
            name = partner.display_name or ""
            entries.append(
                (
                    self._collection_report_code_sort(code, name)
                    + (voucher.name or "",),
                    voucher.document_type or "",
                    voucher._receipt_assignment_value_row(
                        currency, labels, free, partner_name=name
                    ),
                )
            )
        entries.sort(key=lambda item: item[0])
        grouped = {}
        for _sort, code, row in entries:
            grouped.setdefault(code, []).append(row)
        blocks = _voucher_blocks(grouped, labels)
        return {
            "blocks": blocks,
            "subtotal_voucher_amount": sum(
                block["subtotal_voucher_amount"] for block in blocks
            ),
            "subtotal_free_amount": sum(block["subtotal_applied"] for block in blocks),
        }

    @api.private
    def _receipt_assignment_recon(self, currency, customer_totals, unassigned):
        """Assigned + free + replaced against the sheet's own voucher total.

        Per voucher `amount == assigned + free + replaced`, so the three
        components summed over the sheet must equal `sum(voucher.amount)`.
        `replaced_amount` only ever lands on the cash side of a replacement, so
        a plain sum never double-counts the remittance. A non-zero `difference`
        means some voucher is assigned beyond its own amount.
        """
        self.ensure_one()
        assigned = customer_totals.get("total_collected") or 0.0
        free = unassigned.get("subtotal_free_amount") or 0.0
        replaced = sum(voucher.replaced_amount or 0.0 for voucher in self.voucher_ids)
        sheet_total = sum(voucher.amount or 0.0 for voucher in self.voucher_ids)
        computed = assigned + free + replaced
        difference = currency.round(computed - sheet_total)
        return {
            "assigned_total": currency.round(assigned),
            "unassigned_total": currency.round(free),
            "replaced_total": currency.round(replaced),
            "computed_total": currency.round(computed),
            "sheet_total": currency.round(sheet_total),
            "difference": difference,
            # Two states only: this report has no benign non-zero difference,
            # so the workbook paints it green or red, never amber.
            "status": (
                "balanced"
                if currency.compare_amounts(difference, 0.0) == 0
                else "outstanding"
            ),
        }

    @api.private
    def _receipt_assignment_ensure_exportable(self):
        """Proposal onwards only, and never across mixed allocation currencies."""
        self.ensure_one()
        if self.state not in ASSIGNMENT_STATES:
            raise UserError(
                _(
                    "The receipt assignment report is only available on collection "
                    "sheets in proposal or closed."
                )
            )
        if len(self.allocation_ids.currency_id) > 1:
            raise UserError(
                _("The receipt assignment report does not support mixed currencies.")
            )

    @api.model
    @api.private
    def _receipt_assignment_totals(self, rows, keys):
        return {key: sum(row.get(key) or 0.0 for row in rows) for key in keys}

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def action_print_receipt_assignment_xlsx(self):
        """Build the Asignaciones workbook and return a download URL."""
        self.ensure_one()
        content = self.env["collection.receipt.assignment.xlsx"]._render_xlsx(
            self._receipt_assignment_report_data()
        )
        filename = f"{(self.name or '').replace('/', '-')}-asignaciones.xlsx"
        Attachment = self.env["ir.attachment"]
        Attachment.search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("name", "=", filename),
            ]
        ).unlink()
        attachment = Attachment.create(
            {
                "name": filename,
                "type": "binary",
                "raw": content,
                "mimetype": _XLSX_MIMETYPE,
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "download",
        }
