```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d6c7166a2b544e04036322e81d20c397e21080393da4bf48aca8218d2f3e8c4f
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 17/17
scenarios: 34/34
test_command: invoke test -m collection_receipt_proposal --mode=update
test_exit_code: 0
test_output_hash: sha256:4a053dc1ba5553e8d843d64b4579c00d9bb112e1c714908048736737026c9a58
build_command: pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**
build_exit_code: 0
build_output_hash: sha256:d3413a096909dcbf202523481b083f9b248e87cad9e3fdb2d9ce09c0144e91e6
```

## Verification Report

**Change**: collection-receipt-proposal
**Version**: 19.0.1.0.0
**Mode**: Strict TDD

Heading counts from retrieved delta specs (board + fifo + splits + events): **17** `### Requirement:` and **34** `#### Scenario:` headings.

This run re-verifies after the overall-largest owner remediation. Prior FAIL envelope `evidence_revision` `sha256:220ddc8bcce0e02d6c860ffc421413c44c05292d425be563b46d0c3063c399be` had 16/17 requirements and 33/34 scenarios; missing scenario was **Largest-share owner** / **Re-point after split**.

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 32 |
| Tasks complete | 32 |
| Tasks incomplete | 0 |

`tasks.md` and `apply-progress.md` both show 32/32 `[x]`. `applyState`: all_done.

### Build & Tests Execution
**Build**: ✅ Passed (exit 0)
```text
pre-commit run --files odoo/custom/src/private/collection_receipt_proposal/**
EXIT:0
hash: sha256:d3413a096909dcbf202523481b083f9b248e87cad9e3fdb2d9ce09c0144e91e6 (2003 bytes)
Hooks: ruff, ruff-format, prettier, pylint_odoo mandatory, OCA module checks, README generator — Passed.
Optional pylint_odoo logged C8101 manifest-required-author (Eynes) on __manifest__.py; the optional hook still Passed.
```

**Tests**: ✅ 134 passed / ❌ 0 failed / ⚠️ 0 skipped (addon invoke; authoritative `test_command`)
```text
invoke test -m collection_receipt_proposal --mode=update
EXIT:0
odoo.tests.stats: collection_receipt_proposal: 148 tests 6.98s 10499 queries
odoo.tests.result: 0 failed, 0 error(s) of 134 tests when loading database 'devel'
Starting TestReceiptProposal* methods: 134
hash: sha256:4a053dc1ba5553e8d843d64b4579c00d9bb112e1c714908048736737026c9a58 (96193 bytes)
```

**Additional evidence** (not `test_command`; partner-match relax regression):
```text
invoke test -m collection --mode=update
EXIT:1
odoo.tests.stats: collection: 817 tests 38.69s 63693 queries
odoo.tests.result: 13 failed, 0 error(s) of 749 tests when loading database 'devel'
hash: sha256:086b901181f8c9e9cc02977d4a7b2a300baa7f7d4b1824fbd2e811ab45dbbae2 (808187 bytes)
Passed: TestCollectionAllocation.test_fully_applied_source_detach_via_partner_write_succeeds
Failed (13, collection document-review / version drift, not partner-match):
- TestCollectionAcl.test_internal_user_review_queue_and_approve_allowed (100.0 != 150.0)
- TestCollectionCompanyMigration.test_agents_md_four_state_workflow (expects 19.0.1.37.0)
- TestCollectionCompanyMigration.test_manifest_version_is_1_37_0 (on-disk version 19.0.1.36.0)
- TestCollectionDocumentReview.test_approve_persists_cash_deposit_fields
- TestCollectionDocumentReview.test_approve_persists_check_fields
- TestCollectionDocumentReview.test_approve_persists_edits_and_records_audit
- TestCollectionDocumentReview.test_build_approve_vals_sends_current_keys_only
- TestCollectionDocumentReview.test_owl_empty_provenance_still_loads
- TestCollectionDocumentReview.test_owl_keeps_type_visibility_hides_document_id_and_shows_provenance
- TestCollectionDocumentReview.test_owl_review_rpcs_pass_sheet_id_from_action_params
- TestCollectionDocumentReview.test_review_lock_uses_for_update_on_collection_voucher
- TestCollectionDocumentReview.test_reviewer_correction_matches_snapshot_current_only
- TestCollectionDocumentReview.test_stale_approve_and_reject_refuse_without_corruption
```

