# MyIDM Bot Phased Restructure Blueprint

## 1. Build Order Justification and Phase Plan

### Why This Exact 6-Phase Order

The monolith (`bot.py`, 6,088 lines) is extracted strictly **bottom-up along the topological DAG** defined in `docs/bot-target-architecture.md`:

1. **Foundation first (Phase 1: `L0` and `L1`)**: `config`, `state`, `texts`, `db`, and `utils` have zero dependencies on upper bot logic. Moving them first establishes the canonical homes for `cfg.DB_FILE`, `state.ACTIVE_TASKS`, `state.request_queue`, and `texts.TEXTS`, and introduces the automated contract-parity suite (`tests/test_contract_parity.py`) before any pipeline code moves.
2. **Upload, Validation, Clients, Keyboards, and APK Inspection second (Phase 2: `L2` and `L3b`)**: These modules depend only on Phase 1 foundations and do not call download engines or resolvers. Extracting them before downloads isolates the frozen `BLITZVERIFY v1` formatter (`apk_inspect.py`), duplicate warning formatter (`dupguard.py`), keyboards (`keyboards.py`), and `process_single_local_file_upload` / `run_approved_pending_upload` (`upload.py`).
3. **Host Resolvers, Download Engines, and Delivery Cache third (Phase 3: `L3a`, `L4`, `L5`)**: `resolvers.py`, `downloads.py` (`process_download_and_upload`, `process_torrent_download`, `process_zip_bundle`, `download_multi_stream_turbo`, `download_video_or_m3u8`), and `fwdcache.py` sit cleanly on top of Phases 1 and 2.
4. **Commands, Callbacks, and Message Intake fourth (Phase 4: `L6a`, `L6b`, `L6c`)**: All 20 Pyrogram handlers and `queue_worker` move into `commands.py`, `callbacks.py`, and `intake.py` with explicit, deterministic registration order (`commands` -> `callbacks` -> `intake`).
5. **Web Dashboard fifth (Phase 5: `L6d`)**: `dashboard.py` (`handle_health_check`, `handle_dashboard_view`, `handle_dashboard_stats_api`, `handle_dashboard_cancel_task_api`, `start_web_server`) extracts cleanly and re-points `tests/test_dashoff.py`.
6. **Lifecycle Entrypoint, Final Test Re-Pointing, and Docker Shape sixth (Phase 6: `L7` and `L8`)**: `myidm/app.py` absorbs `cleanup_temp_dir`, `background_cleaner_worker`, `BOT_COMMANDS`, and `main()`/`run()`; `bot.py` shrinks to the ~30-line entrypoint; all 11 test files complete mechanical re-pointing to `myidm.*`.

**Self-Contained Deployability Invariant**: In Phases 1 through 5, `bot.py` imports newly extracted `myidm.*` modules at the top while keeping un-extracted functions in `bot.py`. No `myidm.*` module ever imports `bot.py`. Consequently, `python bot.py` (and `CMD ["python", "bot.py"]` in `Dockerfile`) starts and runs cleanly at the close of every single phase without waiting for any later phase.

*(All `bot.py` line ranges cited below refer to the Phase 0 baseline file of 6,088 lines, MD5 `1551B1FD0883702B28345D0DA6D4AEA8`.)*

---

### Phase 1: Foundation Layer (Bootstrap, Config, State, Localization, Persistence, Utilities)

