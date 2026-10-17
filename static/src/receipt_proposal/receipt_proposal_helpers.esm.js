/** @odoo-module **/

import {
  parseAmount,
  rawAmount,
} from "@collection_receipt_proposal/receipt_proposal/amount_parser.esm";
import {_t} from "@web/core/l10n/translation";

/* Typed amounts are read by the user's locale; the pure parser lives in its
   own import-free module so plain Node can test it. */
export {parseAmount, rawAmount};

export const BOARD_MODEL = "collection.sheet";
export const PREVIEW_DEBOUNCE_MS = 250;

/* Tolerancia de comparación de importes. Las figuras llegan sumadas en punto
   flotante, así que "igual" e "cero" se preguntan contra este margen y nunca
   con `===`. */
export const AMOUNT_EPSILON = 0.001;

/* Auto-scroll de arrastre. HTML5 drag and drop no desplaza nada por su cuenta:
   el operador arrastra un valor hasta el borde del carril y el cliente al que
   apunta simplemente no está en pantalla. `AUTOSCROLL_EDGE` es el ancho de la
   franja de borde en la que el gesto ya pide scroll y `AUTOSCROLL_STEP` el paso
   máximo por cuadro — a 60 fps, ~1300 px/s pegado al borde, que recorre un
   carril largo sin pasarse de la tarjeta que el operador está buscando. */
const AUTOSCROLL_EDGE = 72;
const AUTOSCROLL_STEP = 22;

/* Los dos circuitos de Cobrado. Una tarjeta asignada pertenece a UNO solo y su
   importe únicamente puede imputarse a documentos de ese tipo. */
export const CIRCUITS = {
  invoice: {
    key: "invoice",
    tag: "FAC",
    cls: "c-inv",
    short: "inv",
    noun: "facturas",
    one: "factura",
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
    one: "presupuesto",
    Noun: "Presupuestos",
    doc: "Presupuesto",
    long: "Cobrado a aplicar a Presupuestos",
  },
};

export const CIRCUIT_KEYS = ["invoice", "quotation"];

/* La retención es el único tipo que NO vuelve a Sin asignar: es impuesto que
   el cliente retuvo sobre sus propios documentos, así que por construcción es
   plata de ese cliente y un botón de tablero no puede ofrecérsela a otro. */
export const RETENTION_CERTIFICATE = "retention_certificate";

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

/* Los ocho `collection.voucher.document_type`. El glifo es un canal de FORMA,
   no de color: el color de una tarjeta ya significa circuito (FAC / PRE), que
   es lo que limita a qué documentos puede imputarse su importe. Un tipo sin
   glifo propio cae en `unsupported`, que es un tipo real del catálogo. */
