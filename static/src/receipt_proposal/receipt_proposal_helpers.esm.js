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
  },
};

export const CIRCUIT_KEYS = ["invoice", "quotation"];

/* Los cuatro controles de la barra de filtros, en su estado neutro. Viven en
   el componente y mueren con la acción: el tablero filtra un payload que ya
   tiene, así que ningún filtro viaja al servidor. */
export const FILTER_DEFAULTS = {search: "", circuit: "", method: "", sort: "name"};

/* `name` es el orden del payload — el servidor ya devuelve las columnas por
   nombre de cliente — y por eso es el orden por defecto. Los otros tres
   ordenan descendente sobre la suma de los circuitos VISIBLES: el operador
   ordena por la cifra que las tarjetas que está mirando le muestran. */
export const SORT_ORDERS = [
  {key: "name", label: _t("Cliente A→Z")},
  {key: "debt", label: _t("Mayor deuda")},
  {key: "collected", label: _t("Mayor cobrado")},
  {key: "pending", label: _t("Más sin imputar")},
];

const SORT_FIELDS = {debt: "total", collected: "collected", pending: "available"};

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

/* Los ocho `collection.voucher.document_type`. El glifo es un canal de FORMA,
   no de color: el color de una tarjeta ya significa circuito (FAC / PRE), que
   es lo que limita a qué documentos puede imputarse su importe. Un tipo sin
   glifo propio cae en `unsupported`, que es un tipo real del catálogo. */
export const DOCUMENT_TYPE_GLYPHS = [
  "bank_transfer",
  "check",
  "echeck",
  "cash",
  "cash_deposit",
  "seller_deposit",
  "retention_certificate",
  "unsupported",
];

export function glyphOf(documentType) {
  return DOCUMENT_TYPE_GLYPHS.includes(documentType) ? documentType : "unsupported";
}

export function circuitOf(documentKind) {
  return CIRCUITS[documentKind] || null;
}

/* El filtro de circuito ESCONDE la otra tarjeta, no la borra: `hasCircuit`
   sigue decidiendo únicamente la tira `.rp-circ.empty`, porque un circuito
   vacío es la zona de drop que crea su primer valor de recibo. */
export function visibleCircuitKeys(circuit) {
  return CIRCUIT_KEYS.includes(circuit) ? [circuit] : CIRCUIT_KEYS;
}

/* Plegado de caso y de acentos: la planilla escribe `Núñez S.A.` y el
   operador teclea `nunez`. */
export function normalizeText(value) {
  return String(value === undefined || value === null ? "" : value)
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

/* El CUIT entra en el pajar porque es el único identificador que el operador
   lee de un comprobante que tiene en la mano. */
export function matchesCustomer(column, search) {
  const needle = normalizeText(search);
  if (!needle) {
    return true;
  }
  const name = normalizeText(column.partner_name);
  const vat = normalizeText(column.partner_vat);
  return `${name} ${vat}`.includes(needle);
}

export function columnTotals(column, kinds) {
  const totals = {collected: 0, total: 0, available: 0};
  for (const kind of kinds) {
    const figures = column.circuits[kind];
    totals.collected += figures.collected;
    totals.total += figures.total;
    totals.available += figures.available;
  }
  return totals;
}

/* Ordena sobre una COPIA. `columns` es la respuesta del servidor y el tablero
   se relee contra ella en cada refresco, así que un `sort()` en el lugar
   reescribiría en silencio el orden que `name` tiene que poder devolver. */
export function sortColumns(columns, order, kinds) {
  const field = SORT_FIELDS[order];
  if (!field) {
    return [...columns];
  }
  return [...columns].sort(
    (left, right) =>
      columnTotals(right, kinds)[field] - columnTotals(left, kinds)[field]
  );
}

export function filterPool(pool, method) {
  return method ? pool.filter((item) => item.document_type === method) : [...pool];
}

/* Las opciones salen del pool mismo, así el control nunca ofrece un filtro
   que vaciaría la columna. La clave es el `document_type` crudo: `method` es la
   etiqueta traducida y no se puede indexar por ella — por eso el payload
   manda las dos. */
export function poolMethodOptions(pool) {
  const options = new Map();
  for (const item of pool) {
    if (!options.has(item.document_type)) {
      options.set(item.document_type, {code: item.document_type, label: item.method});
    }
  }
  return [...options.values()].sort((left, right) =>
    left.label.localeCompare(right.label, "es")
  );
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

/* The imputation table is six columns inside half a customer card, and every
   figure in it is in the sheet's currency — so the symbol is a header's job,
   not a cell's. Bare numbers also line the two money columns up with the
   Imputado input, which has always taken one. */
export function formatBare(value, currency) {
  const decimals =
    currency && Number.isInteger(currency.decimal_places) ? currency.decimal_places : 2;
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(splitAmount(value));
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

/* The imputation table gives a date one narrow column inside half a customer
   card, where an ISO date costs the money columns ten characters it cannot
   spare. The year still reads, so 2025 and 2026 stay apart. */
export function formatShortDate(value) {
  const text = String(value === undefined || value === null ? "" : value).trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})/u.exec(text);
  return iso ? `${iso[3]}/${iso[2]}/${iso[1].slice(2)}` : text;
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
        document_type: glyphOf(sanitizeText(card.document_type)),
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
      document_type: glyphOf(sanitizeText(item.document_type)),
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