- **File Scope**:
  - **Created**:
    - `myidm/__init__.py` (absorbs `bot.py:1-38, 44-53, 66-81`)
    - `myidm/config.py` (absorbs `bot.py:39-43, 54-65, 82-141, 167-174, 5075`)
    - `myidm/state.py` (absorbs `bot.py:1025-1027`)
    - `myidm/texts.py` (absorbs `bot.py:175-346, 1018-1021`)
    - `myidm/db.py` (absorbs `bot.py:142-166, 347-1017, 1022-1024`)
    - `myidm/utils.py` (absorbs `bot.py:1889-2125, 2710-2716`)
    - `tests/test_contract_parity.py` (automated contract parity + DAG verifier)
  - **Edited**:
    - `bot.py`: removes moved definitions, imports `config as cfg`, `state`, `texts`, `db`, `utils` (plus transitional re-exports on `bot`), and updates remaining functions in `bot.py` to read `cfg.DB_FILE`, `cfg.DATA_DIR`, `cfg.PENDING_DIR`, `cfg.DOWNLOAD_DIR`, `cfg.DISK_MIN_FREE_GB`, `state.ACTIVE_TASKS`, `state.request_queue`, `db.DASHBOARD_SECRET`.
    - Mechanical path-override sync in tests that mutate `bot.DATA_DIR`, `bot.DB_FILE`, `bot.PENDING_DIR`, `bot.DOWNLOAD_DIR`: `tests/test_dedupguard.py`, `tests/test_dupfix.py`, `tests/test_fwdcache.py`, `tests/test_sslretry.py`, `tests/test_end_to_end_simulation.py` (pointing path mutations at `myidm.config.*` while keeping all test assertions identical).
- **What Changes**:
  - Extracts all Layer 0 and Layer 1 modules; centralizes all 24 `sqlite3.connect` calls inside `myidm/db.py` reading `cfg.DB_FILE` dynamically; ensures `init_db()` runs before `get_or_create_dashboard_secret()` so WAL mode is set first; adds `tests/test_contract_parity.py` locking SHA-256 digests of `TEXTS`, `BLITZVERIFY` fixtures, SQLite schema, commands, and callbacks.
- **What Must Not Change**:
  - Zero changes to SQLite table names, column names/types/defaults, index `idx_deliveries_user_url`, or the 12 guarded `ALTER TABLE` statements.
  - Zero byte changes to any `TEXTS["ar"]` or `TEXTS["en"]` value or key.
  - Zero changes to environment variable names, `ADMIN_IDS`, disk-check formulas, or `clean_and_rename_filename` regex rules.
- **Verification Battery (in fixed order)**:
  1. `python -m py_compile bot.py main.py myidm/*.py tests/*.py`
  2. `DATA_DIR=<isolated_tmp> python -m unittest discover tests -v` (all 56 baseline tests + new `test_contract_parity.py` tests green)
  3. `DATA_DIR=<isolated_tmp> python tests/test_end_to_end_simulation.py` (all 4 flows green)
  4. Contract checks in `test_contract_parity.py`: `BLITZVERIFY` fixture byte equality, `callback_data` set equality, command set equality, `TEXTS` key/byte equality in `ar` and `en`, fresh + legacy-migrated SQLite schema equality, and AST DAG check.
- **Risks**:
  - Stale string copy if any function does `from myidm.config import DB_FILE` instead of reading `cfg.DB_FILE`. Mitigated by AST check in `test_contract_parity.py` banning direct value imports of mutable config paths.
- **Rollback Note**:
  - Revert `bot.py` and the 5 test files to pre-Phase-1 state and remove `myidm/` and `tests/test_contract_parity.py`. Zero SQLite schema or `DATA_DIR` changes occur, so rollback is instant and lossless.

---

### Phase 2: Clients, Keyboards, Validation, Duplicate Guard, APK Inspection, and Upload Pipeline

- **File Scope**:
  - **Created**:
    - `myidm/clients.py` (absorbs `bot.py:1391-1418`)
    - `myidm/keyboards.py` (absorbs `bot.py:2126-2255, 3077-3086`)
    - `myidm/validation.py` (absorbs `bot.py:1419-1597, 5076-5133`)
    - `myidm/dupguard.py` (absorbs `bot.py:3028-3076`)
    - `myidm/apk_inspect.py` (absorbs `bot.py:2256-2709, 2717-2990, 3087-3140`)
    - `myidm/upload.py` (absorbs `bot.py:3141-3199, 4136-4425, 4936-5074`)
  - **Edited**:
    - `bot.py`: replaces moved functions with imports from `myidm.clients`, `myidm.keyboards`, `myidm.validation`, `myidm.dupguard`, `myidm.apk_inspect`, `myidm.upload` (keeping transitional re-exports on `bot.py` until Phase 6).
    - Mechanical patch-target sync in `tests/test_dupfix.py`, `tests/test_nocard.py`, `tests/test_end_to_end_simulation.py` (`patch("myidm.upload.resilient_send_media", ...)` and `patch("myidm.apk_inspect.handle_apk_inspection_card", ...)`), plus adding end-to-end local upload & duplicate-approval coverage in `tests/test_contract_parity.py`.
