/** @odoo-module **/

import {
  AMOUNT_EPSILON,
  BOARD_MODEL,
  CIRCUITS,
  CIRCUIT_KEYS,
  FILTER_DEFAULTS,
  PREVIEW_DEBOUNCE_MS,
  SORT_ORDERS,
  autoscrollDelta,
  cardsOfVoucher,
  circuitGap,
  circuitOf,
  columnTotals,
  coverageOf,
  eventBullet,
  filterPool,
  formatAmount,
  formatBare,
  formatShort,
  formatShortDate,
  glyphOf,
  matchesCustomer,
  methodOptions,
  nextIsolate,
  parseAmount,
  rawAmount,
  resetBlockers,
  resetSummary,
  roundAmount,
  rpcErrorMessage,
  sanitizeBoardPayload,
  sortCardsByType,
  sortColumns,
  splitKind,
  transferButtonLabel,
  typeClass,
  validateTransferAmount,
  visibleCircuitKeys,
} from "@collection_receipt_proposal/receipt_proposal/receipt_proposal_helpers.esm";
import {Component, onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {ControlPanel} from "@web/search/control_panel/control_panel";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useHotkey} from "@web/core/hotkeys/hotkey_hook";
import {useService} from "@web/core/utils/hooks";

/* Los dos valores de `overflow` que hacen a un elemento scrolleable de verdad.
   `hidden` también acepta que le escriban `scrollTop`, y el tablero está lleno
   de tarjetas con `overflow: hidden`: sin este filtro, la primera de ellas se
   tragaría el gesto y desplazaría su propio contenido en vez de dejar pasar el
   arrastre al carril. */
const SCROLLABLE_OVERFLOW = new Set(["auto", "scroll"]);