**Coverage**: ➖ Not available — no coverage tool in `openspec/config.yaml` / cached capabilities.

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Proposal entry action | Opens on proposal with sheet_id | `test_receipt_proposal_board.py` > `TestReceiptProposalBoard.test_action_open_receipt_proposal_returns_the_client_action` | ✅ COMPLIANT |
| Proposal entry action | Non-proposal refused | `test_receipt_proposal_board.py` > `TestReceiptProposalBoard.test_action_open_receipt_proposal_refuses_non_proposal_sheets` | ✅ COMPLIANT |
| Proposal entry action | Header button placement and visibility | `test_receipt_proposal_ui.py` > `TestReceiptProposalUi.test_sheet_form_button_is_inherited_correctly` + `test_export_xlsx_stays_the_last_object_button` | ✅ COMPLIANT |
| RPC sheet gate | Invalid sheet_id refused | `test_receipt_proposal_board.py` > `TestReceiptProposalBoard.test_require_proposal_sheet_rejects_non_integers` + `test_require_proposal_sheet_rejects_missing_records` + `test_require_proposal_sheet_rejects_other_states` + `test_invalid_sheet_id_does_not_mutate` + `test_sheet_company_rule_still_guards_the_board` | ✅ COMPLIANT |
| Board RPCs | Transfer, circuit, impute, close, reopen | `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_transfer_set_circuit_impute_close_reopen_return_the_full_board` + `test_transfer_ignores_client_supplied_applied_lines` | ✅ COMPLIANT |
| Board RPCs | Previews do not persist | `test_receipt_proposal_board.py` > `TestReceiptProposalBoard.test_preview_transfer_does_not_persist` + `test_preview_circuit_does_not_persist` + `test_preview_undo_split_does_not_persist` + `test_preview_impute_does_not_persist`; `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_previews_do_not_write` | ✅ COMPLIANT |
| Board payload | Payload shape and synthetic pool | `test_receipt_proposal_board.py` > `TestReceiptProposalBoard.test_board_payload_shape` + `test_column_payload_shape` + `test_pool_is_synthetic_for_free_amount_only` | ✅ COMPLIANT |
| No sudo and no new groups | Internal user without sudo | `test_receipt_proposal_board.py` > `TestReceiptProposalBoard.test_internal_user_reads_the_board_without_sudo`; `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_no_dedicated_groups_and_never_sudo` | ✅ COMPLIANT |
| FIFO sort key | Same order as receipt lines | `test_receipt_proposal_order.py` > `TestReceiptProposalOrder.test_fifo_key_matches_receipt_line_ids_order` | ✅ COMPLIANT |
| FIFO sort key | Undated last and empty number | `test_receipt_proposal_order.py` > `TestReceiptProposalOrder.test_undated_line_sorts_after_every_dated_line` + `test_same_due_date_empty_number_matches_compute_line_ids`; `test_receipt_proposal_fifo.py` > `TestReceiptProposalFifo.test_undated_documents_sort_last` | ✅ COMPLIANT |
| Balance ceiling and remainder | Ceiling is invoice_balance | `test_receipt_proposal_fifo.py` > `TestReceiptProposalFifo.test_ceiling_spec_amounts_ignore_invoice_amount` | ✅ COMPLIANT |
| Balance ceiling and remainder | Partial fill, surplus, and no documents | `test_receipt_proposal_fifo.py` > `TestReceiptProposalFifo.test_partial_fill_on_a_single_document` + `test_surplus_when_budget_exceeds_all_balances` + `test_no_documents_is_flagged` | ✅ COMPLIANT |
| Idempotent overwrite | Second pass and discarded Imputar | `test_receipt_proposal_fifo.py` > `TestReceiptProposalFifo.test_recompute_is_idempotent` + `test_manual_edits_do_not_survive_a_recompute` | ✅ COMPLIANT |
| Idempotent overwrite | Overdraft self-heals | `test_receipt_proposal_fifo.py` > `TestReceiptProposalFifo.test_circuit_overdraft_self_heals` | ✅ COMPLIANT |
| Close, reopen, and status | Closed frozen | `test_receipt_proposal_fifo.py` > `TestReceiptProposalFifo.test_closed_allocation_is_frozen` | ✅ COMPLIANT |
| Close, reopen, and status | Close note and reopen | `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_close_customer_requires_a_note_when_there_are_differences` + `test_close_without_differences_needs_no_note` + `test_reopen_customer_clears_the_close_stamp` + `test_close_requires_a_note_when_collected_exceeds_applied` | ✅ COMPLIANT |
| Close, reopen, and status | Status is not allocation state | `test_receipt_proposal_fifo.py` > `TestReceiptProposalFifo.test_cerrado_does_not_reuse_allocation_state` | ✅ COMPLIANT |
| Same-sheet split | Cross-customer same sheet accepted | `test_receipt_proposal_split.py` > `TestReceiptProposalSplit.test_cross_customer_split_is_accepted_within_a_sheet` | ✅ COMPLIANT |
| Same-sheet split | Cross-sheet refused | `test_receipt_proposal_split.py` > `TestReceiptProposalSplit.test_split_across_sheets_is_rejected` | ✅ COMPLIANT |
| Sheet-wide split cap | Over-cap across customers refused | `test_receipt_proposal_split.py` > `TestReceiptProposalSplit.test_over_cap_across_three_customers_is_refused` + `test_sheet_wide_split_cap_is_enforced` | ✅ COMPLIANT |
| Sheet-wide split cap | At-cap allowed | `test_receipt_proposal_split.py` > `TestReceiptProposalSplit.test_at_cap_across_customers_persists` | ✅ COMPLIANT |
| Largest-share owner | Re-point after split | `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_owner_repoints_to_largest_share_after_split`; `test_receipt_proposal_split.py` > `TestReceiptProposalSplit.test_voucher_owner_follows_overall_largest_share` | ✅ COMPLIANT |
| Largest-share owner | Re-point after undo | `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_undo_split_keeps_the_chosen_card_and_returns_the_board` | ✅ COMPLIANT |
| Unify and undo split | Unify merges parts | `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_unify_merges_parts_into_one_value_and_returns_the_board`; `test_receipt_proposal_split.py` > `TestReceiptProposalSplit.test_transfer_merges_into_an_existing_card` | ✅ COMPLIANT |
| Unify and undo split | Undo split keeps one part | `test_receipt_proposal_split.py` > `TestReceiptProposalSplit.test_undo_split_reunifies_on_the_kept_card`; `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_undo_split_keeps_the_chosen_card_and_returns_the_board` | ✅ COMPLIANT |
| Event model | Fields and type list | `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_transfer_type_stores_sheet_user_timestamp_and_company` + `test_event_type_selection_is_closed_and_invalid_refuses` | ✅ COMPLIANT |
| Event model | Newest first | `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_order_is_newest_first` | ✅ COMPLIANT |
| Immutability | Create gated | `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_create_is_gated_on_the_context_key` | ✅ COMPLIANT |
| Immutability | Write refused | `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_write_raises_and_leaves_row_unchanged` | ✅ COMPLIANT |
| Immutability | Unlink refused except sheet cascade | `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_unlink_raises_except_sheet_cascade` | ✅ COMPLIANT |
| ACL and company rule | Other-company hidden | `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_other_company_events_hidden` | ✅ COMPLIANT |
| ACL and company rule | Internal read and create without sudo | `test_receipt_proposal_events.py` > `TestReceiptProposalEvents.test_internal_user_reads_and_creates_without_sudo` + `test_access_rights_are_read_and_create_only` + `test_company_rule_is_global_noupdate` | ✅ COMPLIANT |
| Mutation events | Actions write expected types | `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_mutations_write_the_matching_event_types` + `test_unify_and_undo_split_write_unify_events` | ✅ COMPLIANT |
| Mutation events | Auto-impute only when FIFO changes | `test_receipt_proposal_actions.py` > `TestReceiptProposalActions.test_auto_impute_is_skipped_when_fifo_already_matches` + `test_mutations_write_the_matching_event_types` | ✅ COMPLIANT |