- **What Changes**:
  - Isolates `Client("downloader_bot")` construction, all inline keyboard builders, `progress_bar`, `safe_edit_text`, binary/HTML validation, `is_cert_verification_error`, APK/XAPK/APKS inspection, frozen `format_blitzverify_block` (and preserved test-coupled `format_apk_inspection_card`), and the local upload pipeline (`process_single_local_file_upload`, `run_approved_pending_upload`, `resilient_send_media`, `build_file_caption`, `extract_video_metadata`).
- **What Must Not Change**:
  - `format_blitzverify_block` output bytes, `format_signer_change_warning` text and `ParseMode.DISABLED`, `format_duplicate_warning_card` text, keyboard labels and `callback_data` values, `safe_edit_text` swallowing of `MessageNotModified`, Pyrogram client name `downloader_bot` and `workdir=cfg.DATA_DIR`.
- **Verification Battery (in fixed order)**:
  1. `python -m py_compile bot.py main.py myidm/*.py tests/*.py`
  2. `DATA_DIR=<isolated_tmp> python -m unittest discover tests -v`
  3. `DATA_DIR=<isolated_tmp> python tests/test_end_to_end_simulation.py`
  4. Standalone APK fixtures check: `DATA_DIR=<isolated_tmp> python tests/test_apkinspect_suite.py` and `python tests/test_real_apk_inspection.py`
  5. Contract parity checks (`BLITZVERIFY`, `callback_data`, commands, `TEXTS`, DB schema, DAG layer check).
- **Risks**:
  - `test_fwdcache.py` and `test_sslretry.py` still patch `bot.resilient_send_media` until Phase 3 moves `process_download_and_upload`. Mitigated by having un-moved `process_download_and_upload` in `bot.py` call `upload.resilient_send_media` AND re-pointing `resilient_send_media` / `inspect_apk` / `is_valid_binary_file` / `handle_apk_inspection_card` patches in `test_fwdcache.py` and `test_sslretry.py` to `myidm.*` in Phase 2 so all callers and tests agree on one target.
- **Rollback Note**:
  - Revert Phase 2 files to Phase 1 commit/tag; Phase 1 remains runnable and deployable on its own.

---

### Phase 3: Host Resolvers, Download Engines, and Delivery Cache (`fwdcache`)

- **File Scope**:
  - **Created**:
    - `myidm/resolvers.py` (absorbs `bot.py:1598-1888, 4714-4776`)
    - `myidm/downloads.py` (absorbs `bot.py:4067-4135, 4426-4713, 4777-4935, 5134-5988`)
    - `myidm/fwdcache.py` (absorbs `bot.py:2991-3027, 3574-3666`)
  - **Edited**:
    - `bot.py`: removes moved resolver, download engine, and `fwdcache` functions; imports them from `myidm.resolvers`, `myidm.downloads`, `myidm.fwdcache`.
    - Mechanical re-pointing of `tests/test_fwdcache.py` and `tests/test_sslretry.py` to `myidm.resolvers`, `myidm.downloads`, `myidm.fwdcache`, `myidm.config.CURL_CFFI_AVAILABLE`, and `myidm.config.CurlAsyncSession`; extends end-to-end tests to cover resolver dispatch, TLS cert-error single retry, and `fwdcache` hit/stale-fallback flows through the new modules.
- **What Changes**:
  - Moves all 13 host-family resolvers, `download_multi_stream_turbo`, `download_video_or_m3u8`, `process_torrent_download`, `process_zip_bundle`, `process_download_and_upload`, `handle_url_intake`, and `run_fresh_download` into single-responsibility modules using `logging.getLogger("bot.<module>")`.
