/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";

export const BOARD_MODEL = "collection.sheet";
export const PREVIEW_DEBOUNCE_MS = 250;

/* Los dos circuitos de Cobrado. Una tarjeta asignada pertenece a UNO solo y su
   importe únicamente puede imputarse a documentos de ese tipo. */
export const CIRCUITS = {
  invoice: {
    key: "invoice",
    tag: "FAC",
    cls: "c-inv",
    short: "inv",
    noun: "facturas",
    Noun: "Facturas",
    doc: "Factura",
    long: "Cobrado a aplicar a Facturas",
    pending: "Deuda",
  },
  quotation: {
    key: "quotation",
    tag: "PRE",
    cls: "c-quo",
    short: "quo",
    noun: "presupuestos",
    Noun: "Presupuestos",
    doc: "Presupuesto",
    long: "Cobrado a aplicar a Presupuestos",
    pending: "Pend.",
  },
};

export const CIRCUIT_KEYS = ["invoice", "quotation"];

export const STATUS_LABELS = {
  sin_iniciar: "Sin iniciar",
  parcial: "Parcial",
  conciliado: "Conciliado",
  a_favor: "Saldo a favor",
  deuda: "Deuda pendiente",
  cruce: "Cruce de circuitos",
  cerrado: "Cerrado",
};

export const EVENT_LABELS = {
  assign: "Asignación",
  transfer: "Transferencia",
  split: "División",
  unify: "Reunificación",
  circuit: "Cambio de circuito",
  impute: "Imputación manual",
  auto_impute: "Reimputación automática",
  close: "Cierre de cliente",
  reopen: "Reapertura de cliente",
};

export const EVENT_BULLETS = {
  auto_impute: "ok",
  impute: "ok",
  close: "warn",
  reopen: "warn",
  circuit: "inv",
  split: "quo",
};

export function circuitOf(documentKind) {
  return CIRCUITS[documentKind] || null;
}

export function splitAmount(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount : 0;
}

export function formatAmount(value, currency) {
  const decimals =
    currency && Number.isInteger(currency.decimal_places) ? currency.decimal_places : 2;
  const number = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(splitAmount(value));
  const symbol = (currency && currency.symbol) || "$";
  return currency && currency.position === "after"
    ? `${number} ${symbol}`
    : `${symbol} ${number}`;
}

export function formatShort(value, currency) {
  const number = new Intl.NumberFormat("es-AR", {
    maximumFractionDigits: 0,
  }).format(splitAmount(value));
  const symbol = (currency && currency.symbol) || "$";
  return currency && currency.position === "after"
    ? `${number} ${symbol}`
    : `${symbol} ${number}`;
}

export function parseAmount(raw) {
  if (typeof raw === "number") {
    return Number.isFinite(raw) ? raw : NaN;
  }
  const text = String(raw === undefined || raw === null ? "" : raw).trim();
  if (!text) {
    return NaN;
  }
  return Number(text.replace(/\./gu, "").replace(",", "."));
}

export function cardsOfVoucher(board, voucherId) {
  const parts = [];
  for (const column of (board && board.columns) || []) {
    for (const card of column.cards || []) {
      if (card.voucher_id === voucherId) {
        parts.push({
          ...card,
          allocation_id: column.allocation_id,
          partner_name: column.partner_name,
        });
      }
    }
  }
  return parts;
}

/* Dividido entre clientes distintos vs dividido por circuito del mismo cliente. */
export function splitKind(board, voucherId) {
  const parts = cardsOfVoucher(board, voucherId);
  if (parts.length < 2) {
    return null;
  }
  const columns = new Set(parts.map((part) => part.allocation_id));
  return columns.size > 1 ? "clientes" : "circuito";
}

export function cardClass(card) {
  const circuit = circuitOf(card && card.document_kind);
  return circuit ? circuit.cls : "c-none";
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || STATUS_LABELS.sin_iniciar;
}

export function eventLabel(eventType) {
  return EVENT_LABELS[eventType] || eventType || "";
}

export function eventBullet(eventType) {
  return EVENT_BULLETS[eventType] || "";
}

export function validateTransferAmount(raw, maximum) {
  const amount = parseAmount(raw);
  if (!Number.isFinite(amount) || amount <= 0) {
    return {valid: false, amount: 0, error: _t("El importe debe ser mayor que cero.")};
  }
  if (amount > splitAmount(maximum) + 0.001) {
    return {valid: false, amount, error: _t("El importe supera el máximo disponible.")};
  }
  return {valid: true, amount, error: ""};
}