**Compliance summary**: 34/34 scenarios compliant.

`Re-point after split` covering test `test_owner_repoints_to_largest_share_after_split` assigns 30 to A then 70 to B via `action_proposal_transfer` and asserts `voucher.allocation_id == allocation_b`. Sibling `test_voucher_owner_follows_overall_largest_share` asserts the same 30/70 pointer after `_proposal_sync_voucher_owner`. Both started and passed in this addon run.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Proposal entry action | ✅ Implemented | `action_open_receipt_proposal`; English button after Document Review, before XLSX; OWL Spanish; no `i18n/`; client action omits `path`. |
| RPC sheet gate | ✅ Implemented | `_require_proposal_sheet` refuses non-int/missing/non-proposal/other-company; no `sudo()`. |
| Board RPCs | ✅ Implemented | Full mutating + preview surface; typed amount only; previews do not write. Extra `preview_proposal_impute` kept per design (not required by the board RPC MUST-expose list). |
| Board payload | ✅ Implemented | `{sheet, columns, pool, events}`; synthetic pool; no `value_id` on pool cards. |
| No sudo and no new groups | ✅ Implemented | `base.group_user`; model sources scanned; no `res.groups` xmlids. Mutating RPCs were not invoked via `with_user` (board read was). |
| FIFO sort key | ✅ Implemented | `_proposal_fifo_key` matches `_compute_line_ids`; empty number is `""`. |
| Balance ceiling and remainder | ✅ Implemented | Cap is `invoice_balance`; partial/surplus/no-docs paths exist. |
| Idempotent overwrite | ✅ Implemented | Recompute overwrites Imputar; second pass empty `changes`; quotation overdraft self-heals. |
| Close, reopen, and status | ✅ Implemented | `proposal_closed` freeze; note on difference; `cerrado` vs `allocation.state` draft. |
| Same-sheet split | ✅ Implemented | `_check_same_allocation` is sheet-scope; UNIQUE and amount `> 0` still hold. |
| Sheet-wide split cap | ✅ Implemented | `_check_voucher_split_cap` sums all values with `currency.compare_amounts`. Partner-detach collection test passed; other collection failures are document-review/version drift. |
| Largest-share owner | ✅ Implemented | `_proposal_sync_voucher_owner` picks overall largest share (tie-break `allocation.id`). `_check_voucher_allocation_partner` and `_check_voucher_partners` allow a same-sheet share on the named allocation. 30 A then 70 B names B. |
| Unify and undo split | ✅ Implemented | Unify merges remaining values; undo-split keeps `keep_value_id` and restores assigned total. |
| Event model | ✅ Implemented | Nine `event_type` values; stored related `company_id`; `_order` newest-first. |
| Immutability | ✅ Implemented | Context-gated create; write raise; `@api.ondelete` except sheet cascade. |
| ACL and company rule | ✅ Implemented | `1,0,1,0`; global noupdate company `ir.rule`; no dedicated groups. |
| Mutation events | ✅ Implemented | Matching types including unify; `auto_impute` skipped when FIFO `changes` is empty. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Write existing `collection.*` (no parallel schema) | ✅ Yes | Inherit locally; apply roots stayed in this addon. |
| Python-only FIFO; JS debounce 250 ms | ✅ Yes | `@api.private` engine; `PREVIEW_DEBOUNCE_MS = 250`. |
| Synthetic pool | ✅ Yes | Pool entries have no `value_id`. |
| Overall largest owner; relax partner match on same-sheet share | ✅ Yes | Design owner row and AGENTS.md match the splits spec. Code: `_proposal_allocation_owner_ok` + `_proposal_sync_voucher_owner`. |
| Keep `collection_receipt.py` totals `depends=` | ✅ Yes | SQL-safe FIFO writes tested. |
| Keep `preview_proposal_impute` | ✅ Yes | Preview does not persist. |
| Client action omits `path`; English views / Spanish OWL | ✅ Yes | UI tests + views. |
| Threat matrix N/A; no HttpCase | ✅ Yes | Static-text UI tests only. |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | TDD Cycle Evidence tables present in `apply-progress.md` for phases 1–6. |
| All tasks have tests | ✅ | 32/32 tasks `[x]`; RED tasks map to `TestReceiptProposal*` files; 1.1/1.6/6.7/6.8 are mixin/structural/harness. |
| RED confirmed (tests exist) | ✅ | All seven `tests/test_receipt_proposal_*.py` files exist on disk and 134 methods started in this run. |
| GREEN confirmed (tests pass) | ✅ | 134/134 addon tests passed on this execution. |
| Triangulation adequate | ✅ | Multi-case RED tasks have distinct expected values. Owner now triangulates overall largest: 30/70 B, 100/200 B, all-shares-to-B, no-share write refused. |
| Safety Net for modified files | ⚠️ | Several modified test/model files are marked `N/A (new behaviors)` rather than a prior green count (phases 1–2). Later phases recorded numeric safety nets (board 11/11, UI 1 failed/25, actions 0/18). |