- **What Must Not Change**:
  - Exact control flow inside the 854-line `process_download_and_upload` (moved intact without speculative refactoring, preserving `hop_count < 2`, 3-profile `curl_cffi` loop, `aiohttp` fallback, `curl` CLI fallback, TLS retry logging/notice, APK duplicate staging, and upload branches).
  - Exact `url_key = (url or "").strip()` fragment preservation and `is_message_not_found_error` fallback in `fwdcache.py`.
- **Verification Battery (in fixed order)**:
  1. `python -m py_compile bot.py main.py myidm/*.py tests/*.py`
  2. `DATA_DIR=<isolated_tmp> python -m unittest discover tests -v`
  3. `DATA_DIR=<isolated_tmp> python tests/test_end_to_end_simulation.py`
  4. Contract parity checks (`BLITZVERIFY`, `callback_data`, commands, `TEXTS`, DB schema, `"bot"` logger propagation, DAG layer check).
- **Risks**:
  - `self.assertLogs("bot", level="WARNING")` in `test_fwdcache.py` (`L149`) and `test_sslretry.py` (`L168, L423`) would fail if logger names do not descend from `"bot"`. Mitigated by naming module loggers `"bot.fwdcache"` and `"bot.downloads"`.
  - `patch("myidm.config.CurlAsyncSession", ...)` in `test_sslretry.py` requires `downloads.py` and `resolvers.py` to instantiate `cfg.CurlAsyncSession(...)` rather than importing `CurlAsyncSession` by value. Verified by `test_sslretry_curl_cffi_unverified_retry`.
- **Rollback Note**:
  - Revert Phase 3 edits to Phase 2 state; Phase 2 remains independently runnable and deployable.

---

### Phase 4: Command Handlers, Callback Router, and Message/Queue Intake

- **File Scope**:
  - **Created**:
    - `myidm/commands.py` (absorbs `bot.py:3200-3573`: all 17 command handlers + `register_command_handlers(bot)`)
    - `myidm/callbacks.py` (absorbs `bot.py:3667-3944`: `callback_handler` + `register_callback_handlers(bot)`)
    - `myidm/intake.py` (absorbs `bot.py:3945-4066`: `handle_document_torrent`, `handle_all_messages`, `handle_queued_task`, `queue_worker` + `register_intake_handlers(bot)`)
  - **Edited**:
    - `bot.py`: removes moved handlers and calls `register_command_handlers(bot)`, `register_callback_handlers(bot)`, `register_intake_handlers(bot)` in exact order.
    - `tests/test_dashoff.py` (`test_admin_panel_callback_keyboard` updated to inspect `myidm/callbacks.py` and scan all package files for banned dashboard buttons/commands); `tests/test_fwdcache.py` (`callback_handler` pointed to `myidm.callbacks.callback_handler`); adds handler-routing and callback end-to-end tests in `tests/test_contract_parity.py`.
- **What Changes**:
  - Replaces import-side-effect `@bot.on_message` decorators with explicit, idempotent registration functions (`register_command_handlers`, `register_callback_handlers`, `register_intake_handlers`) called in deterministic order so `handle_all_messages` is guaranteed to register last in Pyrogram group `0`.
- **What Must Not Change**:
  - All 30 command names across 17 handlers, all 22 emitted `callback_data` values + `"btn_help"` handler branch, all owner-gate checks (`cfg.is_admin`), 300-second stale message threshold (`L3974`), `[ZIP]` sentinel, magnet regex, and `URL | Name | Caption` parser.
- **Verification Battery (in fixed order)**:
  1. `python -m py_compile bot.py main.py myidm/*.py tests/*.py`
  2. `DATA_DIR=<isolated_tmp> python -m unittest discover tests -v`
  3. `DATA_DIR=<isolated_tmp> python tests/test_end_to_end_simulation.py`
  4. Contract parity checks, including explicit inspection of `clients.bot.dispatcher.groups[0]` handler count (`20` total: `19` `MessageHandler` + `1` `CallbackQueryHandler` in `groups`) and ordering (all 17 command handlers strictly precede `handle_document_torrent` and `handle_all_messages`).