export function transferButtonLabel({toAllocationId, unify, amount, maximum}) {
  if (!toAllocationId) {
    return _t("Devolver a Sin asignar");
  }
  if (unify) {
    return _t("Reunificar");
  }
  return splitAmount(amount) < splitAmount(maximum) - 0.001
    ? _t("Transferir parte")
    : _t("Transferir todo");
}

function sanitizeCircuit(raw) {
  const circuit = raw || {};
  return {
    collected: splitAmount(circuit.collected),
    applied: splitAmount(circuit.applied),
    available: splitAmount(circuit.available),
    total: splitAmount(circuit.total),
    pending: splitAmount(circuit.pending),
  };
}

function sanitizeText(value) {
  return value === false || value === null || value === undefined ? "" : String(value);
}

function sanitizeDocuments(rows) {
  return (rows || []).map((row) => ({
    line_id: row.line_id,
    number: sanitizeText(row.number),
    issue_date: sanitizeText(row.issue_date),
    due_date: sanitizeText(row.due_date),
    amount: splitAmount(row.amount),
    balance: splitAmount(row.balance),
    applied: splitAmount(row.applied),
  }));
}

export function sanitizeBoardPayload(raw) {
  const payload = raw || {};
  const sheet = payload.sheet || {};
  const currency = sheet.currency || {};
  return {
    sheet: {
      id: sheet.id || 0,
      name: sanitizeText(sheet.name),
      state: sanitizeText(sheet.state),
      editable: Boolean(sheet.editable),
      currency: {
        id: currency.id || 0,
        symbol: sanitizeText(currency.symbol) || "$",
        position: sanitizeText(currency.position) || "before",
        decimal_places: Number.isInteger(currency.decimal_places)
          ? currency.decimal_places
          : 2,
      },
    },
    columns: (payload.columns || []).map((column) => ({
      allocation_id: column.allocation_id,
      partner_id: column.partner_id,
      partner_name: sanitizeText(column.partner_name),
      partner_vat: sanitizeText(column.partner_vat),
      closed: Boolean(column.closed),
      note: sanitizeText(column.note),
      closed_by: sanitizeText(column.closed_by),
      closed_date: sanitizeText(column.closed_date),
      status: sanitizeText(column.status) || "sin_iniciar",
      circuits: {
        invoice: sanitizeCircuit((column.circuits || {}).invoice),
        quotation: sanitizeCircuit((column.circuits || {}).quotation),
      },
      cards: (column.cards || []).map((card) => ({
        value_id: card.value_id,
        voucher_id: card.voucher_id,
        voucher_name: sanitizeText(card.voucher_name),
        method: sanitizeText(card.method),
        reference: sanitizeText(card.reference),
        date: sanitizeText(card.date),
        amount: splitAmount(card.amount),
        voucher_amount: splitAmount(card.voucher_amount),
        document_kind: sanitizeText(card.document_kind),
        split_parts: card.split_parts || 1,
        free_amount: splitAmount(card.free_amount),
      })),
      documents: {
        invoice: sanitizeDocuments((column.documents || {}).invoice),
        quotation: sanitizeDocuments((column.documents || {}).quotation),
      },
    })),
    pool: (payload.pool || []).map((item) => ({
      voucher_id: item.voucher_id,
      voucher_name: sanitizeText(item.voucher_name),
      method: sanitizeText(item.method),
      reference: sanitizeText(item.reference),
      date: sanitizeText(item.date),
      amount: splitAmount(item.amount),
      free_amount: splitAmount(item.free_amount),
      partner_id: item.partner_id,
      partner_name: sanitizeText(item.partner_name),
    })),
    events: (payload.events || []).map((event) => ({
      id: event.id,
      allocation_id: event.allocation_id || false,
      voucher_id: event.voucher_id || false,
      event_type: sanitizeText(event.event_type),
      name: sanitizeText(event.name),
      description: sanitizeText(event.description),
      value_from: sanitizeText(event.value_from),
      value_to: sanitizeText(event.value_to),
      user_name: sanitizeText(event.user_name),
      event_date: sanitizeText(event.event_date),
    })),
  };
}

export function nextIsolate(current, voucherId) {
  return current === voucherId ? null : voucherId;
}

export function rpcErrorMessage(error) {
  if (error && error.data && error.data.message) {
    return error.data.message;
  }
  if (error && error.message) {
    return error.message;
  }
  return _t("No se pudo completar la operación del tablero.");
}