const DOCUMENT_TYPE_GLYPHS = [
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

/* Las filas de un circuito se agrupan por TIPO DE COMPROBANTE. El circuito ya
   lo fija la tarjeta que las contiene —todas son FAC o todas son PRE—, así que
   el único tipo que varía de fila a fila es el del comprobante, que es además
   el que el operador tiene en la mano mientras concilia: los cheques juntos,
   las transferencias juntas. Ordena por la etiqueta traducida, la misma clave
   que ordena el select de método, para que la tarjeta y el filtro nombren los
   tipos en el mismo orden. Sobre una COPIA, como `sortColumns`: `column.cards`
   es la respuesta del servidor y el tablero se relee contra ella en cada
   refresco. Y con un solo criterio: el `sort` de JS es estable, así que dentro
   de un tipo sobrevive el orden del payload —el de los `value_id`— y una fila
   nunca salta de lugar por un refresco que no la tocó. */
export function sortCardsByType(cards) {
  return [...cards].sort((left, right) =>
    String(left.method || "").localeCompare(String(right.method || ""), "es")
  );
}

/* El control ofrece el catálogo COMPLETO de tipos de la compañía, no sólo los
   que el pool tiene en este momento: el operador filtra por el tipo que tiene
   en la mano, y sacado el último cheque del pool la opción `check` —y con ella
   el filtro— desaparecía debajo del cursor. El pool se recorre igual, por si
   trae un tipo que el catálogo ya no permite pero un comprobante viejo todavía
   lleva. La clave es siempre el `document_type` crudo: `method` es la etiqueta
   traducida y no se puede indexar por ella — por eso el payload manda las dos. */
export function methodOptions(documentTypes, pool) {
  const options = new Map();
  for (const type of documentTypes || []) {
    options.set(type.code, {code: type.code, label: type.label});
  }
  for (const item of pool || []) {
    if (!options.has(item.document_type)) {
      options.set(item.document_type, {code: item.document_type, label: item.method});
    }
  }
  return [...options.values()].sort((left, right) =>
    left.label.localeCompare(right.label, "es")
  );
}

function splitAmount(value) {
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

/* Este resumen tiene que prometer exactamente lo que el servidor va a hacer,
   así que cuenta todo salvo las retenciones — el único tipo que se queda. */
export function resetSummary(board) {
  const summary = {cards: 0, customers: 0, amount: 0};
  for (const column of (board && board.columns) || []) {
    const movable = (column.cards || []).filter(
      (card) => card.document_type !== RETENTION_CERTIFICATE
    );
    if (!movable.length) {
      continue;
    }
    summary.customers += 1;
    summary.cards += movable.length;
    for (const card of movable) {
      summary.amount += splitAmount(card.amount);
    }
  }
  return summary;
}

export function resetBlockers(board) {
  return ((board && board.columns) || [])
    .filter(
      (column) =>
        column.closed &&
        (column.cards || []).some(
          (card) => card.document_type !== RETENTION_CERTIFICATE
        )
    )
    .map((column) => column.partner_name);
}

/* Cuánto de la deuda cubre lo cobrado, para las dos barras de progreso: la
   del circuito y la del cliente en el drawer. Sin deuda pero con plata, la
   barra se llena: no falta nada por cubrir. */
export function coverageOf(collected, total) {
  let ratio = 0;
  if (total > 0) {
    ratio = (splitAmount(collected) / splitAmount(total)) * 100;
  } else if (collected > 0) {
    ratio = 100;
  }
  return {
    percent: Math.max(Math.round(ratio), 0),
    fill: Math.min(Math.max(ratio, 0), 100),
  };
}

/* La clase de color de una tarjeta de valor — la del pool y la fila asignada —
   sale del TIPO de comprobante, no del circuito: la fila vive dentro de la
   tarjeta de circuito que ya dice FAC o PRE, y la tarjeta del pool todavía no
   tiene circuito ninguno. Pasa por `glyphOf` para que la clase no pueda nombrar
   una regla que el SCSS no tiene: un tipo sin glifo propio cae en
   `.t-unsupported`, que es el gris de la casa. */
export function typeClass(documentType) {
  return `t-${glyphOf(documentType)}`;
}

/* Redondea a los decimales de la moneda. La aritmética de flotantes deja
   restos que cualquier atajo sembraría en el input tal cual, y `Math.round`
   no sirve: truncaría los centavos que el operador sí tiene que ver. */
export function roundAmount(value, currency) {
  const decimals =
    currency && Number.isInteger(currency.decimal_places) ? currency.decimal_places : 2;
  return Number(splitAmount(value).toFixed(decimals));
}

/* Cuánta plata le falta a un circuito para cubrir su deuda: lo que los
   documentos todavía deben menos lo cobrado ahí. Es la pregunta que el
   operador contesta cuando parte un valor, y NO es `pending` (deuda −
   imputado), que ya descuenta lo que FIFO aplicó y por eso lee de menos
   mientras la plata está en el circuito sin imputar. Negativo = sobra.
   Se redondea a la moneda: la resta de dos sumas de flotantes deja restos
   que el atajo `Cubrir` sembraría en el input tal cual. */
export function circuitGap(figures, currency) {
  const circuit = figures || {};
  return roundAmount(
    splitAmount(circuit.total) - splitAmount(circuit.collected),
    currency
  );
}

/* `separators` are the user's `localization` decimal point and thousands
   separator: the component passes them, the helpers never read a service. */
export function validateTransferAmount(raw, maximum, separators) {
  const amount = parseAmount(raw, separators);
  if (!Number.isFinite(amount) || amount <= 0) {
    return {valid: false, amount: 0, error: _t("El importe debe ser mayor que cero.")};
  }
  if (amount > splitAmount(maximum) + AMOUNT_EPSILON) {
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
  return splitAmount(amount) < splitAmount(maximum) - AMOUNT_EPSILON
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
    /* El catálogo de tipos de valor de la compañía, con la etiqueta ya
       traducida por el servidor. Sólo el filtro lo usa; el glifo se sigue
       resolviendo con `glyphOf` en el punto de dibujo, que es lo que deja a
       `document_type` llegar crudo y comparable hasta el filtro. */
    document_types: (payload.document_types || []).map((type) => ({
      code: sanitizeText(type.code),
      label: sanitizeText(type.label),
    })),
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
        document_type: sanitizeText(card.document_type),
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
      document_type: sanitizeText(item.document_type),
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

/* Cuánto desplazar UN eje según dónde cayó el puntero dentro de él: negativo
   cerca del arranque, positivo cerca del final, 0 en el medio. El paso crece
   lineal con lo adentro de la franja que esté el puntero — rozarla desplaza
   despacio, pegarse al borde desplaza al máximo — y sale entero para que
   `scrollTop` no vaya acumulando restos de flotante. Fuera del contenedor
   cuenta como pegado al borde: el puntero se va del carril antes de que el
   botón se suelte y el scroll tiene que seguir. La franja nunca pasa de la
   mitad del eje, para que un contenedor bajo no quede scrolleando siempre. */
function axisScrollStep(start, end, position) {
  const span = end - start;
  if (span <= 0) {
    return 0;
  }
  const edge = Math.min(AUTOSCROLL_EDGE, span / 2);
  if (position < start + edge) {
    const depth = Math.max(position - start, 0) / edge;
    return -Math.ceil((1 - depth) * AUTOSCROLL_STEP);
  }
  if (position > end - edge) {
    const depth = Math.max(end - position, 0) / edge;
    return Math.ceil((1 - depth) * AUTOSCROLL_STEP);
  }
  return 0;
}

/* El paso de auto-scroll de un contenedor para un puntero, `{x, y}` en píxeles.
   Puro y por eje, así el bucle de arrastre es sólo "leer rect, sumar, escribir"
   y los dos sentidos —arriba y abajo— salen de la misma cuenta. */
export function autoscrollDelta(rect, x, y) {
  return {
    x: axisScrollStep(rect.left, rect.right, x),
    y: axisScrollStep(rect.top, rect.bottom, y),
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