export class ReceiptProposalAction extends Component {
  static template = "collection_receipt_proposal.ReceiptProposalAction";
  static components = {ControlPanel};
  static props = {...standardActionServiceProps};

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");
    this.circuits = CIRCUITS;
    this.circuitKeys = CIRCUIT_KEYS;
    this.state = useState({
      board: null,
      loading: true,
      busy: false,
      isolate: null,
      collapsed: [],
      openSplits: [],
      menu: null,
      modal: null,
      drawer: null,
      details: [],
      dropTarget: null,
      filters: {...FILTER_DEFAULTS},
    });
    this.dragged = null;
    this.previewTimer = null;
    this.dragPointer = null;
    this.dragScrollListener = null;
    this.dragScrollFrame = null;
    useHotkey("escape", () => this.onEscape());
    onWillStart(() => this.loadBoard());
    onWillUnmount(() => {
      this.clearPreviewTimer();
      this.stopAutoScroll();
    });
  }

  // ----------------------------------------------------------------
  // Data
  // ----------------------------------------------------------------

  get sheetId() {
    const params = this.props.action && this.props.action.params;
    const sheetId = params ? params.sheet_id : undefined;
    if (!Number.isInteger(sheetId) || sheetId <= 0) {
      return false;
    }
    return sheetId;
  }

  get columns() {
    return (this.state.board && this.state.board.columns) || [];
  }

  get pool() {
    return (this.state.board && this.state.board.pool) || [];
  }

  get events() {
    return (this.state.board && this.state.board.events) || [];
  }

  get documentTypes() {
    return (this.state.board && this.state.board.document_types) || [];
  }

  get currency() {
    return this.state.board ? this.state.board.sheet.currency : null;
  }

  get editable() {
    return Boolean(this.state.board && this.state.board.sheet.editable);
  }

  get hasBoard() {
    return Boolean(this.state.board);
  }

  get poolTotal() {
    return this.visiblePool.reduce((total, item) => total + item.free_amount, 0);
  }

  /* `Requiere asignación` / `Todo asignado` y el `Pendiente de asignar` son
     hechos de la planilla, no del filtro: una columna que un filtro de tipo
     dejó vacía NO puede declarar que la cobranza está terminada. */
  get sheetPoolTotal() {
    return this.pool.reduce((total, item) => total + item.free_amount, 0);
  }

  /* The customer lane's header sums what the lane is showing: the visible
     customers, over the visible circuits. */
  // The lane header carries the two figures the circuit cards themselves are
  // read by — collected and debt. Imputado and Sin imputar are per-circuit
  // questions the card below answers, so the header does not sum them.
  // Debt is `total`, the documents' own balance, exactly what a card's Deuda
  // shows — never `pending`, which is that balance net of what is already
  // imputed and therefore reads $ 0 on a board that is fully distributed.
  get laneTotals() {
    return this.columnsTotals(this.visibleColumns, this.visibleCircuitKeys);
  }

  /* La cifra sin filtrar, que el encabezado muestra al lado de la filtrada:
     filtrar a cinco clientes para preguntar cuánta plata hay en juego es la
     razón por la que el operador filtra, y un encabezado que siguiera sumando
     cuarenta y siete contestaría una pregunta que nadie hizo. */
  get sheetTotals() {
    return this.columnsTotals(this.columns, CIRCUIT_KEYS);
  }

  columnsTotals(columns, kinds) {
    const totals = {collected: 0, total: 0};
    for (const column of columns) {
      const figures = columnTotals(column, kinds);
      totals.collected += figures.collected;
      totals.total += figures.total;
    }
    return totals;
  }

  // ----------------------------------------------------------------
  // Filtros — vistas sobre el payload que el tablero ya tiene
  // ----------------------------------------------------------------

  /* Los filtros ESCONDEN, nunca deshabilitan. Una tarjeta oculta deja de ser
     zona de drop porque no está en pantalla, y eso es una elección explícita
     del operador que el mismo control revierte: nada se auto-revela al
     arrastrar, ninguna mutación limpia un filtro y `Escape` sigue
     significando "cerrá las capas, después los circuitos abiertos". */
  get visibleCircuitKeys() {
    return visibleCircuitKeys(this.state.filters.circuit);
  }

  get visibleColumns() {
    const matched = this.columns.filter((column) =>
      matchesCustomer(column, this.state.filters.search)
    );
    return sortColumns(matched, this.state.filters.sort, this.visibleCircuitKeys);
  }

  get visiblePool() {
    return filterPool(this.pool, this.state.filters.method);
  }

  /* Todo el catálogo de tipos de la compañía, no sólo los que el pool tiene
     ahora: el operador filtra por el tipo que tiene en la mano, y la opción no
     puede desaparecer porque se asignó el último comprobante de ese tipo. */
  get methodOptions() {
    return methodOptions(this.documentTypes, this.pool);
  }

  /* El control de tipo existe sólo cuando hay entre qué elegir: con el pool
     vacío no hay nada que filtrar, y con un solo tipo en el catálogo filtrar
     por él es no filtrar. Se ESCONDE en vez de deshabilitarse — un control
     muerto en pantalla se lee como un control roto, que es exactamente lo que
     un `disabled` sobre un pool vacío parecía. */
  get canFilterMethod() {
    return this.pool.length > 0 && this.methodOptions.length > 1;
  }

  get sortOrders() {
    return SORT_ORDERS;
  }

  get hasFilters() {
    const filters = this.state.filters;
    return Object.keys(FILTER_DEFAULTS).some(
      (key) => filters[key] !== FILTER_DEFAULTS[key]
    );
  }

  setCircuitFilter(circuit) {
    this.state.filters.circuit = this.state.filters.circuit === circuit ? "" : circuit;
  }

  clearFilters() {
    this.state.filters = {...FILTER_DEFAULTS};
  }

  async loadBoard() {
    const sheetId = this.sheetId;
    this.state.loading = true;
    if (!sheetId) {
      this.notification.add(
        _t("Se requiere una planilla de cobranza válida para el tablero."),
        {type: "danger"}
      );
      this.state.board = null;
      this.state.loading = false;
      return;
    }
    try {
      const payload = await this.orm.call(BOARD_MODEL, "get_proposal_board", [sheetId]);
      this.applyBoard(payload);
    } catch (error) {
      this.notifyError(error);
      this.state.board = null;
    } finally {
      this.state.loading = false;
    }
  }

  applyBoard(payload) {
    this.state.board = sanitizeBoardPayload(payload);
    const columnIds = new Set(this.columns.map((column) => column.allocation_id));
    this.state.collapsed = this.state.collapsed.filter((id) => columnIds.has(id));
    const valueIds = new Set();
    for (const column of this.columns) {
      for (const card of column.cards) {
        valueIds.add(card.value_id);
      }
    }
    this.state.openSplits = this.state.openSplits.filter((id) => valueIds.has(id));
    /* El de tipo de valor es el único filtro que puede quedar sin control que
       lo revierta: vaciado el pool, la barra deja de dibujar el select y un
       filtro `check` seguiría escondiendo tarjetas sin nada que lo limpie. Se
       limpia contra lo que el control ofrece —el catálogo, no el pool crudo—
       así el filtro nunca sobrevive al control que lo puso. Los otros tres
       sobreviven a cualquier refresco. */
    const offered = new Set(
      this.canFilterMethod ? this.methodOptions.map((option) => option.code) : []
    );
    if (this.state.filters.method && !offered.has(this.state.filters.method)) {
      this.state.filters.method = "";
    }
    if (this.state.drawer && !columnIds.has(this.state.drawer.allocation_id)) {
      this.state.drawer = null;
    }
    this.syncDetails();
  }

  async runMutation(rpcCall, successMessage) {
    if (this.state.busy) {
      return false;
    }
    this.state.busy = true;
    try {
      const payload = await rpcCall();
      this.applyBoard(payload);
      if (successMessage) {
        this.notification.add(successMessage, {type: "success"});
      }
      return true;
    } catch (error) {
      this.notifyError(error);
      return false;
    } finally {
      this.state.busy = false;
    }
  }

  notifyError(error) {
    this.notification.add(rpcErrorMessage(error), {type: "danger"});
  }

  // ----------------------------------------------------------------
  // Formatting and lookups
  // ----------------------------------------------------------------

  fmt(value) {
    return formatAmount(value, this.currency);
  }

  fmtShort(value) {
    return formatShort(value, this.currency);
  }

  fmtDate(value) {
    return value ? formatShortDate(value) : "—";
  }

  fmtBare(value) {
    return formatBare(value, this.currency);
  }

  circuitTag(documentKind) {
    const circuit = circuitOf(documentKind);
    return circuit ? circuit.tag : "S/C";
  }

  circuitClass(documentKind) {
    const circuit = circuitOf(documentKind);
    return circuit ? circuit.short : "none";
  }

  /* Cuántos documentos reimputa un plan del panel de previsualización, con el
     sustantivo pegado al número: dos `t-out` hermanos los renderizaban sin el
     espacio del medio ("1facturas"). Concuerda en número, y cuando el modal ya
     fijó el circuito el sustantivo es neutro — ver `previewCircuits`. */
  previewCountLabel(plan, withCircuit) {
    const count = (plan.changes || []).length;
    const circuit = withCircuit ? circuitOf(plan.document_kind) : null;
    if (!circuit) {
      return `${count} ${count === 1 ? _t("documento") : _t("documentos")}`;
    }
    return `${count} ${count === 1 ? circuit.one : circuit.noun}`;
  }

  /* El sustantivo suelto, para las líneas que no llevan número. */
  previewNoun(plan, withCircuit) {
    const circuit = withCircuit ? circuitOf(plan.document_kind) : null;
    return circuit ? circuit.noun : _t("documentos");
  }

  typeClass(documentType) {
    return typeClass(documentType);
  }

  glyphOf(documentType) {
    return glyphOf(documentType);
  }

  /* La tarjeta del pool es angosta y trunca método, referencia y cliente, así
     que los tres viajan enteros en el `title`: el operador arrastra al cliente
     que pagó, y ese nombre no puede quedar cortado sin forma de leerlo. */
  poolCardTitle(item) {
    return [item.method, item.reference, item.partner_name].filter(Boolean).join(" · ");
  }

  eventBullet(eventType) {
    return eventBullet(eventType);
  }

  columnById(allocationId) {
    return this.columns.find((column) => column.allocation_id === allocationId) || null;
  }

  cardsOfVoucher(voucherId) {
    return cardsOfVoucher(this.state.board, voucherId);
  }

  splitKind(voucherId) {
    return splitKind(this.state.board, voucherId);
  }

  isSplit(voucherId) {
    return this.cardsOfVoucher(voucherId).length > 1;
  }

  /* El comprobante partido se lee como "parte i de n", no como un multiplicador. */
  splitPosition(card) {
    const parts = this.cardsOfVoucher(card.voucher_id);
    const index = parts.findIndex((part) => part.value_id === card.value_id);
    const total = parts.length || card.split_parts || 1;
    return `${index >= 0 ? index + 1 : 1}/${total}`;
  }

  splitLabel(card) {
    const kind = this.splitKind(card.voucher_id);
    const position = this.splitPosition(card);
    if (kind === "circuito") {
      return _t("Parte %s — dividido por circuito", position);
    }
    return _t("Parte %s — dividido entre clientes", position);
  }

  hasCircuit(column, kind) {
    return column.documents[kind].length > 0 || column.circuits[kind].collected !== 0;
  }

  /* Un circuito que todavía no recibió plata: tiene deuda que mostrar, pero
     ni barra de cobertura (siempre 0 %) ni filas que listar. La tarjeta se
     queda en su encabezado — figuras incluidas — en vez de gastar media
     tarjeta de cliente en un cartel de vacío por cada circuito. */
  hasValues(column, kind) {
    return this.circuitCards(column, kind).length > 0;
  }

  /* Agrupadas por tipo de comprobante: el circuito es el mismo para todas las
     filas de esta tarjeta, así que el tipo es lo único que las distingue. */
  circuitCards(column, kind) {
    return sortCardsByType(column.cards.filter((card) => card.document_kind === kind));
  }

  /* The card header carries this circuit's figures, and while the circuit is
     expanded it carries the ones the operator's own inputs are producing —
     otherwise the detail would need a second figures line restating them. */
  circuitFigures(column, kind) {
    const figures = column.circuits[kind];
    const detail = this.detailOf(column.allocation_id, kind);
    if (!detail) {
      return figures;
    }
    const applied = this.imputeApplied(detail);
    return {
      ...figures,
      applied,
      available: figures.collected - applied,
      pending: this.imputePending(detail),
    };
  }

  circuitCoverage(column, kind) {
    const figures = column.circuits[kind];
    return coverageOf(figures.collected, figures.total);
  }

  isCollapsed(allocationId) {
    return this.state.collapsed.includes(allocationId);
  }

  toggleCollapsed(allocationId) {
    this.state.collapsed = this.isCollapsed(allocationId)
      ? this.state.collapsed.filter((id) => id !== allocationId)
      : [...this.state.collapsed, allocationId];
  }

  isSplitOpen(valueId) {
    return this.state.openSplits.includes(valueId);
  }

  toggleSplitOpen(valueId) {
    this.state.openSplits = this.isSplitOpen(valueId)
      ? this.state.openSplits.filter((id) => id !== valueId)
      : [...this.state.openSplits, valueId];
  }

  isDimmedCard(card) {
    return Boolean(this.state.isolate) && this.state.isolate !== card.voucher_id;
  }

  isDimmedColumn(column) {
    if (!this.state.isolate) {
      return false;
    }
    return !column.cards.some((card) => card.voucher_id === this.state.isolate);
  }

  get isolatedParts() {
    return this.state.isolate ? this.cardsOfVoucher(this.state.isolate) : [];
  }

  clearIsolate() {
    this.state.isolate = null;
  }

  toggleIsolate(voucherId) {
    this.state.isolate = nextIsolate(this.state.isolate, voucherId);
  }

  // ----------------------------------------------------------------
  // Drag and drop
  // ----------------------------------------------------------------

  onCardDragStart(ev, card) {
    if (!this.editable) {
      ev.preventDefault();
      return;
    }
    this.dragged = {value_id: card.value_id, voucher_id: card.voucher_id};
    this.startAutoScroll();
    ev.dataTransfer.effectAllowed = "move";
    ev.dataTransfer.setData("text/plain", String(card.value_id));
  }

  onPoolDragStart(ev, item) {
    if (!this.editable) {
      ev.preventDefault();
      return;
    }
    this.dragged = {voucher_id: item.voucher_id};
    this.startAutoScroll();
    ev.dataTransfer.effectAllowed = "move";
    ev.dataTransfer.setData("text/plain", `v${item.voucher_id}`);
  }

  onDragEnd() {
    this.dragged = null;
    this.state.dropTarget = null;
    this.stopAutoScroll();
  }

  /* Mientras dura un arrastre el tablero se desplaza solo cuando el puntero
     entra en la franja de borde de un contenedor scrolleable — hacia abajo al
     pie de la pantalla, hacia arriba en la cabecera, y lo mismo a los lados.
     El puntero se lee en `dragover` en CAPTURA: las zonas de drop paran la
     propagación en burbuja, y la captura corre antes que ellas, así que el
     seguimiento no depende de sobre qué elemento esté pasando el valor. El
     desplazamiento en sí va en su propio `requestAnimationFrame`, porque
     `dragover` se dispara a ritmo del mouse y deja de dispararse en cuanto el
     puntero se queda quieto contra el borde, que es justo cuando el operador
     está esperando que la lista siga corriendo. */
  startAutoScroll() {
    if (this.dragScrollListener) {
      return;
    }
    this.dragScrollListener = (ev) => {
      this.dragPointer = {x: ev.clientX, y: ev.clientY};
    };
    document.addEventListener("dragover", this.dragScrollListener, true);
    this.dragScrollFrame = window.requestAnimationFrame(() => this.autoScrollFrame());
  }

  stopAutoScroll() {
    if (this.dragScrollListener) {
      document.removeEventListener("dragover", this.dragScrollListener, true);
      this.dragScrollListener = null;
    }
    if (this.dragScrollFrame) {
      window.cancelAnimationFrame(this.dragScrollFrame);
      this.dragScrollFrame = null;
    }
    this.dragPointer = null;
  }

  autoScrollFrame() {
    this.dragScrollFrame = null;
    if (!this.dragScrollListener) {
      return;
    }
    if (this.dragPointer) {
      this.autoScrollAt(this.dragPointer.x, this.dragPointer.y);
    }
    this.dragScrollFrame = window.requestAnimationFrame(() => this.autoScrollFrame());
  }

  /* El que se desplaza es el contenedor scrolleable más cercano al puntero que
     TODAVÍA tenga recorrido en el sentido pedido: el carril de clientes y el
     pool scrollean vertical, el tablero horizontal, y un carril que ya tocó
     fondo le cede el gesto al tablero en vez de tragárselo. Por eso se sube por
     los ancestros hasta que uno se mueva de verdad. */
  autoScrollAt(x, y) {
    let node = document.elementFromPoint(x, y);
    while (node && node !== document.body) {
      const step = autoscrollDelta(node.getBoundingClientRect(), x, y);
      const style = window.getComputedStyle(node);
      const top = node.scrollTop;
      const left = node.scrollLeft;
      if (step.y && SCROLLABLE_OVERFLOW.has(style.overflowY)) {
        node.scrollTop = top + step.y;
      }
      if (step.x && SCROLLABLE_OVERFLOW.has(style.overflowX)) {
        node.scrollLeft = left + step.x;
      }
      if (node.scrollTop !== top || node.scrollLeft !== left) {
        return;
      }
      node = node.parentElement;
    }
  }

  /* A drop zone is the pool column or one (customer, circuit) card: dropping
     onto FAC or PRE already answers the circuit question the modal used to
     ask. The whole card is the target, not just the rows holding vouchers. */
  zoneKey(column, kind) {
    return column ? `${column.allocation_id}:${kind}` : "pool";
  }

  onZoneDragOver(ev, column, kind) {
    if (!this.dragged) {
      return;
    }
    ev.preventDefault();
    ev.stopPropagation();
    ev.dataTransfer.dropEffect = column && column.closed ? "none" : "move";
    const key = this.zoneKey(column, kind);
    if (this.state.dropTarget !== key) {
      this.state.dropTarget = key;
    }
  }

  onZoneDragLeave(ev) {
    if (!ev.currentTarget.contains(ev.relatedTarget)) {
      this.state.dropTarget = null;
    }
  }

  zoneClass(column, kind) {
    if (this.state.dropTarget !== this.zoneKey(column, kind)) {
      return "";
    }
    return column && column.closed ? "dropping-blocked" : "dropping";
  }

  onZoneDrop(ev, column, kind) {
    ev.preventDefault();
    ev.stopPropagation();
    const dragged = this.dragged;
    this.dragged = null;
    this.state.dropTarget = null;
    this.stopAutoScroll();
    if (!dragged) {
      return;
    }
    if (column && column.closed) {
      this.notification.add(
        _t("El cliente está cerrado. Reabrilo para modificar imputaciones."),
        {type: "warning"}
      );
      return;
    }
    if (!column && !dragged.value_id) {
      return;
    }
    /* Dropped back onto the circuit it already sits in: not a transfer, and the
       circuit is no longer a question the modal could re-ask. Ignore it. */
    if (column && dragged.value_id) {
      const card = this.findCard(dragged.value_id);
      if (
        card &&
        card.document_kind === kind &&
        this.allocationOfCard(card) === column.allocation_id
      ) {
        return;
      }
    }
    this.openTransfer(dragged, column ? column.allocation_id : null, kind);
  }

  // ----------------------------------------------------------------
  // Context menu
  // ----------------------------------------------------------------

  openMenu(ev, card, column) {
    ev.preventDefault();
    this.state.menu = {
      card,
      allocation_id: column.allocation_id,
      closed: column.closed,
      x: Math.min(ev.clientX, window.innerWidth - 260),
      y: Math.min(ev.clientY, window.innerHeight - 260),
    };
  }

  closeMenu() {
    this.state.menu = null;
  }

  get menuStyle() {
    const menu = this.state.menu;
    return menu ? `left: ${menu.x}px; top: ${menu.y}px;` : "";
  }

  // ----------------------------------------------------------------
  // Transfer modal
  // ----------------------------------------------------------------

  openTransfer(source, toAllocationId, kind) {
    this.closeMenu();
    const card = source.value_id
      ? this.findCard(source.value_id)
      : this.findPoolItem(source.voucher_id);
    if (!card) {
      return;
    }
    const maximum = source.value_id ? card.amount : card.free_amount;
    this.state.modal = {
      type: "transfer",
      value_id: source.value_id || null,
      voucher_id: card.voucher_id,
      method: card.method,
      reference: card.reference,
      source_kind: source.value_id ? card.document_kind : "",
      source_allocation_id: source.value_id ? this.allocationOfCard(card) : null,
      to_allocation_id: toAllocationId,
      kind: toAllocationId ? kind || "" : "",
      amount: maximum,
      raw_amount: rawAmount(maximum),
      maximum,
      unify: true,
      preview: [],
      previewLoading: false,
      error: "",
    };
    this.syncTransfer();
  }

  findCard(valueId) {
    for (const column of this.columns) {
      const card = column.cards.find((item) => item.value_id === valueId);
      if (card) {
        return card;
      }
    }
    return null;
  }

  allocationOfCard(card) {
    for (const column of this.columns) {
      if (column.cards.some((item) => item.value_id === card.value_id)) {
        return column.allocation_id;
      }
    }
    return null;
  }

  findPoolItem(voucherId) {
    return this.pool.find((item) => item.voucher_id === voucherId) || null;
  }

  get transferTwin() {
    const modal = this.state.modal;
    if (!modal || modal.type !== "transfer" || !modal.to_allocation_id || !modal.kind) {
      return null;
    }
    const column = this.columnById(modal.to_allocation_id);
    if (!column) {
      return null;
    }
    return (
      column.cards.find(
        (card) =>
          card.voucher_id === modal.voucher_id &&
          card.document_kind === modal.kind &&
          card.value_id !== modal.value_id
      ) || null
    );
  }

  get transferIsUnify() {
    return Boolean(this.transferTwin) && this.state.modal.unify;
  }

  get transferButtonLabel() {
    const modal = this.state.modal;
    return transferButtonLabel({
      toAllocationId: modal.to_allocation_id,
      unify: this.transferIsUnify,
      amount: modal.amount,
      maximum: modal.maximum,
    });
  }

  get transferTargetName() {
    const modal = this.state.modal;
    if (!modal.to_allocation_id) {
      return _t("Sin asignar");
    }
    const column = this.columnById(modal.to_allocation_id);
    return column ? column.partner_name : "";
  }

  get transferSourceName() {
    const modal = this.state.modal;
    if (!modal.source_allocation_id) {
      return _t("Sin asignar");
    }
    const column = this.columnById(modal.source_allocation_id);
    return column ? column.partner_name : "";
  }

  /* Las cifras del circuito que el gesto eligió. El modal tapa la tarjeta que
     las traía, y partir un valor es exactamente la pregunta "¿cuánto falta
     acá?": sin esta línea el operador tenía que cerrar el modal, leer la
     tarjeta y volver a arrastrar. Se lee, no se toca — como el `tstrip`.
     Un lado que no es un circuito (el pool) no aporta grupo: no tiene deuda. */
  get transferFigureGroups() {
    const modal = this.state.modal;
    const groups = [];
    const source = this.circuitFiguresOf(modal.source_allocation_id, modal.source_kind);
    if (source) {
      groups.push({
        key: "source",
        label: _t("Origen"),
        figures: source,
        gap: circuitGap(source, this.currency),
      });
    }
    const target = this.circuitFiguresOf(modal.to_allocation_id, modal.kind);
    if (target) {
      groups.push({
        key: "target",
        label: _t("Destino"),
        figures: target,
        gap: circuitGap(target, this.currency),
      });
    }
    return groups;
  }

  circuitFiguresOf(allocationId, kind) {
    if (!allocationId || !kind) {
      return null;
    }
    const column = this.columnById(allocationId);
    return column ? column.circuits[kind] || null : null;
  }

  /* El faltante del destino, y sólo cuando nombra un importe que los otros
     atajos no dan: si falta más que el máximo, `Todo` ya es esa respuesta, y
     si no falta nada el botón no tendría qué cubrir. */
  get transferGapQuick() {
    const modal = this.state.modal;
    const figures = this.circuitFiguresOf(modal.to_allocation_id, modal.kind);
    const gap = circuitGap(figures, this.currency);
    return gap > 0 && gap < modal.maximum - AMOUNT_EPSILON ? gap : 0;
  }

  get transferGapQuickLabel() {
    return _t("Cubrir %s", this.fmt(this.transferGapQuick));
  }

  setTransferGap() {
    const modal = this.state.modal;
    modal.raw_amount = rawAmount(this.transferGapQuick);
    this.syncTransfer();
  }

  get transferIsNoop() {
    const modal = this.state.modal;
    return (
      Boolean(modal.to_allocation_id) &&
      modal.source_allocation_id === modal.to_allocation_id &&
      modal.source_kind === modal.kind
    );
  }

  get transferValid() {
    const modal = this.state.modal;
    if (modal.to_allocation_id && !modal.kind) {
      return false;
    }
    if (this.transferIsNoop) {
      return false;
    }
    return this.transferIsUnify || !modal.error;
  }

  onTransferAmountInput(ev) {
    const modal = this.state.modal;
    modal.raw_amount = ev.target.value;
    this.syncTransfer();
  }

  setTransferQuick(ratio) {
    const modal = this.state.modal;
    modal.raw_amount = rawAmount(roundAmount(modal.maximum * ratio, this.currency));
    this.syncTransfer();
  }

  setTransferMode(unify) {
    this.state.modal.unify = unify;
    this.syncTransfer();
  }

  syncTransfer() {
    const modal = this.state.modal;
    if (this.transferIsUnify) {
      modal.amount = modal.maximum;
      modal.error = "";
    } else {
      const check = validateTransferAmount(modal.raw_amount, modal.maximum);
      modal.amount = check.amount;
      modal.error = check.error;
    }
    this.schedulePreview(() => this.loadTransferPreview());
  }

  async loadTransferPreview() {
    const modal = this.state.modal;
    if (!modal || modal.type !== "transfer" || !this.transferValid) {
      if (modal) {
        modal.preview = [];
      }
      return;
    }
    modal.previewLoading = true;
    try {
      modal.preview = await this.orm.call(BOARD_MODEL, "preview_proposal_transfer", [
        this.sheetId,
        modal.value_id,
        modal.value_id ? null : modal.voucher_id,
        modal.to_allocation_id,
        modal.kind || null,
        modal.amount,
        this.transferIsUnify,
      ]);
    } catch (error) {
      modal.preview = [];
      this.notifyError(error);
    } finally {
      modal.previewLoading = false;
    }
  }

  async confirmTransfer() {
    const modal = this.state.modal;
    const unify = this.transferIsUnify;
    const done = await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_transfer", [
          this.sheetId,
          modal.value_id,
          modal.value_id ? null : modal.voucher_id,
          modal.to_allocation_id,
          modal.kind || null,
          modal.amount,
          unify,
        ]),
      _t("Tablero actualizado.")
    );
    if (done) {
      this.closeModal();
    }
  }

  // ----------------------------------------------------------------
  // Circuit modal
  // ----------------------------------------------------------------

  openCircuit(card, column) {
    this.closeMenu();
    this.state.modal = {
      type: "circuit",
      value_id: card.value_id,
      voucher_id: card.voucher_id,
      method: card.method,
      reference: card.reference,
      amount: card.amount,
      allocation_id: column.allocation_id,
      partner_name: column.partner_name,
      source_kind: card.document_kind,
      kind: "",
      preview: [],
      previewLoading: false,
    };
  }

  async setCircuitKind(kind) {
    const modal = this.state.modal;
    modal.kind = kind;
    modal.previewLoading = true;
    try {
      modal.preview = await this.orm.call(BOARD_MODEL, "preview_proposal_circuit", [
        this.sheetId,
        modal.value_id,
        kind,
      ]);
    } catch (error) {
      modal.preview = [];
      this.notifyError(error);
    } finally {
      modal.previewLoading = false;
    }
  }

  async confirmCircuit() {
    const modal = this.state.modal;
    const done = await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_set_circuit", [
          this.sheetId,
          modal.value_id,
          modal.kind,
        ]),
      _t("Circuito actualizado.")
    );
    if (done) {
      this.closeModal();
    }
  }

  // ----------------------------------------------------------------
  // Undo split modal
  // ----------------------------------------------------------------

  openUndoSplit(card) {
    this.closeMenu();
    const parts = this.cardsOfVoucher(card.voucher_id);
    this.state.modal = {
      type: "undo",
      voucher_id: card.voucher_id,
      method: card.method,
      reference: card.reference,
      parts,
      keep_value_id: card.value_id,
      preview: [],
      previewLoading: false,
    };
    this.loadUndoPreview();
  }

  get undoTotal() {
    return this.state.modal.parts.reduce((total, part) => total + part.amount, 0);
  }

  async setUndoKeep(valueId) {
    this.state.modal.keep_value_id = valueId;
    await this.loadUndoPreview();
  }

  async loadUndoPreview() {
    const modal = this.state.modal;
    modal.previewLoading = true;
    try {
      modal.preview = await this.orm.call(BOARD_MODEL, "preview_proposal_undo_split", [
        this.sheetId,
        modal.voucher_id,
        modal.keep_value_id,
      ]);
    } catch (error) {
      modal.preview = [];
      this.notifyError(error);
    } finally {
      modal.previewLoading = false;
    }
  }

  async confirmUndoSplit() {
    const modal = this.state.modal;
    const done = await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_undo_split", [
          this.sheetId,
          modal.voucher_id,
          modal.keep_value_id,
        ]),
      _t("División deshecha.")
    );
    if (done) {
      this.state.isolate = null;
      this.closeModal();
    }
  }

  // ----------------------------------------------------------------
  // Reset: every assignable card back to Sin asignar
  // ----------------------------------------------------------------

  /* El resumen sale del payload que el tablero ya tiene — reiniciar no
     necesita una previsualización FIFO porque su resultado no depende de
     ninguna: todo circuito queda en cero. */
  get resetSummary() {
    return resetSummary(this.state.board);
  }

  /* Un cliente cerrado está congelado, y el servidor rechaza el reinicio
     entero antes que dejar el pool sin lo que el botón prometió. El tablero
     lo dice antes de pedir la confirmación, con los nombres a reabrir. */
  get resetBlockers() {
    return resetBlockers(this.state.board);
  }

  get canReset() {
    return this.editable && this.resetSummary.cards > 0;
  }

  openReset() {
    this.closeMenu();
    if (!this.canReset) {
      return;
    }
    this.state.modal = {type: "reset"};
  }

  async confirmReset() {
    const done = await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_reset_vouchers", [this.sheetId]),
      _t("Comprobantes devueltos a Sin asignar.")
    );
    if (done) {
      this.state.isolate = null;
      this.closeModal();
    }
  }

  // ----------------------------------------------------------------
  // The expanded circuit: one circuit of one customer, with its imputation
  // ----------------------------------------------------------------

  /* Any number of circuits stay expanded at once: comparing what one customer
     owes on two circuits, or the same circuit across customers, is the whole
     job — so each grid owns its own entry and closing one leaves the rest. */
  openDetail(allocationId, kind) {
    this.closeMenu();
    if (!this.columnById(allocationId) || !CIRCUIT_KEYS.includes(kind)) {
      return;
    }
    if (this.isDetailOpen(allocationId, kind)) {
      return;
    }
    const detail = {
      allocation_id: allocationId,
      kind,
      budget: 0,
      rows: [],
    };
    this.state.details = [...this.state.details, detail];
    this.syncDetail(detail);
  }

  closeDetail(allocationId, kind) {
    this.state.details = this.state.details.filter(
      (detail) => detail.allocation_id !== allocationId || detail.kind !== kind
    );
  }

  closeAllDetails() {
    this.state.details = [];
  }

  toggleDetail(allocationId, kind) {
    if (this.isDetailOpen(allocationId, kind)) {
      this.closeDetail(allocationId, kind);
      return;
    }
    this.openDetail(allocationId, kind);
  }

  detailOf(allocationId, kind) {
    return (
      this.state.details.find(
        (detail) => detail.allocation_id === allocationId && detail.kind === kind
      ) || null
    );
  }

  isDetailOpen(allocationId, kind) {
    return Boolean(this.detailOf(allocationId, kind));
  }

  detailColumn(detail) {
    return detail ? this.columnById(detail.allocation_id) : null;
  }

  /* The server is the only truth for the imputation grid: every mutation
     redistributes the circuit by FIFO, so local edits are rebuilt from the
     refreshed payload rather than merged into it. */
  syncDetails() {
    this.state.details = this.state.details.filter((detail) =>
      Boolean(this.columnById(detail.allocation_id))
    );
    for (const detail of this.state.details) {
      this.syncDetail(detail);
    }
  }

  syncDetail(detail) {
    const column = this.columnById(detail.allocation_id);
    if (!column) {
      return;
    }
    detail.budget = column.circuits[detail.kind].collected;
    detail.rows = column.documents[detail.kind].map((row) => ({
      line_id: row.line_id,
      number: row.number,
      issue_date: row.issue_date,
      due_date: row.due_date,
      amount: row.amount,
      balance: row.balance,
      applied: row.applied,
      raw: rawAmount(row.applied),
    }));
  }

  imputeLocked(detail) {
    const column = this.detailColumn(detail);
    return Boolean(!this.editable || !column || column.closed || this.state.busy);
  }

  imputeCanConfirm(detail) {
    return Boolean(
      detail &&
        detail.rows.length &&
        !this.imputeLocked(detail) &&
        !this.imputeIsOver(detail)
    );
  }

  onImputeInput(ev, row) {
    row.raw = ev.target.value;
    const parsed = parseAmount(ev.target.value);
    row.applied = Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  }

  imputeRowAmount(row) {
    return row.applied;
  }

  imputeRows(detail) {
    return detail ? detail.rows : [];
  }

  imputeApplied(detail) {
    return this.imputeRows(detail).reduce(
      (total, row) => total + this.imputeRowAmount(row),
      0
    );
  }

  imputeAvailable(detail) {
    return (detail ? detail.budget : 0) - this.imputeApplied(detail);
  }

  imputePending(detail) {
    return this.imputeRows(detail).reduce(
      (total, row) => total + Math.max(row.balance - this.imputeRowAmount(row), 0),
      0
    );
  }

  imputeRowIsOver(row) {
    return this.imputeRowAmount(row) > row.balance + AMOUNT_EPSILON;
  }

  imputeIsOver(detail) {
    return (
      this.imputeAvailable(detail) < -AMOUNT_EPSILON ||
      this.imputeRows(detail).some((row) => this.imputeRowIsOver(row))
    );
  }

  async autoDistribute(detail) {
    try {
      const preview = await this.orm.call(BOARD_MODEL, "preview_proposal_impute", [
        this.sheetId,
        detail.allocation_id,
        detail.kind,
      ]);
      const changes = new Map(
        (preview.changes || []).map((change) => [change.line_id, change.to])
      );
      /* `confirmImpute` posts `row.applied`, and repintar el input no dispara
         ningún evento `input`: si sólo escribiéramos `raw`, la grilla mostraría
         el reparto nuevo y el servidor recibiría el viejo. */
      for (const row of detail.rows) {
        if (changes.has(row.line_id)) {
          const applied = changes.get(row.line_id);
          row.applied = applied;
          row.raw = rawAmount(applied);
        }
      }
      this.notification.add(_t("Cobrado distribuido desde la deuda más antigua."), {
        type: "success",
      });
    } catch (error) {
      this.notifyError(error);
    }
  }

  async confirmImpute(detail) {
    await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_impute", [
          this.sheetId,
          detail.allocation_id,
          detail.kind,
          detail.rows.map((row) => ({
            line_id: row.line_id,
            amount: this.imputeRowAmount(row),
          })),
        ]),
      _t("Imputación confirmada.")
    );
  }

  // ----------------------------------------------------------------
  // Close / reopen
  // ----------------------------------------------------------------

  openClose(allocationId) {
    const column = this.columnById(allocationId);
    if (!column) {
      return;
    }
    this.state.modal = {
      type: "close",
      allocation_id: allocationId,
      partner_name: column.partner_name,
      column,
      note: "",
    };
  }

  get closeDifferences() {
    const column = this.state.modal.column;
    const rows = [];
    for (const kind of CIRCUIT_KEYS) {
      const figures = column.circuits[kind];
      const circuit = CIRCUITS[kind];
      if (figures.available > AMOUNT_EPSILON) {
        rows.push({
          label: _t("Cobrado a %s sin imputar", circuit.noun),
          amount: figures.available,
          tone: "fav",
        });
      } else if (figures.available < -AMOUNT_EPSILON) {
        rows.push({
          label: _t("Imputado a %s por encima del cobro", circuit.noun),
          amount: -figures.available,
          tone: "neg",
        });
      }
      if (figures.pending > AMOUNT_EPSILON) {
        rows.push({
          label:
            kind === "invoice"
              ? _t("Facturas sin cubrir")
              : _t("Presupuestos sin conciliar"),
          amount: figures.pending,
          tone: kind === "invoice" ? "neg" : "",
        });
      }
    }
    return rows;
  }

  get closeIsBlocked() {
    return this.closeDifferences.length > 0 && this.state.modal.note.trim().length < 4;
  }

  onCloseNoteInput(ev) {
    this.state.modal.note = ev.target.value;
  }

  async confirmClose() {
    const modal = this.state.modal;
    const done = await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_close_customer", [
          this.sheetId,
          modal.allocation_id,
          modal.note,
        ]),
      _t("Cliente cerrado en la planilla.")
    );
    if (done) {
      this.closeModal();
    }
  }

  async reopenCustomer(allocationId) {
    await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_reopen_customer", [
          this.sheetId,
          allocationId,
        ]),
      _t("Cliente reabierto.")
    );
  }

  // ----------------------------------------------------------------
  // Drawer
  // ----------------------------------------------------------------

  openDrawer(allocationId, tab) {
    this.closeMenu();
    this.state.drawer = {allocation_id: allocationId, tab: tab || "conc"};
  }

  setDrawerTab(tab) {
    this.state.drawer.tab = tab;
  }

  closeDrawer() {
    this.state.drawer = null;
  }

  get drawerColumn() {
    return this.state.drawer ? this.columnById(this.state.drawer.allocation_id) : null;
  }

  get drawerEvents() {
    const drawer = this.state.drawer;
    if (!drawer) {
      return [];
    }
    return this.events.filter(
      (event) => !event.allocation_id || event.allocation_id === drawer.allocation_id
    );
  }

  drawerTotals(column) {
    const totals = columnTotals(column, CIRCUIT_KEYS);
    return {
      collected: totals.collected,
      debt: totals.total,
      ...coverageOf(totals.collected, totals.total),
    };
  }

  // ----------------------------------------------------------------
  // Modal plumbing
  // ----------------------------------------------------------------

  closeModal() {
    this.clearPreviewTimer();
    this.state.modal = null;
  }

  onOverlayClick(ev) {
    if (ev.target === ev.currentTarget) {
      this.closeModal();
    }
  }

  onEscape() {
    if (this.state.menu || this.state.modal || this.state.drawer) {
      this.closeMenu();
      this.closeModal();
      this.closeDrawer();
      return;
    }
    this.closeAllDetails();
  }

  schedulePreview(callback) {
    this.clearPreviewTimer();
    this.previewTimer = window.setTimeout(callback, PREVIEW_DEBOUNCE_MS);
  }

  clearPreviewTimer() {
    if (this.previewTimer) {
      window.clearTimeout(this.previewTimer);
      this.previewTimer = null;
    }
  }
}

registry
  .category("actions")
  .add("collection_receipt_proposal.receipt_proposal", ReceiptProposalAction);