- **Risks**:
  - Duplicate handler registration if `register_*_handlers` were called twice, or inverted handler order swallowing `/` commands. Mitigated by idempotency guard `_handlers_registered` and explicit `dispatcher.groups` order assertion in `test_contract_parity.py`.
- **Rollback Note**:
  - Revert Phase 4 changes to Phase 3 state; Phase 3 remains independently runnable and deployable.

---

### Phase 5: Web Health and Live Telemetry Dashboard

- **File Scope**:
  - **Created**:
    - `myidm/dashboard.py` (absorbs `bot.py:1028-1390`: `DASHBOARD_HTML_TEMPLATE`, `handle_health_check`, `handle_dashboard_view`, `handle_dashboard_stats_api`, `handle_dashboard_cancel_task_api`, `start_web_server`)
  - **Edited**:
    - `bot.py`: removes dashboard code and imports `start_web_server` from `myidm.dashboard`.
    - `tests/test_dashoff.py`: updates `test_web_server_routes_preserved` to read `myidm/dashboard.py` and `myidm/db.py`, plus adds an ephemeral `aiohttp` route test in `tests/test_contract_parity.py` exercising `GET /`, `GET /dashboard` (403 without key, 200 with key), `GET /api/dashboard/stats` (403/200), and `POST /api/dashboard/cancel` (403/200).
- **What Changes**:
  - Isolates the 362-line `aiohttp` web server and embedded HTML/JS telemetry dashboard into `myidm/dashboard.py`.
- **What Must Not Change**:
  - Route paths (`/`, `/dashboard`, `/api/dashboard/stats`, `/api/dashboard/cancel`), `DASHBOARD_SECRET` query-key gate (`403` on mismatch), JSON response keys in `handle_dashboard_stats_api`, port binding (`0.0.0.0:cfg.PORT`), and absence of any dashboard command or button in Telegram menus (`dashoff` contract).
- **Verification Battery (in fixed order)**:
  1. `python -m py_compile bot.py main.py myidm/*.py tests/*.py`
  2. `DATA_DIR=<isolated_tmp> python -m unittest discover tests -v`
  3. `DATA_DIR=<isolated_tmp> python tests/test_end_to_end_simulation.py`
  4. Contract parity checks + live ephemeral HTTP dashboard route tests.
- **Risks**:
  - `DASHBOARD_SECRET` mismatch if `dashboard.py` cached an old secret when tests re-run `get_or_create_dashboard_secret()`. Mitigated by reading `db.DASHBOARD_SECRET` dynamically.
- **Rollback Note**:
  - Revert Phase 5 changes to Phase 4 state; Phase 4 remains independently runnable and deployable.

---

### Phase 6: Application Entrypoint, Final Test Re-Pointing, and Docker Build Shape

- **File Scope**:
  - **Created**:
    - `myidm/app.py` (absorbs `bot.py:5989-6088`: `BOT_COMMANDS`, `cleanup_temp_dir`, `background_cleaner_worker`, `register_all_handlers`, `main()`, `run()`)
  - **Edited**:
    - `bot.py`: reduced to the clean ~30-line entrypoint calling `myidm.app.run()` under `if __name__ == "__main__":` (see Open Question `OQ-1` regarding optional compatibility re-exports).
    - Remaining test files re-pointed mechanically per `docs/bot-target-architecture.md` Section 4: `tests/test_apkinspect_regression.py`, `tests/test_apkinspect_suite.py`, `tests/test_blitzverify.py`, `tests/test_dedupguard.py` (including full-package `eval(`/`/eval` scan), `tests/test_real_apk_inspection.py`.
    - Optional `.dockerignore` ONLY if approved by owner under `OQ-2` (otherwise zero root/Docker files touched).
- **What Changes**:
  - Completes decomposition of `bot.py`; every module in `myidm/` owns a single responsibility; all 11 test files point at canonical `myidm.*` modules; `bot.py`, `main.py`, `Procfile`, and `Dockerfile` launch `myidm.app.run()`.