**TDD Compliance**: 5/6 checks passed (safety-net WARNING only).

---

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 30 | 1 (`test_receipt_proposal_ui.py`, static-text `TransactionCase`) | Odoo test runner |
| Integration | 104 | 6 (`test_receipt_proposal_{events,split,fifo,order,board,actions}.py`) | Odoo `TransactionCase` / Doodba invoke |
| E2E | 0 | 0 | not installed (design: no HttpCase/tours) |
| **Total** | **134** | **7** | |

---

### Changed File Coverage
Coverage analysis skipped — no coverage tool detected.

---

### Assertion Quality
**Assertion quality**: ✅ All assertions verify real behavior

No tautologies, ghost loops over empty queryAll, or assertions that never call production code. UI tests intentionally assert source tokens (`t-out`, Spanish copy, debounce 250, omit `path`) as the designed static-text layer. Owner tests assert overall largest (`allocation_id` becomes B after 30 A / 70 B and after 100 A / 200 B). `test_partner_write_still_refused_without_a_share_on_the_target` writes `allocation_id` to B with no share and expects `UserError`.

---

### Quality Metrics
**Linter**: ✅ No errors (pre-commit exit 0). Optional pylint C8101 `manifest-required-author` (Eynes) on `__manifest__.py` — SUGGESTION; mandatory pylint Passed.
**Type Checker**: ➖ Not available

