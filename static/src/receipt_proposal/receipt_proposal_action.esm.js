/** @odoo-module **/

import {
  BOARD_MODEL,
  CIRCUITS,
  CIRCUIT_KEYS,
  PREVIEW_DEBOUNCE_MS,
  cardClass,
  cardsOfVoucher,
  circuitOf,
  eventBullet,
  eventLabel,
  formatAmount,
  formatShort,
  nextIsolate,
  parseAmount,
  rpcErrorMessage,
  sanitizeBoardPayload,
  splitKind,
  statusLabel,
  transferButtonLabel,
  validateTransferAmount,
} from "@collection_receipt_proposal/receipt_proposal/receipt_proposal_helpers.esm";
import {Component, onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";

export class ReceiptProposalAction extends Component {
  static template = "collection_receipt_proposal.ReceiptProposalAction";
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
      dropTarget: null,
    });
    this.dragged = null;
    this.previewTimer = null;
    onWillStart(() => this.loadBoard());
    onWillUnmount(() => this.clearPreviewTimer());
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

  get board() {
    return this.state.board;
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
    return this.pool.reduce((total, item) => total + item.free_amount, 0);
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
    if (this.state.drawer && !columnIds.has(this.state.drawer.allocation_id)) {
      this.state.drawer = null;
    }
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

  circuitOf(documentKind) {
    return circuitOf(documentKind);
  }

  circuitTag(documentKind) {
    const circuit = circuitOf(documentKind);
    return circuit ? circuit.tag : "S/C";
  }

  circuitClass(documentKind) {
    const circuit = circuitOf(documentKind);
    return circuit ? circuit.short : "none";
  }

  cardClass(card) {
    return cardClass(card);
  }

  statusLabel(status) {
    return statusLabel(status);
  }

  eventLabel(eventType) {
    return eventLabel(eventType);
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

  splitLabel(card) {
    const kind = this.splitKind(card.voucher_id);
    if (kind === "circuito") {
      return _t("Dividido por circuito");
    }
    return _t("Dividido ×%s", this.cardsOfVoucher(card.voucher_id).length);
  }

  hasCircuit(column, kind) {
    return column.documents[kind].length > 0 || column.circuits[kind].collected !== 0;
  }

  circuitPercent(column, kind) {
    const figures = column.circuits[kind];
    if (!figures.total) {
      return 0;
    }
    return Math.min(
      Math.max(Math.round((figures.applied / figures.total) * 100), 0),
      100
    );
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
    ev.dataTransfer.effectAllowed = "move";
    ev.dataTransfer.setData("text/plain", String(card.value_id));
  }

  onPoolDragStart(ev, item) {
    if (!this.editable) {
      ev.preventDefault();
      return;
    }
    this.dragged = {voucher_id: item.voucher_id};
    ev.dataTransfer.effectAllowed = "move";
    ev.dataTransfer.setData("text/plain", `v${item.voucher_id}`);
  }

  onDragEnd() {
    this.dragged = null;
    this.state.dropTarget = null;
  }

  dropKey(column) {
    return column ? column.allocation_id : "pool";
  }

  /* The whole column is the drop target, not just the area holding cards. */
  onColumnDragOver(ev, column) {
    if (!this.dragged) {
      return;
    }
    ev.preventDefault();
    ev.dataTransfer.dropEffect = column && column.closed ? "none" : "move";
    const key = this.dropKey(column);
    if (this.state.dropTarget !== key) {
      this.state.dropTarget = key;
    }
  }

  onColumnDragLeave(ev) {
    if (!ev.currentTarget.contains(ev.relatedTarget)) {
      this.state.dropTarget = null;
    }
  }

  dropClass(column) {
    if (this.state.dropTarget !== this.dropKey(column)) {
      return "";
    }
    return column && column.closed ? "dropping-blocked" : "dropping";
  }

  onColumnDrop(ev, column) {
    ev.preventDefault();
    const dragged = this.dragged;
    this.dragged = null;
    this.state.dropTarget = null;
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
    this.openTransfer(dragged, column ? column.allocation_id : null);
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

  openTransfer(source, toAllocationId) {
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
      kind: "",
      amount: maximum,
      raw_amount: String(maximum),
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

  setTransferKind(kind) {
    const modal = this.state.modal;
    if (modal.kind === kind) {
      return;
    }
    modal.kind = kind;
    modal.unify = true;
    this.syncTransfer();
  }

  onTransferAmountInput(ev) {
    const modal = this.state.modal;
    modal.raw_amount = ev.target.value;
    this.syncTransfer();
  }

  setTransferQuick(ratio) {
    const modal = this.state.modal;
    modal.raw_amount = String(Math.round(modal.maximum * ratio));
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
  // Manual imputation modal
  // ----------------------------------------------------------------

  openImpute(allocationId, kind) {
    this.closeMenu();
    const column = this.columnById(allocationId);
    if (!column) {
      return;
    }
    this.state.modal = {
      type: "impute",
      allocation_id: allocationId,
      partner_name: column.partner_name,
      partner_vat: column.partner_vat,
      kind,
      budget: column.circuits[kind].collected,
      rows: column.documents[kind].map((row) => ({
        line_id: row.line_id,
        number: row.number,
        due_date: row.due_date,
        balance: row.balance,
        amount: row.applied,
        raw: String(row.applied),
      })),
      cards: column.cards.filter((card) => card.document_kind === kind),
    };
  }

  onImputeInput(ev, row) {
    row.raw = ev.target.value;
    const parsed = parseAmount(ev.target.value);
    row.amount = Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  }

  get imputeApplied() {
    return this.state.modal.rows.reduce((total, row) => total + row.amount, 0);
  }

  get imputeAvailable() {
    return this.state.modal.budget - this.imputeApplied;
  }

  get imputePending() {
    return this.state.modal.rows.reduce(
      (total, row) => total + Math.max(row.balance - row.amount, 0),
      0
    );
  }

  imputeRowIsOver(row) {
    return row.amount > row.balance + 0.001;
  }

  get imputeIsOver() {
    return (
      this.imputeAvailable < -0.001 ||
      this.state.modal.rows.some((row) => this.imputeRowIsOver(row))
    );
  }

  async autoDistribute() {
    const modal = this.state.modal;
    try {
      const preview = await this.orm.call(BOARD_MODEL, "preview_proposal_impute", [
        this.sheetId,
        modal.allocation_id,
        modal.kind,
      ]);
      const changes = new Map(
        (preview.changes || []).map((change) => [change.line_id, change.to])
      );
      for (const row of modal.rows) {
        if (changes.has(row.line_id)) {
          row.amount = changes.get(row.line_id);
          row.raw = String(row.amount);
        }
      }
      this.notification.add(_t("Cobrado distribuido desde la deuda más antigua."), {
        type: "success",
      });
    } catch (error) {
      this.notifyError(error);
    }
  }

  async confirmImpute() {
    const modal = this.state.modal;
    const done = await this.runMutation(
      () =>
        this.orm.call(BOARD_MODEL, "action_proposal_impute", [
          this.sheetId,
          modal.allocation_id,
          modal.kind,
          modal.rows.map((row) => ({line_id: row.line_id, amount: row.amount})),
        ]),
      _t("Imputación confirmada.")
    );
    if (done) {
      this.closeModal();
    }
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
      if (figures.available > 0.001) {
        rows.push({
          label: _t("Cobrado a %s sin imputar", circuit.noun),
          amount: figures.available,
          tone: "fav",
        });
      } else if (figures.available < -0.001) {
        rows.push({
          label: _t("Imputado a %s por encima del cobro", circuit.noun),
          amount: -figures.available,
          tone: "neg",
        });
      }
      if (figures.pending > 0.001) {
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
    const invoice = column.circuits.invoice;
    const quotation = column.circuits.quotation;
    return {
      collected: invoice.collected + quotation.collected,
      applied: invoice.applied + quotation.applied,
      available: invoice.available + quotation.available,
      debt: invoice.pending,
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

  onWindowKeydown(ev) {
    if (ev.key === "Escape") {
      this.closeMenu();
      this.closeModal();
      this.closeDrawer();
    }
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