- **What Must Not Change**:
  - Startup sequence in `main()` (`API_ID`/`API_HASH`/`BOT_TOKEN` check -> `cleanup_temp_dir(6.0)` -> `cleanup_expired_pending_downloads()` -> `start_web_server()` -> `queue_worker` & `background_cleaner_worker` tasks -> `bot.start()` -> dormant `user_bot` -> `bot.get_me()` -> `bot.set_bot_commands(BOT_COMMANDS)` -> `idle()` -> shutdown).
  - `Dockerfile` base image, system packages, `requirements.txt` pins, `DATA_DIR` layout, session file `downloader_bot.session`, and all Section B contracts.
- **Verification Battery (in fixed order)**:
  1. `python -m py_compile bot.py main.py myidm/*.py tests/*.py`
  2. `DATA_DIR=<isolated_tmp> python -m unittest discover tests -v` (all tests green above Phase 0 baseline of 56)
  3. `DATA_DIR=<isolated_tmp> python tests/test_end_to_end_simulation.py` (all 4 flows green)
  4. `DATA_DIR=<isolated_tmp> python tests/test_apkinspect_suite.py` and `python tests/test_real_apk_inspection.py` (all assertions green)
  5. Full contract parity battery in `tests/test_contract_parity.py`: `BLITZVERIFY` byte identity, `callback_data` set equality, command & handler-order equality, `TEXTS` byte equality, SQLite schema equality, full-package zero-`eval` check, DAG cycle-free check, and zero banned em/en dash scan across all created/edited files.
- **Risks**:
  - Missing `register_all_handlers` call if `myidm.app` is imported in tests vs run via `bot.py`. Mitigated by invoking `register_all_handlers(clients.bot)` idempotently on `myidm.app` import as well as inside `main()`.
- **Rollback Note**:
  - Revert Phase 6 commit/image tag to Phase 5 (or any earlier tag down to `myidm-bot:v8-deflair`). Because `DATA_DIR/bot_database.db` and `DATA_DIR/downloader_bot.session` are untouched across all 6 phases, rolling the container image back to `myidm-bot:v8-deflair` works at any point with zero data migration or session loss.

---

## 2. Open Questions and Unclear Current Behavior (For Owner Clarification)

1. **`OQ-1` (`bot.py` post-Phase-6 compatibility re-exports)**: Once all 11 test files are re-pointed to `myidm.*` in Phase 6, should root `bot.py` be a pure ~25-line entrypoint (`from myidm.app import run` + `if __name__ == "__main__": run()`), or should it also re-export the public `myidm.*` symbols (`from myidm... import ...`) as a backwards-compatible facade for ad-hoc one-liner scripts?
2. **`OQ-2` (Adding `.dockerignore` in Phase 6)**: `Dockerfile:19` runs `COPY . .` and no `.dockerignore` exists in the repository today (`DEF-25.4`). Should Phase 6 add a `.dockerignore` excluding `.git/`, `.env`, `*.db`, `*.session*`, `pending_downloads/`, `__pycache__/`, and `tests_apk/SuperTuxKart*.apk`, or leave root files untouched because the architect's release pipeline builds from a clean export?
3. **`OQ-3` (Orphan `"btn_help"` and duplicate `"btn_settings"` branches in `callback_handler`)**: `callback_handler` contains an unreachable second `elif data == "btn_settings":` branch (`bot.py:3901-3906`, `DEF-06`) and an orphan `elif data == "btn_help":` branch (`bot.py:3908-3909`, `DEF-07`) that no button emits. Confirm that Phases 4-6 should preserve `"btn_help"` in the handled-callback set and leave the duplicate branch flagged (or authorize removing only the unreachable duplicate `elif` at `L3901`).
4. **`OQ-4` (Concurrent execution in `queue_worker`)**: `handle_all_messages` (`bot.py:4028-4035`) displays `"Queue position #N"` from `request_queue.qsize()`, whereas `queue_worker` (`bot.py:4062-4065`) immediately spawns `asyncio.create_task(handle_queued_task(...))` without awaiting completion, running transfers concurrently (`DEF-25.2`). Confirm that concurrent dispatch is the intended behavior to preserve verbatim during the restructure.
5. **`OQ-5` (Standalone non-`TestCase` scripts in `tests/`)**: `tests/test_apkinspect_suite.py` and `tests/test_real_apk_inspection.py` define standalone functions under `if __name__ == "__main__":` rather than `unittest.TestCase` classes, so `python -m unittest discover tests` runs 56 tests from 8 files and skips those 2 scripts. Should Phase 6 keep them as standalone scripts run alongside the battery, or also expose them as `unittest.TestCase` methods so `unittest discover` includes them?