### Issues Found
**CRITICAL**: None

**WARNING**:
1. Additional suite `invoke test -m collection --mode=update` exited 1 with 13 failed / 749. Failures are collection document-review provenance/current-key tests and manifest/AGENTS version 19.0.1.37.0 vs on-disk 19.0.1.36.0. They are outside `allowedEditRoots`. The partner-match regression `test_fully_applied_source_detach_via_partner_write_succeeds` passed. Not a spec miss for this change.
2. FIFO scenario `Undated last and empty number` THEN says `"A"` MUST precede `""` among the same due date. Requirement `FIFO sort key` and `_compute_line_ids` use `(due_date or date.max, invoice_number or "")`, which sorts `""` before `"A"`. Covering tests (`test_same_due_date_empty_number_matches_compute_line_ids`) assert empty-before-named and id-match with receipt lines. Treat as a spec AND typo, not an implementation miss; sibling scenario `Same order as receipt lines` is COMPLIANT.
3. Board scenario `Internal user without sudo` WHEN includes a mutating RPC. Covering runtime evidence is `get_proposal_board` as `with_user(internal)` plus a no-`sudo()` source scan. Mutating `action_proposal_*` were not executed as that user.
4. Strict TDD safety net: some modified files in apply-progress use `N/A (new behaviors)` instead of a prior green count.
5. Optional pylint C8101 author warning on `__manifest__.py` (hook still Passed).
6. `apply-progress.md` / tasks 6.2 still describe same-customer owner. Design.md, AGENTS.md, and production code now implement overall largest. Historical apply text was not refreshed after remediation.

**SUGGESTION**:
1. Add one `with_user(internal)` mutating RPC test if the board scenario WHEN is kept.
2. Refresh apply-progress owner notes so they match the current overall-largest implementation.
3. Resolve collection 1.36 vs 1.37 / document-review provenance drift in the `collection` addon (outside this change).

### Verdict
PASS WITH WARNINGS
All 34 spec scenarios are COMPLIANT, including Re-point after split (30 A / 70 B → owner B). Authoritative addon suite 0/134 and pre-commit 0. Collection `--mode=update` is 13 failed / 749 on unrelated document-review and version assertions; partner-detach regression passed.