---

## 3. Intentional Behavior Changes Excluded From All Phases (`REQUIRES OWNER DECISION`)

None of the items below may be absorbed into Phases 1 through 6 unless the owner explicitly approves the specific item in writing.

1. **`IBC-01` (`capbrand` Draft Feature) - `REQUIRES OWNER DECISION`**:
   - Moving delivery details into the uploaded file caption, adding a caption brand footer, removing the dormant Telegram Premium userbot surface, and adding a copy button on the `BLITZVERIFY v1` block. Pre-listed per Master Brief: excluded completely from all restructure phases.
2. **`IBC-02` (Unifying the Duplicated Upload Pipeline in `process_single_local_file_upload` and `process_download_and_upload`, `DEF-20` & `DEF-23`) - `REQUIRES OWNER DECISION`**:
   - Merging the ~260 duplicated lines between `upload.py:process_single_local_file_upload` and `downloads.py:process_download_and_upload` would alter observable behavior on at least one path unless decided: passing `url_key` and dynamic `flow_type` instead of hardcoded `"torrent"` on duplicate APK staging (`L4187`), including `TLS_VERIFICATION_SKIPPED_NOTICE` on Premium uploads (`L4261`), attaching `make_cancel_keyboard` during normal local uploads (`L4352`), and popping `task_id` from `ACTIVE_TASKS` in `run_approved_pending_upload` (`L3174`).
3. **`IBC-03` (Fixing Section A Silent-Failure Defects `DEF-09` through `DEF-16`) - `REQUIRES OWNER DECISION`**:
   - Editing `status_msg` with a bilingual error explanation when `forward_messages` raises a non-`MessageIdInvalid` error (`DEF-09`).
   - Calling `client.stop_transmission()` so `cancel_<task_id>` aborts active Pyrogram uploads instead of uploading to 100% after alerting `"Task cancelled"` (`DEF-10`), and editing `status_msg` when cancelling mid-split (`DEF-11`).
   - Validating HTTP status codes and `is_valid_binary_file` inside `process_zip_bundle` instead of silently skipping failed URLs or zipping HTML error pages (`DEF-12`).
   - Removing hardcoded `"OK"` on non-2xx HTTP status in `/probe` (`DEF-13`), reading real DB flags in `/brand @tag` confirmation (`DEF-14`), adding the missing `row["status"] == "expired"` check in `dup_no_` (`DEF-15`), and retrying/reporting `BLITZVERIFY` send errors (`DEF-16`).
4. **`IBC-04` (Section D Anti-Slop Cleanup of Web Health, Dashboard HTML, and Startup Logs, `DEF-17` & `DEF-18`) - `REQUIRES OWNER DECISION`**:
   - Replacing `"⚡ OMNIPOTENT OVERLORD ENGINE - ABSOLUTE POWER 100%"` on `GET /`, `"OMNIPOTENT OVERLORD ENGINE"` in `DASHBOARD_HTML_TEMPLATE`, and `"OMNIPOTENT OVERLORD"` log banners with plain factual text.
5. **`IBC-05` (Deleting Dead Code & Unused Artefacts `DEF-01` through `DEF-08`) - `REQUIRES OWNER DECISION`**:
   - Deleting `format_apk_inspection_card` (`bot.py:2718-2880`, coupled to 3 test files), `_owner_filter` / `owner_filter` (`L112-118`), `ADMIN_ID` / `MAX_SINGLE_FILE_SIZE` / `SPLIT_PART_SIZE` (`L105, 123-127`), unused `global_stats` table (`L397-403`), or the 11 unreferenced `TEXTS` keys (`L208, 230-238, 240`, frozen under Section B.4).
