# MyIDM Bot Module and Defect Inventory (Phase 0 Census)

## Document Metadata

- **Repository Root**: `C:\Users\TM\Desktop\idm`
- **Git Baseline**: Commit `8c8db3a` (`deflair`), clean tracked tree; untracked root files at audit start: `.aiexclude` (451 bytes) and `myidm-restructure-carbon-brief-v1.md` (20,294 bytes).
- **Monolith Target**: `bot.py` (298,010 bytes, 6,088 lines, MD5 `1551B1FD0883702B28345D0DA6D4AEA8`).
- **Function and Class Totals in `bot.py`**: 114 module-scope functions (`def` / `async def`), 10 nested functions, 124 total functions, 0 classes.
- **Logical Modules Inventoried**: 20 logical module groups (`M01` through `M20`) covering lines `1-6088` with zero unmapped lines.
- **Measured Test Baseline**:
  - `python -m unittest discover tests -v`: **56 tests run, 56 green (`OK`)** across 8 `unittest.TestCase` files (`test_apkinspect_suite.py`, `test_real_apk_inspection.py`, and `test_end_to_end_simulation.py` have 0 `TestCase` subclasses and execute as standalone scripts).
  - `python tests/test_end_to_end_simulation.py`: **4 end-to-end flows passed (`OK`, exit code 0)** (non-APK PDF download, fresh APK download + `BLITZVERIFY v1`, duplicate APK pause + warning card, approved duplicate upload + `BLITZVERIFY v1`).

---

## 1. Entry Chain and Runtime Tree Census

### 1.1 Root Files Classification

| Path | Size (Bytes) | Role / Classification | Evidence |
| :--- | ---: | :--- | :--- |
| `Dockerfile` | 422 | Container build definition (`python:3.11-slim`, `CMD ["python", "bot.py"]`) | `Dockerfile:1-22` |
| `Procfile` | 19 | Legacy PaaS process entry (`web: python bot.py`) | `Procfile:1` |
| `runtime.txt` | 14 | Legacy PaaS Python version pin (`python-3.11.9`) | `runtime.txt:1` |
| `.python-version` | 7 | Python version pin (`3.11.9`) | `.python-version:1` |
| `requirements.txt` | 193 | 11 pinned Python dependencies (`==`) | `requirements.txt:1-11` |
| `main.py` | 215 | Fallback exec wrapper invoking `bot.py` via `os.execv` | `main.py:1-6` |
| `bot.py` | 298,010 | Entire bot application monolith (6,088 lines) | `bot.py:1-6088` |
| `.gitignore` | 167 | Git ignore rules for secrets, DBs, sessions, temp dirs | `.gitignore:1-14` |
| `.aiexclude` | 451 | Context exclusion rules (untracked) | `.aiexclude:1-25` |
| `README.md` | 2,776 | Legacy project overview | `README.md:1-49` |
| `.env` | 157 | Local runtime secrets (untracked, ignored, not read) | `.gitignore:1` |
| `bot_database.db` | 131,072 | Local dev SQLite database (runtime state, not code) | `bot.py:131` |
| `downloader_bot.session` | 28,672 | Active local Pyrogram session file (runtime state, not code) | `bot.py:1395` |
| `bot_session.session` | 28,672 | Legacy/orphan local Pyrogram session file (runtime state, not code) | Root file |
| `pending_downloads/` | Directory | Local dev staged duplicate APKs (2 files, 7,707 bytes each; runtime state) | `bot.py:132-133` |
| `tests/` | Directory | 11 automated test and simulation scripts | `tests/*.py` |
| `tests_apk/` | Directory | 10 APK/ZIP/DB test fixtures used by `tests/` | `tests_apk/*` |

### 1.2 Container and Process Entry Chain

1. **Image Build (`Dockerfile:1-22`)**:
   - Base image: `FROM python:3.11-slim` (`Dockerfile:1`).
   - System packages (`Dockerfile:4-9`): `ffmpeg` (provides `ffmpeg` and `ffprobe` used at `bot.py:4948-4993`), `curl` (used at `bot.py:5662-5673`), `git` (unused at runtime), `aria2` (unused at runtime).
   - Working directory: `WORKDIR /app` (`Dockerfile:12`).
   - Dependencies: `COPY requirements.txt .` then `RUN pip install --no-cache-dir -r requirements.txt` (`Dockerfile:15-16`).
   - Application copy: `COPY . .` (`Dockerfile:19`). No `.dockerignore` exists in the repository.
   - Startup command: `CMD ["python", "bot.py"]` (`Dockerfile:22`).
2. **Alternative Entrypoints**:
   - `Procfile:1`: `web: python bot.py`.
   - `main.py:5-6`: `if __name__ == "__main__": os.execv(sys.executable, [sys.executable, "bot.py"])`.
3. **Import-Time Execution Sequence in `bot.py`** (runs immediately on `python bot.py` OR `import bot`):
   - `bot.py:6-10`: Calls `asyncio.get_event_loop()`, falling back to `asyncio.new_event_loop()` + `asyncio.set_event_loop(loop)` on Python 3.12+ where main-thread implicit loop creation was removed (required before `from pyrogram import ...` at `bot.py:44`).
   - `bot.py:39-43`: Optional `import psutil` sets `PSUTIL_AVAILABLE`.
   - `bot.py:51-52`: Mutates `pyrogram.utils.MIN_CHANNEL_ID = -10099999999999` and `pyrogram.utils.MAX_CHANNEL_ID = -1000000000000` to accept 64-bit Telegram channel IDs.
   - `bot.py:54-80`: Optional imports set `CURL_CFFI_AVAILABLE`, `TORRENTP_AVAILABLE`, and `YTDLP_AVAILABLE`; lines `70-78` monkeypatch `yt_dlp.extractor.odnoklassniki.OdnoklassnikiIE._parse_json` with `_safe_ok_parse_json`.
   - `bot.py:82`: Calls `load_dotenv()`.
   - `bot.py:87-91`: Calls `logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")` and binds `logger = logging.getLogger(__name__)`.
   - `bot.py:93-140`: Reads environment variables, initializes `ADMIN_IDS`, creates `DATA_DIR` (`L130`), `PENDING_DIR` (`L133`), and `DOWNLOAD_DIR` (`L139`), and records `START_TIME = time.time()` (`L140`).
   - `bot.py:165`: Calls `DASHBOARD_SECRET = get_or_create_dashboard_secret()`, opening `DB_FILE`, creating table `bot_meta` if absent, and reading/persisting `dashboard_secret`.
   - `bot.py:1023`: Calls `init_db()`, opening `DB_FILE`, enabling `WAL` and `busy_timeout=30000`, creating all 8 tables + 1 index, and running 12 guarded `ALTER TABLE` migrations.
   - `bot.py:1025-1026`: Initializes `ACTIVE_TASKS = {}` and `request_queue = asyncio.Queue()`.
   - `bot.py:1394-1412`: Instantiates `bot = Client("downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workdir=DATA_DIR, workers=16)` and conditionally `user_bot = Client("premium_user_uploader", ..., workdir=DATA_DIR, workers=16)` when `USER_SESSION_STRING` is non-empty.
   - `bot.py:3203-3965`: Registers 19 `@bot.on_message(...)` handlers and 1 `@bot.on_callback_query()` handler on `bot` in definition order.
4. **Runtime Startup and Shutdown Sequence (`bot.py:6029-6088`)**:
   - `bot.py:6084-6086`: `if __name__ == "__main__": bot.run(main())`.
   - `bot.py:6030-6032`: Verifies `API_ID`, `API_HASH`, and `BOT_TOKEN` are non-empty; logs error and calls `sys.exit(1)` if any is missing.
   - `bot.py:6034-6035`: Runs one-shot startup cleanups `cleanup_temp_dir(max_age_hours=6.0)` and `cleanup_expired_pending_downloads()`.
   - `bot.py:6036`: `await start_web_server()` binds `aiohttp.web.TCPSite` on `0.0.0.0:PORT` (`L1379-1389`).
   - `bot.py:6037-6038`: Spawns `asyncio.create_task(queue_worker())` and `asyncio.create_task(background_cleaner_worker())` (task handles are not stored).
   - `bot.py:6041-6059`: Starts `bot` (`await bot.start()`), conditionally starts dormant `user_bot` (`L6043-6052`), and calls `await bot.get_me()` (`L6054`).
   - `bot.py:6061-6077`: Calls `await bot.set_bot_commands([...])` with 12 `BotCommand` entries.
   - `bot.py:6079-6082`: Waits on `await idle()`, then stops `user_bot` (if connected) and `await bot.stop()`.

---

## 2. Logical Module and Function Inventory (`bot.py:1-6088`)

Every line of `bot.py` (`1-6088`) belongs to one of the 20 logical module groups below. Notice that several logical modules are physically split across non-adjacent line ranges in `bot.py` today (for example, `tr()` sits at `L1018-1021` separated from `TEXTS` at `L175-346`, and `get_ok_direct_mp4` sits at `L4714-4775` separated from the resolver block at `L1598-1888`).

### Summary Table of Logical Modules

| ID | Logical Module | Exact `bot.py` Line Ranges | Top-Level Fns | Nested Fns | Internal Dependencies | Depended On By |
| :--- | :--- | :--- | ---: | ---: | :--- | :--- |
| `M01` | Runtime Bootstrap & Optional Adapters | `1-83` | 1 | 0 | None (stdlib / 3rd-party) | `M02`, `M06`, `M08`, `M09`, `M18`, `M19` |
| `M02` | Configuration, Owner Gate & Paths | `84-174`, `5075` | 3 | 0 | `M01` (`load_dotenv`) | All modules (`M04`-`M20`) |
| `M03` | Localization (`TEXTS`) & Translator | `175-346`, `1018-1021` | 1 | 0 | None | `M11`, `M14`, `M15`, `M16`, `M18`, `M19` |
| `M04` | SQLite Persistence & Migrations | `347-1017`, `1022-1024` | 24 | 0 | `M02` (`DB_FILE`, `logger`) | `M06`, `M10`-`M20` |
| `M05` | In-Memory Task & Queue State | `1025-1027` | 0 | 0 | stdlib `asyncio` | `M06`, `M14`-`M19` |
| `M06` | `aiohttp` Health & Web Dashboard | `1028-1390` | 5 | 0 | `M01`, `M02`, `M04`, `M05`, `M10` | `M20` (`main`) |
| `M07` | Pyrogram Client & Uploader Handle | `1391-1418` | 1 | 0 | `M02` | `M13`, `M15`-`M17`, `M19`, `M20` |
| `M08` | Validation, HTML Scraper & TLS Error Classifier | `1419-1597`, `5076-5133` | 4 | 0 | `M01`, `M02` | `M09`, `M12`, `M18`, `M19` |
| `M09` | Host Link Resolvers (13 host families) | `1598-1888`, `4714-4776` | 5 | 0 | `M01`, `M02`, `M08` | `M15` (`/probe`), `M18`, `M19` |
| `M10` | Formatting, Filename Renamer & Disk Guards | `1889-2125` | 9 | 0 | `M02`, `M04` | `M06`, `M11`-`M19` |
| `M11` | Keyboards, Progress Bar & Safe Message Edit | `2126-2255` | 7 | 0 | `M02`, `M03`, `M04`, `M10` | `M14`-`M19` |
| `M12` | APK Inspection & `BLITZVERIFY` Formatter | `2256-2990`, `3087-3140` | 11 | 1 | `M02`, `M04`, `M08`, `M10` | `M13`, `M14`, `M19` |
| `M13` | Delivery Forward Cache (`fwdcache`) | `2991-3027`, `3574-3666` | 4 | 0 | `M02`, `M04`, `M07`, `M10`, `M12`, `M19` | `M16`, `M17` |
| `M14` | Duplicate APK Guard (`dedupguard` / `dupfix`) | `3028-3086`, `3141-3199` | 3 | 0 | `M02`, `M03`, `M04`, `M05`, `M10`, `M11`, `M12`, `M19` | `M16`, `M19` |
| `M15` | Owner & Admin Command Handlers | `3200-3573` | 17 | 0 | `M02`, `M03`, `M04`, `M05`, `M07`, `M09`, `M10`, `M11` | `M20` (via `@bot.on_message`) |
| `M16` | Callback Query Router | `3667-3944` | 1 | 0 | `M02`-`M05`, `M07`, `M10`, `M11`, `M13`, `M14` | `M20` (via `@bot.on_callback_query`) |
| `M17` | Message/Torrent Intake & Queue Worker | `3945-4066` | 4 | 0 | `M02`, `M04`, `M05`, `M07`, `M13`, `M18` | `M20` (`main`, decorators) |
| `M18` | Download Engines (Torrent, ZIP, Turbo, Stream) | `4067-4135`, `4426-4713`, `4777-4935` | 6 | 4 | `M01`-`M05`, `M09`, `M10`, `M11`, `M19` | `M17`, `M19` |
| `M19` | Upload Pipeline & Download-Upload Orchestrator | `4136-4425`, `4936-5074`, `5134-5988` | 5 | 5 | `M01`-`M05`, `M07`-`M12`, `M14`, `M18` | `M13`, `M14`, `M17`, `M18` |
| `M20` | Background Cleaners & Entrypoint | `5989-6088` | 3 | 0 | `M02`, `M04`, `M06`, `M07`, `M17` | Process root (`__main__`) |
| **Total** | **20 Logical Modules** | **`1-6088` (100%)** | **114** | **10** | **0 Classes** | **124 Total Functions** |

### Complete Function Inventory by Logical Module

#### `M01`: Runtime Bootstrap & Optional Dependency Adapters (`bot.py:1-83`)
- `_safe_ok_parse_json(self, json_string, *args, **kwargs)` (`L72-75`, 4L): Guard wrapper around `odnoklassniki.OdnoklassnikiIE._parse_json` returning `dict`/`list` inputs directly.

#### `M02`: Configuration, Owner Gate & Paths (`bot.py:84-174`, `L5075`)
- `is_admin(user_id: int) -> bool` (`L107-110`, 4L): Returns `True` if `ADMIN_IDS` is empty or `user_id in ADMIN_IDS`. Called at 24 sites in `bot.py` + `test_fwdcache.py`.
- `_owner_filter(_, __, message)` (`L112-116`, 5L): Pyrogram custom filter callback checking `ADMIN_IDS` (used only at `L118` to build dead `owner_filter`).
- `get_or_create_dashboard_secret() -> str` (`L142-163`, 22L): Returns `DASHBOARD_SECRET` env override if set, else reads/creates `bot_meta['dashboard_secret']` (`secrets.token_hex(24)`) in `DB_FILE`.
- Constant `TLS_VERIFICATION_SKIPPED_NOTICE` (`L5075`, 1L): Bilingual notice appended to success cards when unverified TLS retry succeeded.

#### `M03`: Localization (`TEXTS`) & Translator (`bot.py:175-346`, `L1018-1021`)
- `tr(lang: str, key: str, **kwargs) -> str` (`L1018-1021`, 4L): Looks up `TEXTS.get(lang, TEXTS["ar"]).get(key, TEXTS["ar"].get(key, ""))` and formats `kwargs` when non-empty. Called 93 times across `bot.py`.

#### `M04`: SQLite Persistence & Migrations (`bot.py:347-1017`, `L1022-1024`)
- `init_db()` (`L356-509`, 154L): Enables WAL + `busy_timeout=30000`, creates 8 tables + 1 index, runs 12 guarded `ALTER TABLE` migrations; called at module import (`L1023`).
- `db_add_user(user_id, username, first_name)` (`L511-519`, 9L): `INSERT OR IGNORE INTO users`.
- `db_get_user_settings(user_id) -> dict` (`L521-562`, 42L): Returns 12-key user settings dict with defaults.
- `db_add_replacement(user_id, find_text, replace_text)` (`L564-572`, 9L): Inserts row in `custom_replacements`.
- `db_get_user_replacements(user_id) -> list` (`L574-580`, 7L): Returns `[(find_text, replace_text), ...]`.
- `db_clear_user_replacements(user_id)` (`L582-587`, 6L): Deletes user's rows in `custom_replacements`.
- `db_get_total_users_count() -> int` (`L589-598`, 10L): Returns `COUNT(*) FROM users` (0 on error).
- `db_update_user_setting(user_id, key, val)` (`L600-608`, 9L): Validates `key in ALLOWED_USER_SETTINGS` then updates `users`.
- `db_add_history(user_id, filename, size, category)` (`L610-616`, 7L): Inserts completed transfer in `history`.
- `db_get_history(user_id, limit=10) -> list` (`L618-627`, 10L): Returns latest `limit` rows from `history`.
- `db_add_apk_inspection(...) -> int` (`L629-653`, 25L): Coerces `min_sdk`/`target_sdk` to `int` where possible and inserts into `apk_inspections`.
- `db_get_last_inspection_for_package(package, exclude_latest=True, exclude_version_code=None) -> dict | None` (`L655-721`, 67L): Fetches prior inspection row for signer comparison.
- `db_check_apk_duplicate(package, version_code) -> dict | None` (`L723-756`, 34L): Queries `apk_inspections WHERE package = ? AND version_code = ? ORDER BY id DESC LIMIT 1`.
- `db_add_pending_download(...) -> int` (`L758-786`, 29L): Embeds `url_key` into `inspection_json` backup and inserts row into `pending_downloads` with legacy fallback if `url_key` column missing.
- `db_get_pending_download(pending_id) -> dict | None` (`L788-855`, 68L): Reads `pending_downloads` row by `id` with `inspection_json["url_key"]` fallback.
- `db_update_pending_status(pending_id, status)` (`L857-862`, 6L): Updates `pending_downloads.status`.
- `db_record_delivery(...) -> int` (`L864-885`, 22L): Replaces `(user_id, url_key)` row in `download_deliveries` (`DELETE` then `INSERT`).
- `db_get_delivery(user_id, url_key) -> dict | None` (`L887-922`, 36L): Looks up cached delivery by `(user_id, url_key)` and parses `message_ids` JSON.
- `db_get_delivery_by_id(delivery_id) -> dict | None` (`L924-957`, 34L): Looks up `download_deliveries` row by `id`.
- `db_delete_delivery(delivery_id)` (`L959-970`, 12L): Deletes stale `download_deliveries` row by `id`.
- `db_get_apk_inspection(package, version_code) -> dict | None` (`L972-973`, 2L): Alias delegating to `db_check_apk_duplicate(package, version_code)`.
- `cleanup_expired_pending_downloads()` (`L975-993`, 19L): Deletes files on disk and sets `status = 'expired'` for rows in `('pending', 'approved')` older than 24h (`cutoff = time.time() - 86400`).
- `db_get_all_user_ids() -> list` (`L995-1004`, 10L): Returns all `user_id` values from `users` for `/broadcast`.
- `db_get_global_stats() -> dict` (`L1006-1016`, 11L): Aggregates `users` count and `history` count + byte sum.

#### `M05`: In-Memory Task & Queue State (`bot.py:1025-1027`)
- Module state only: `ACTIVE_TASKS = {}` (`L1025`) and `request_queue = asyncio.Queue()` (`L1026`).

#### `M06`: `aiohttp` Health & Web Dashboard (`bot.py:1028-1390`)
- `handle_health_check(request)` (`L1031-1032`, 2L): `GET /` health response.
- `handle_dashboard_view(request)` (`L1300-1312`, 13L): `GET /dashboard?key=...` HTML view gated by `DASHBOARD_SECRET`.
- `handle_dashboard_stats_api(request)` (`L1314-1367`, 54L): `GET /api/dashboard/stats?key=...` JSON telemetry endpoint.
- `handle_dashboard_cancel_task_api(request)` (`L1369-1377`, 9L): `POST /api/dashboard/cancel?key=...&task_id=...` sets `ACTIVE_TASKS[tid]["cancelled"] = True`.
- `start_web_server()` (`L1379-1389`, 11L): Registers the 4 routes on `web.Application()` and starts `TCPSite` on `0.0.0.0:PORT`.

#### `M07`: Pyrogram Client & Uploader Handle (`bot.py:1391-1418`)
- `get_uploader_client()` (`L1414-1417`, 4L): Returns `user_bot` if connected, else `bot`.

#### `M08`: Binary Validation, HTML Scraper & TLS Error Classifier (`bot.py:1419-1597`, `L5076-5133`)
- `is_valid_binary_file(filepath: str) -> tuple` (`L1422-1475`, 54L): Checks magic bytes, null bytes, and HTML signatures on first 8 KiB; returns `(False, html_up_to_300KB)` when file is an HTML page.
- `extract_video_embed_from_html(html_text: str, original_url: str) -> tuple` (`L1477-1551`, 75L): Extracts `og:title`/`<title>` and ranked embed/stream URLs (`ok.ru`, `dood`, `streamwish`, etc.).
- `extract_real_download_link_from_html(html_text: str, original_url: str) -> str` (`L1553-1596`, 44L): Resolves Google Drive confirmation links, video embeds (`#ref=...&title=...`), or direct archive/APK hrefs (`d.an1.com`, `.apk`, `.zip`, etc.).
- `is_cert_verification_error(exc: BaseException | None, seen: set | None = None) -> bool` (`L5077-5132`, 56L): Recursively inspects exception chains (`__cause__`, `__context__`, `certificate_error`, `os_error`) for `ssl.SSLCertVerificationError`, `aiohttp.ClientConnectorCertificateError`, `curl_cffi` `CertificateVerifyError` / `CurlError(code=60)`, or `"CERTIFICATE_VERIFY_FAILED"` / `"SSLCertVerificationError"`.

#### `M09`: Host Link Resolvers (`bot.py:1598-1888`, `L4714-4776`)
- `unrestrict_terabox(url: str) -> tuple` (`L1598-1636`, 39L): Queries 3 TeraBox proxy APIs (`terabox-downloader.online`, `yt-api.org`, `terabox-api.online`) for `(dlink, fname)`.
- `unrestrict_1fichier(url: str) -> str` (`L1638-1661`, 24L): Posts `did=0` form to bypass 1Fichier countdown page.
- `unrestrict_mega(url: str) -> tuple` (`L1663-1679`, 17L): Queries `megadl.hazex.workers.dev` JSON resolver for `(dlink, fname)`.
- `unrestrict_direct_link(url: str) -> str` (`L1684-1887`, 204L): Master dispatcher across **13 host families**:
  1. TeraBox & 8 mirror domains (`L1686-1692`)
  2. 1Fichier & 4 mirror domains (`L1695-1699`)
  3. Mega.nz / Mega.co.nz (`L1702-1707`)
  4. Mediafire (`L1710-1726`)
  5. Pixeldrain (`L1729-1731`)
  6. AN1 (`an1.net` / `an1.com`, `Referer: https://an1.com/`, fragment `#cookie=` PHPSESSID support, `d*.an1.com` extraction) (`L1734-1771`)
  7. GitHub Blob (`github.com/.../blob/...` -> `raw.githubusercontent.com`) (`L1774-1775`)
  8. Dropbox (`dl=1`) (`L1778-1782`)
  9. Google Drive (`drive.google.com/uc?export=download&id=...`) (`L1785-1788`)
  10. DocumentaryArea (`player.php` -> `/video/` -> `video.php?playback=...#ref=...&cookie=...&title=...`) (`L1791-1817`)
  11. OK.ru / Odnoklassniki (`videoembed/<id>#ref=https://ok.ru/&title=...`) (`L1820-1858`)
  12. Catbox (`catbox.moe` fast-return) (`L1861-1862`)
  13. Generic web page HTML fallback (`CurlAsyncSession` 300 KiB sample with UTF-8 / `cp1256` fallback -> `extract_real_download_link_from_html`) (`L1865-1885`).
- `get_ok_direct_mp4(embed_or_video_url: str) -> tuple` (`L4714-4775`, 62L): Parses `data-options` flashvars metadata from `ok.ru/videoembed/...`, selects highest progressive MP4 quality (`ultra` down to `mobile`), and probes `Content-Range` size with a 1 KiB Range GET.

#### `M10`: Formatting, Filename Sanitizer/Renamer & Disk Guards (`bot.py:1889-2125`)
- `humanbytes(size) -> str` (`L1892-1907`, 16L): Formats byte count using binary IEC units (`B`, `KiB`, `MiB`, `GiB`, `TiB`, `PiB`).
- `time_formatter(seconds: int) -> str` (`L1909-1917`, 9L): Formats seconds as `Xd, Xh, Xm, Xs` or `0s`.
- `get_god_category(filename: str) -> tuple` (`L1919-1934`, 16L): Maps file extension to `(icon, category_name, is_video_bool)`.
- `sanitize_filename(filename: str) -> str` (`L1936-1939`, 4L): Strips path components and replaces illegal filesystem characters with `_`.
- `clean_and_rename_filename(raw_filename: str, user_id: int = 0) -> str` (`L1941-2011`, 71L): Strips ad tags/domains (`clean_tags`), applies `custom_replacements`, applies `channel_tag` (`brand_position`), and prepends/appends `custom_prefix`/`custom_suffix`.
- `smart_extract_filename(url: str, headers: dict) -> str` (`L2013-2067`, 55L): Extracts filename from RFC 5987 `filename*`, `Content-Disposition`, URL path, or `Content-Type` map.
- `parse_chat_id(chat_id_raw)` (`L2069-2075`, 7L): Converts numeric chat ID strings (including `-100...`) to `int`, preserving `@username` strings.
- `check_disk_space(path: str, needed_bytes: int | None = None) -> tuple[bool, int, int, int]` (`L2077-2108`, 32L): Enforces `free >= needed * 1.25 + reserve` when `needed_bytes > 0`, else `free >= reserve * 2`.
- `check_disk_space_for_split(path: str, piece_size: int) -> tuple[bool, int, int, int]` (`L2110-2124`, 15L): Enforces `free >= piece_size + reserve`.

#### `M11`: Keyboards, Progress Bar & Safe Message Edit (`bot.py:2126-2255`)
- `make_start_keyboard(lang="ar", is_admin=False)` (`L2126-2142`, 17L): Builds main menu keyboard (5 buttons + conditional `btn_admin_panel`).
- `make_settings_keyboard(user_id: int)` (`L2144-2162`, 19L): Builds settings menu keyboard (8 buttons).
- `make_brand_keyboard(user_id: int)` (`L2164-2178`, 15L): Builds channel branding submenu (5 buttons).
- `make_back_keyboard(lang="ar")` (`L2180-2183`, 4L): Single `btn_start` back button.
- `make_cancel_keyboard(task_id: str, lang="ar")` (`L2185-2188`, 4L): Single `cancel_{task_id}` button.
- `progress_bar(...)` (`L2190-2241`, 52L): Throttled (2.5s) 10-block (`▰`/`▱`) transfer progress updater handling `FloodWait`, `RPCError`, and `MessageNotModified`.
- `safe_edit_text(message, text, *args, **kwargs)` (`L2243-2254`, 12L): Wraps `message.edit_text(...)`, swallowing `MessageNotModified`.

#### `M12`: APK Inspection & `BLITZVERIFY` Formatter (`bot.py:2256-2990`, `L3087-3140`)
- `compute_file_sha256(filepath: str, chunk_size=8*1024*1024) -> str` (`L2259-2267`, 9L): Streaming uppercase hex SHA-256.
- `format_dn(name: x509.Name) -> str` (`L2269-2296`, 28L): Formats X.509 Subject DN attributes (`CN`, `O`, `OU`, `C`, `ST`, `L`, `emailAddress`).
- `parse_axml(raw: bytes) -> dict` (`L2298-2436`, 139L): Pure-Python binary Android `AndroidManifest.xml` (`RES_XML_TYPE` `0x0003`) parser extracting `package`, `version_name`, `version_code`, `min_sdk`, `target_sdk`, `label`.
- `extract_v1_cert(z: zipfile.ZipFile)` (`L2438-2449`, 12L): Extracts PKCS#7 DER signer certificate from `META-INF/*.RSA|*.DSA|*.EC`.
- `extract_v2_v3_cert(filepath: str)` (`L2451-2531`, 81L): Parses `APK Sig Block 42` pairs `0x7109871a` (v2) and `0xf05368c0` (v3) to load first X.509 DER certificate.
- `inspect_apk(file_path: str) -> dict | None` (`L2533-2708`, 176L): Inspects `.apk` and `.xapk`/`.apks` bundles (selecting base APK by `manifest.json` match -> `base.apk`/`base-master.apk` -> largest `.apk`), extracting hashes, manifest fields, and v1 or v2/v3 certificate fingerprints.
- `format_cairo_time(epoch_time: float) -> str` (`L2710-2716`, 7L): Formats epoch timestamp in `Africa/Cairo` (`UTC+3` fallback) as `%Y-%m-%d %H:%M Cairo`.
- `format_apk_inspection_card(info: dict, prev: dict | None, lang="ar") -> str` (`L2718-2880`, 163L): Legacy inspection card formatter (**zero runtime call sites in `bot.py`**; directly tested in 3 test files).
- `format_signer_change_warning(info: dict, prev: dict | None) -> str | None` (`L2882-2902`, 21L): Returns plain-text bilingual warning when `cert_sha256` differs from previous version of same package.
- `format_blitzverify_block(info: dict) -> str` (`L2904-2989`, 86L) + nested `is_valid_val(val)` (`L2908-2914`, 7L): Formats frozen `BLITZVERIFY v1` fenced Markdown block.
- `handle_apk_inspection_card(...)` (`L3087-3139`, 53L): Post-upload APK hook: runs `inspect_apk` (if not precomputed), queries `db_get_last_inspection_for_package`, records row via `db_add_apk_inspection`, sends optional signer-change warning (`ParseMode.DISABLED`), and sends `BLITZVERIFY v1` block (`ParseMode.MARKDOWN`).

#### `M13`: Delivery Forward Cache (`fwdcache`) (`bot.py:2991-3027`, `L3574-3666`)
- `format_fwdcache_note(filename: str, total_size: int, created_at: int) -> str` (`L2991-3004`, 14L): Formats bilingual forwarded-delivery note with Cairo timestamp.
- `is_message_not_found_error(exc: BaseException | None) -> bool` (`L3006-3026`, 21L): Matches Pyrogram `MessageIdInvalid` or message-not-found error strings.
- `handle_url_intake(...)` (`L3574-3645`, 72L): Checks `db_get_delivery(user_id, url_key)` when `not force_fresh`; forwards cached message IDs, sends `fwdcache` note with `fwd_fresh_<id>` button, re-emits `BLITZVERIFY v1` from stored `apk_inspections` if APK, deletes `status_msg`; on `is_message_not_found_error`, deletes stale row and falls through to `process_download_and_upload`.
- `run_fresh_download(delivery_id, user_msg, status_msg=None, forced_user_id=None)` (`L3647-3665`, 19L): Looks up delivery by ID and invokes `process_download_and_upload` bypassing cache.

#### `M14`: Duplicate APK Guard (`dedupguard` / `dupfix`) (`bot.py:3028-3086`, `L3141-3199`)
- `format_duplicate_warning_card(info: dict, prev: dict, lang="ar") -> str` (`L3028-3075`, 48L): Formats bilingual duplicate APK warning card with signer match/diff status.
- `make_duplicate_keyboard(pending_id: int, lang="ar") -> InlineKeyboardMarkup` (`L3077-3085`, 9L): Builds `dup_go_{pending_id}` and `dup_no_{pending_id}` buttons.
- `run_approved_pending_upload(pending_id: int, original_msg: Message)` (`L3141-3198`, 58L): Loads staged APK from `pending_downloads`, verifies file exists on disk, creates uploading `status_msg`, and calls `process_single_local_file_upload(..., skip_dup_check=True)`.

#### `M15`: Owner & Admin Command Handlers (`bot.py:3200-3573`)
17 `@bot.on_message(filters.command(...))` async handlers:
- `start_handler` (`L3204-3219`, 16L), `god_panel_handler` (`L3222-3234`, 13L), `probe_command_handler` (`L3237-3312`, 76L), `settings_command_handler` (`L3315-3324`, 10L), `help_command_handler` (`L3327-3332`, 6L), `stats_command_handler` (`L3335-3351`, 17L), `history_command_handler` (`L3354-3370`, 17L), `broadcast_command_handler` (`L3373-3426`, 54L), `set_prefix_handler` (`L3429-3439`, 11L), `clear_prefix_handler` (`L3442-3447`, 6L), `set_suffix_handler` (`L3450-3460`, 11L), `clear_suffix_handler` (`L3463-3468`, 6L), `replace_command_handler` (`L3471-3493`, 23L), `list_replacements_handler` (`L3496-3522`, 27L), `clear_replacements_handler` (`L3525-3530`, 6L), `brand_command_handler` (`L3533-3564`, 32L), `clear_brand_handler` (`L3567-3572`, 6L).

#### `M16`: Callback Query Router (`bot.py:3667-3944`)
- `callback_handler(client: Client, query: CallbackQuery)` (`L3668-3943`, 276L): Dispatches all inline keyboard callbacks (`cancel_`, `dup_go_`, `dup_no_`, `fwd_fresh_`, settings toggles, branding toggles, and navigation panels).

#### `M17`: Message/Torrent Intake & Queue Worker (`bot.py:3945-4066`)
- `handle_document_torrent(client, message)` (`L3949-3960`, 12L): Downloads `.torrent` attachments into `DOWNLOAD_DIR` and enqueues `("torrent", ...)`.
- `handle_all_messages(client, message)` (`L3966-4042`, 77L): Parses magnet links, `[ZIP]` multi-URL bundles, and single/bulk `URL | Custom_Name | Custom_Caption` lines; enqueues tasks on `request_queue`.
- `handle_queued_task(task_data)` (`L4044-4060`, 17L): Dispatches `"torrent"`, `"zip_bundle"`, or `"single"` (`handle_url_intake`), calling `request_queue.task_done()` and `gc.collect()` in `finally`.
- `queue_worker()` (`L4062-4065`, 4L): Infinite loop reading `request_queue.get()` and spawning `asyncio.create_task(handle_queued_task(task_data))`.

#### `M18`: Download Engines (`bot.py:4067-4135`, `L4426-4713`, `L4777-4935`)
- `process_torrent_download(torrent_src, status_msg, user_msg)` (`L4070-4134`, 65L): Runs `TorrentDownloader`, polls cancellation every 2s, scans `DOWNLOAD_DIR` for files with `mtime >= start_time`, and uploads each via `process_single_local_file_upload`.
- `process_zip_bundle(valid_requests, status_msg, user_msg)` (`L4426-4509`, 84L): Downloads multiple URLs sequentially, packs them into `bundle_<ts>.zip`, and uploads via `user_msg.reply_document`.
- `is_speed_throttled_url(url: str) -> bool` (`L4511-4528`, 18L): Matches speed-cap query parameters or 13 throttled file-host domains.
- `download_multi_stream_turbo(...) -> bool` (`L4530-4695`, 166L) + nested `fetch_block` (`L4591-4628`, 38L) and `worker_loop` (`L4630-4665`, 36L): Range-segmented parallel downloader (512 KiB to 2 MiB blocks, up to 64 workers, end-game hedging on slowest in-flight block).
- `is_hls_or_video_stream(url: str) -> bool` (`L4697-4712`, 16L): Matches `.m3u8`/`.mpd` or 29 streaming/social video domains.
- `download_video_or_m3u8(...) -> tuple` (`L4777-4934`, 158L) + nested `ytdl_progress_hook` (`L4872-4887`, 16L) and `run_ydl` (`L4914-4924`, 11L): Fast-paths `ok.ru` via `get_ok_direct_mp4` + `download_multi_stream_turbo`, falling back to `yt_dlp.YoutubeDL` across 3 candidate `Referer` values.

#### `M19`: Upload Pipeline & Download-Upload Orchestrator (`bot.py:4136-4425`, `L4936-5074`, `L5134-5988`)
- `process_single_local_file_upload(...)` (`L4136-4424`, 289L) + nested `pyrogram_progress_prem` (`L4221-4226`, 6L) and `pyrogram_progress` (`L4356-4357`, 2L): Local file upload pipeline (APK duplicate check, >1.95 GiB Premium upload or 1.90 GiB part splitting, <=1.95 GiB direct video/document upload + dormant `CHANNEL_ID` copy, history + `download_deliveries` recording, success card, `handle_apk_inspection_card`, and `pending_downloads` cleanup).
- `extract_video_metadata(video_path: str)` (`L4936-5000`, 65L): Runs `ffprobe` for `(duration, width, height)` and `ffmpeg` for a `320px`-wide JPEG thumbnail.
- `build_file_caption(...) -> tuple` (`L5002-5030`, 29L): Builds HTML file caption and optional channel inline button (`reply_markup`).
- `resilient_send_media(...)` (`L5032-5073`, 42L): 4-attempt retry wrapper around `client.send_video` / `client.send_document` handling `FloodWait`.
- `process_download_and_upload(...)` (`L5134-5987`, 854L) + nested `_perform_aiohttp_download` (`L5563-5615`, 53L), `pyrogram_progress_prem` (`L5771-5776`, 6L), and `pyrogram_progress` (`L5892-5897`, 6L): End-to-end single-URL orchestrator (max 2 HTML redirect hops, `unrestrict_direct_link`, fragment `#ref`/`#cookie`/`#title` parsing, initial disk check, stream engine -> throttled turbo engine -> 3-profile `curl_cffi` -> `aiohttp` fallback with 1x TLS cert-error unverified retry at each HTTP stage, binary magic verification + system `curl` fallback + HTML link re-extraction, APK duplicate check, and full upload/history/delivery/`BLITZVERIFY` pipeline).

#### `M20`: Background Cleaners & Entrypoint (`bot.py:5989-6088`)
- `cleanup_temp_dir(max_age_hours: float | None = 6.0)` (`L5989-6008`, 20L): Deletes files in `DOWNLOAD_DIR` older than 6h without touching `PENDING_DIR`.
- `background_cleaner_worker()` (`L6010-6024`, 15L): Hourly loop (`asyncio.sleep(3600)`) calling `cleanup_expired_pending_downloads()` and `cleanup_temp_dir(max_age_hours=6.0)`.
- `main()` (`L6029-6082`, 54L): Startup orchestrator invoked by `bot.run(main())` (`L6086`).

---

## 3. Exact SQLite Database Schema and Migrations

Database file path: `DB_FILE = os.path.join(DATA_DIR, "bot_database.db")` (`bot.py:131`).
Connection settings in `init_db()` (`bot.py:357-363`): `timeout=30`, `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=30000;`.

### 3.1 Tables Created Today (8 Tables + 1 Explicit Index)

1. **`users`** (`bot.py:365-384`):
   - `user_id INTEGER PRIMARY KEY`
   - `username TEXT`
   - `first_name TEXT`
   - `joined_at REAL`
   - `upload_mode TEXT DEFAULT 'auto'`
   - `enable_thumbs INTEGER DEFAULT 1`
   - `enable_caption INTEGER DEFAULT 1`
   - `fast_speed INTEGER DEFAULT 1`
   - `god_threads INTEGER DEFAULT 64`
   - `lang TEXT DEFAULT 'ar'`
   - `clean_tags INTEGER DEFAULT 1`
   - `custom_prefix TEXT DEFAULT ''`
   - `custom_suffix TEXT DEFAULT ''`
   - `channel_tag TEXT DEFAULT ''`
   - `brand_position TEXT DEFAULT 'suffix'`
   - `channel_button INTEGER DEFAULT 1`
2. **`history`** (`bot.py:386-395`):
   - `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `user_id INTEGER`
   - `filename TEXT`
   - `size INTEGER`
   - `category TEXT DEFAULT '📁 عام'`
   - `timestamp REAL`
3. **`global_stats`** (`bot.py:397-403`):
   - `key TEXT PRIMARY KEY`
   - `val_num INTEGER DEFAULT 0`
   - `val_float REAL DEFAULT 0.0`
4. **`custom_replacements`** (`bot.py:405-412`):
   - `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `user_id INTEGER`
   - `find_text TEXT`
   - `replace_text TEXT`
5. **`apk_inspections`** (`bot.py:414-429`):
   - `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `user_id INTEGER`
   - `package TEXT`
   - `version_name TEXT`
   - `version_code INTEGER`
   - `file_sha256 TEXT`
   - `cert_sha256 TEXT`
   - `size INTEGER`
   - `filename TEXT`
   - `checked_at REAL`
   - `min_sdk INTEGER`
   - `target_sdk INTEGER`
6. **`download_deliveries`** (`bot.py:431-445`):
   - `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `user_id INTEGER NOT NULL`
   - `url_key TEXT NOT NULL`
   - `filename TEXT`
   - `total_size INTEGER`
   - `chat_id INTEGER NOT NULL`
   - `message_ids TEXT NOT NULL` (JSON array of integers)
   - `package TEXT`
   - `version_code INTEGER`
   - `created_at INTEGER NOT NULL`
   - Index: `CREATE INDEX IF NOT EXISTS idx_deliveries_user_url ON download_deliveries(user_id, url_key)` (`bot.py:445`)
7. **`bot_meta`** (`bot.py:148-153` in `get_or_create_dashboard_secret`, and `bot.py:447-452` in `init_db`):
   - `key TEXT PRIMARY KEY`
   - `value TEXT`
8. **`pending_downloads`** (`bot.py:454-471` + `ALTER TABLE` at `bot.py:493-496`):
   - `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `user_id INTEGER`
   - `chat_id INTEGER`
   - `file_path TEXT`
   - `filename TEXT`
   - `custom_caption TEXT`
   - `package TEXT`
   - `version_name TEXT`
   - `version_code INTEGER`
   - `size INTEGER`
   - `created_at REAL`
   - `status TEXT DEFAULT 'pending'`
   - `inspection_json TEXT`
   - `flow_type TEXT DEFAULT 'direct'`
   - `url_key TEXT DEFAULT ''` (added via `ALTER TABLE` at `bot.py:494`, even on a fresh database, because `url_key` is not in the `CREATE TABLE` body at `L455-470`).

### 3.2 Guarded Additive Migrations in `init_db()` (12 `ALTER TABLE` Statements)

Each migration wraps `ALTER TABLE ... ADD COLUMN ...` in `try ... except sqlite3.OperationalError: pass`:
1. `users.god_threads INTEGER DEFAULT 64` (`bot.py:474, 484`)
2. `users.lang TEXT DEFAULT 'ar'` (`bot.py:475, 484`)
3. `users.clean_tags INTEGER DEFAULT 1` (`bot.py:476, 484`)
4. `users.custom_prefix TEXT DEFAULT ''` (`bot.py:477, 484`)
5. `users.custom_suffix TEXT DEFAULT ''` (`bot.py:478, 484`)
6. `users.channel_tag TEXT DEFAULT ''` (`bot.py:479, 484`)
7. `users.brand_position TEXT DEFAULT 'suffix'` (`bot.py:480, 484`)
8. `users.channel_button INTEGER DEFAULT 1` (`bot.py:481, 484`)
9. `history.category TEXT DEFAULT '📁 عام'` (`bot.py:489`)
10. `pending_downloads.url_key TEXT DEFAULT ''` (`bot.py:494`)
11. `apk_inspections.min_sdk INTEGER` (`bot.py:499`)
12. `apk_inspections.target_sdk INTEGER` (`bot.py:504`)

---

## 4. Complete Contract Registers

### 4.1 Bot Commands Register (17 Command Handlers, 30 Command Strings, 12 Menu Entries)

| # | Handler Function | Line | Primary Command | Accepted Aliases | In `set_bot_commands` (`L6062-6075`) |
| ---: | :--- | ---: | :--- | :--- | :--- |
| 1 | `start_handler` | `3203` | `start` | None | Yes (`start`) |
| 2 | `god_panel_handler` | `3221` | `omnipotent` | `god`, `godmode` | Yes (`omnipotent`) |
| 3 | `probe_command_handler` | `3236` | `probe` | None | Yes (`probe`) |
| 4 | `settings_command_handler` | `3314` | `settings` | `lang` | Yes (`settings`) |
| 5 | `help_command_handler` | `3326` | `help` | None | Yes (`help`) |
| 6 | `stats_command_handler` | `3334` | `stats` | None | Yes (`stats`) |
| 7 | `history_command_handler` | `3353` | `history` | None | Yes (`history`) |
| 8 | `broadcast_command_handler` | `3372` | `broadcast` | None | Yes (`broadcast`) |
| 9 | `set_prefix_handler` | `3428` | `set_prefix` | `prefix` | Yes (`set_prefix`) |
| 10 | `clear_prefix_handler` | `3441` | `clear_prefix` | `cleanprefix` | No |
| 11 | `set_suffix_handler` | `3449` | `set_suffix` | `suffix` | Yes (`set_suffix`) |
| 12 | `clear_suffix_handler` | `3462` | `clear_suffix` | `cleansuffix` | No |
| 13 | `replace_command_handler` | `3470` | `replace` | None | Yes (`replace`) |
| 14 | `list_replacements_handler` | `3495` | `replacements` | `rules` | Yes (`replacements`) |
| 15 | `clear_replacements_handler` | `3524` | `clear_replacements` | None | No |
| 16 | `brand_command_handler` | `3532` | `brand` | `branding`, `set_brand`, `set_channel`, `channel` | No |
| 17 | `clear_brand_handler` | `3566` | `clear_brand` | `clear_channel` | No |

### 4.2 Pyrogram Handler Registration Order Register (20 Handlers Total)

Pyrogram evaluates group-0 message handlers strictly in registration order:
1. `L3203` - `L3566`: 17 `MessageHandler` registrations with `filters.command(...)` (listed in Table 4.1).
2. `L3667`: 1 `CallbackQueryHandler` (`@bot.on_callback_query()`) -> `callback_handler`.
3. `L3948`: 1 `MessageHandler` (`filters.document & ~filters.service`) -> `handle_document_torrent`.
4. `L3965`: 1 `MessageHandler` (`(filters.text | filters.caption) & ~filters.service`) -> `handle_all_messages`.

### 4.3 `callback_data` Register (22 Emitted Values + 1 Orphan Handler Branch)

| # | `callback_data` Value / Prefix | Match Mode | Emitted At (`bot.py`) | Handled At (`callback_handler`) |
| ---: | :--- | :--- | :--- | :--- |
| 1 | `btn_god_panel` | Exact | `L2129` (`make_start_keyboard`) | `L3893` |
| 2 | `btn_history` | Exact | `L2130` (`make_start_keyboard`) | `L3911` |
| 3 | `btn_settings` | Exact | `L2133` (`make_start_keyboard`), `L2177` (`make_brand_keyboard`) | `L3859` (active), `L3901` (unreachable duplicate) |
| 4 | `btn_probe_info` | Exact | `L2134` (`make_start_keyboard`) | `L3898` |
| 5 | `btn_stats` | Exact | `L2137` (`make_start_keyboard`) | `L3923` |
| 6 | `btn_admin_panel` | Exact | `L2141` (`make_start_keyboard`) | `L3872` |
| 7 | `toggle_lang` | Exact | `L2155` (`make_settings_keyboard`) | `L3776` |
| 8 | `toggle_mode` | Exact | `L2156` (`make_settings_keyboard`) | `L3783` |
| 9 | `toggle_threads` | Exact | `L2157` (`make_settings_keyboard`) | `L3790` |
| 10 | `toggle_caption` | Exact | `L2158` (`make_settings_keyboard`) | `L3799` |
| 11 | `toggle_thumbs` | Exact | `L2158` (`make_settings_keyboard`) | `L3806` |
| 12 | `toggle_cleantags` | Exact | `L2159` (`make_settings_keyboard`) | `L3813` |
| 13 | `btn_open_brand` | Exact | `L2160` (`make_settings_keyboard`) | `L3820` |
| 14 | `btn_start` | Exact | `L2161`, `L2182`, `L3889` | `L3867` |
| 15 | `btn_brand_help` | Exact | `L2173` (`make_brand_keyboard`) | `L3833` |
| 16 | `toggle_brand_pos` | Exact | `L2174` (`make_brand_keyboard`) | `L3837` |
| 17 | `toggle_brand_btn` | Exact | `L2175` (`make_brand_keyboard`) | `L3846` |
| 18 | `btn_clear_brand` | Exact | `L2176` (`make_brand_keyboard`) | `L3853` |
| 19 | `cancel_<task_id>` | Prefix `cancel_` | `L2187` (`make_cancel_keyboard`) | `L3678` |
| 20 | `dup_go_<pending_id>` | Prefix `dup_go_` | `L3082` (`make_duplicate_keyboard`) | `L3687` |
| 21 | `dup_no_<pending_id>` | Prefix `dup_no_` | `L3083` (`make_duplicate_keyboard`) | `L3722` |
| 22 | `fwd_fresh_<delivery_id>` | Prefix `fwd_fresh_` | `L3614` (`handle_url_intake`) | `L3753` |
| 23 | `btn_help` *(orphan branch)* | Exact | *Not emitted by any button* | `L3908` |

*(Note: Channel branding buttons created in `build_file_caption` at `L5028` use `url=ch_url`, not `callback_data`.)*

### 4.4 Environment Variables Register (11 Variables Read)

| # | Variable Name | Read Site(s) | Default | Status / Contract |
| ---: | :--- | :--- | :--- | :--- |
| 1 | `API_ID` | `L93` | `0` (`int`) | Active, required (`main()` exits at `L6030` if `0`) |
| 2 | `API_HASH` | `L94` | `""` | Active, required (`main()` exits at `L6030` if empty) |
| 3 | `BOT_TOKEN` | `L95` | `""` | Active, required (`main()` exits at `L6030` if empty) |
| 4 | `PORT` | `L96` | `8080` (`int`) | Active (`aiohttp` TCP port at `L1387`) |
| 5 | `ADMIN_ID` | `L99` | `""` | Active (comma/semicolon-separated ints merged into `ADMIN_IDS`) |
| 6 | `USER_SESSION_STRING` | `L120` | `""` | Dormant in production (Section C.4) |
| 7 | `PREMIUM_SESSION` | `L120` | `""` | Dormant legacy fallback alias for `USER_SESSION_STRING` |
| 8 | `DATA_DIR` | `L129` | `"."` | Active (holds `bot_database.db`, session file, `pending_downloads/`) |
| 9 | `DISK_MIN_FREE_GB` | `L135` | `"2"` (`2.0` float) | Active (disk reserve threshold in GiB) |
| 10 | `DASHBOARD_SECRET` | `L143` | `""` | Active optional override before SQLite `bot_meta` lookup |
| 11 | `CHANNEL_ID` | `L4204`, `L5755`, `L5905` | `""` | Dormant in production (read dynamically per upload; Section C.5) |

### 4.5 Background Tasks and Periodic/On-Demand Triggers Register

| # | Task / Coroutine | Spawn Site | Trigger / Interval | Purpose |
| ---: | :--- | :--- | :--- | :--- |
| 1 | `cleanup_temp_dir(6.0)` | `main()` `L6034` | One-shot on startup | Purges `DOWNLOAD_DIR` files older than 6 hours |
| 2 | `cleanup_expired_pending_downloads()` | `main()` `L6035` | One-shot on startup | Expires `pending`/`approved` rows older than 24h and removes files |
| 3 | `start_web_server()` (`TCPSite`) | `main()` `L6036` | Long-lived server | Serves `/`, `/dashboard`, `/api/dashboard/stats`, `/api/dashboard/cancel` |
| 4 | `queue_worker()` | `main()` `L6037` | Continuous `request_queue.get()` | Spawns `asyncio.create_task(handle_queued_task(...))` per item |
| 5 | `handle_queued_task(task_data)` | `queue_worker()` `L4065` | Per queued item | Executes `torrent`, `zip_bundle`, or `single` download flow |
| 6 | `background_cleaner_worker()` | `main()` `L6038` | Every `3600` seconds (1h) | Runs `cleanup_expired_pending_downloads()` + `cleanup_temp_dir(6.0)` |
| 7 | `run_approved_pending_upload(...)` | `callback_handler` `L3719` | On `dup_go_<id>` click | Uploads approved duplicate APK in background |
| 8 | `run_fresh_download(...)` | `callback_handler` `L3773` | On `fwd_fresh_<id>` click | Runs fresh download bypassing delivery cache |
| 9 | Dashboard JS `fetchStats()` | `DASHBOARD_HTML_TEMPLATE` `L1293` | Client browser `2000` ms | Polls `/api/dashboard/stats?key=...` when dashboard tab is open |

---

## 5. Global State Inventory

This table records every module-level mutable object, handle, monkeypatch, and test-overridden binding in `bot.py`.

| Global Symbol | Defined At | Kind / Type | Mutation Sites in `bot.py` | Read Sites in `bot.py` | Mutated/Patched in `tests/` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ACTIVE_TASKS` | `L1025` | `dict[str, dict]` | Insert: `L3174`, `L4080`, `L5152`; Mutate `"cancelled"`: `L1375`, `L3681`; Mutate `"filename"`: `L4155`, `L5233`, `L5271`, `L5325`, `L5397`, `L5489`, `L5581`; Mutate `"ssl_unverified"`: `L5307`, `L5468`, `L5628`; Pop: `L4133`, `L5976` | `L1338`, `L1360`, `L1374`, `L3680`, `L4105`, `L4154`, `L4222`, `L4303`, `L4330`, `L4404`, `L4592`, `L4632`, `L4675`, `L4867`, `L4873`, `L5232`, `L5270`, `L5306`, `L5324`, `L5364`, `L5369`, `L5396`, `L5430`, `L5467`, `L5488`, `L5522`, `L5557`, `L5580`, `L5597`, `L5627`, `L5642`, `L5772`, `L5843`, `L5893`, `L5901` | None |
| `request_queue` | `L1026` | `asyncio.Queue` | `put`: `L3960`, `L3990`, `L4017`, `L4042`; `get`: `L4064`; `task_done`: `L4059` | `qsize`: `L1361`, `L3341`, `L3877`, `L3925`, `L4028` | None |
| `ADMIN_IDS` | `L98` | `set[int]` | `ADMIN_IDS.add(...)` at import (`L103`) | `L108`, `L110`, `L113`, `L116` | None (`is_admin` patched in `test_fwdcache.py:196`) |
| `bot` | `L1394` | `pyrogram.Client` | Handler decorators `L3203-3965`; lifecycle `start`/`set_bot_commands`/`stop`/`run` at `L6041, 6062, 6082, 6086` | `L1417`, `L3589`, `L4368`, `L5913`, `L6054` | `patch.object(bot.bot, "forward_messages")` in `test_fwdcache.py`; `bot.bot.workdir` read in `test_dedupguard.py:53` |
| `user_bot` | `L1403-1405` | `Client \| None` | Conditional `Client` at `L1405`; `start`/`stop` at `L6045, 6081` | `L1415-1416`, `L4203`, `L5757`, `L6043`, `L6046`, `L6080` | `test_dedupguard.py:54-55` |
| `DATA_DIR` | `L129` | `str` (config path) | Rebound in test `setUp`/`tearDown` | `L130-132`, `L1399`, `L1410` | Mutated in `test_dedupguard`, `test_dupfix`, `test_fwdcache`, `test_sslretry` |
| `DB_FILE` | `L131` | `str` (config path) | Rebound in test `setUp`/`tearDown` | 24 `sqlite3.connect(DB_FILE, timeout=30)` sites (`L146` to `L1007`) | Mutated in `test_dedupguard`, `test_dupfix`, `test_fwdcache`, `test_sslretry`; read in `test_end_to_end_simulation` |
| `PENDING_DIR` | `L132` | `str` (config path) | Rebound in test `setUp`/`tearDown` | `L133`, `L4171`, `L4173`, `L5719`, `L5721` | Mutated in `test_dedupguard`, `test_dupfix`, `test_fwdcache`, `test_sslretry` |
| `DOWNLOAD_DIR` | `L138` | `str` (config path) | Rebound in test `setUp`/`tearDown` | 28 sites (`L139` to `L6000`) | Mutated in `test_fwdcache`, `test_sslretry`; read in `test_dedupguard` |
| `CURL_CFFI_AVAILABLE` | `L56, 58` | `bool` (feature flag) | Set at import (`L56`/`L58`) | 9 sites (`L1712`-`L5362`) | Patched via `patch("bot.CURL_CFFI_AVAILABLE", ...)` in `test_sslretry.py` |
| `DASHBOARD_SECRET` | `L165` | `str` | Set once at import via `get_or_create_dashboard_secret()` | `L1302`, `L1312`, `L1316`, `L1371` | Function tested in `test_dedupguard.py:293,307` |
| `START_TIME` | `L140` | `float` | Set once at import via `time.time()` | `L1333`, `L3342`, `L3878`, `L3926` | None |
| `loop` | `L7, 9` | `AbstractEventLoop` | Set at import (`L7-10`); shadowed by local `loop = asyncio.get_running_loop()` in functions | `L10` | None |
| `pyrogram.utils.*_CHANNEL_ID` | `L51-52` | External module attrs | Monkeypatched at import (`MIN_CHANNEL_ID`, `MAX_CHANNEL_ID`) | Inside `pyrogram` | None |
| `OdnoklassnikiIE._parse_json` | `L71, 76` | External class method | Monkeypatched at import with `_safe_ok_parse_json` | Inside `yt_dlp` | None |

---

## 6. Load-Bearing Texts and Sentinels Register

Moving any string below without its paired producer/consumer or test assertion breaks runtime behavior or test parity.

### 6.1 Internal Sentinels, Status Pre-Fills, and Error Classifiers

| Category | Exact String / Pattern | Producer / Definition Site | Consumer / Comparison Site | Risk Lesson |
| :--- | :--- | :--- | :--- | :--- |
| Status pre-fill (`dupfix`) | `f"📤 <b>{tr(lang, 'uploading')}</b>"` (`TEXTS[*]["uploading"]`) | `run_approved_pending_upload` (`L3170`) | `process_single_local_file_upload` (`L4352`) via `safe_edit_text` | Identical consecutive `edit_text` raises `MessageNotModified`; `safe_edit_text` (`L2243`) must wrap every status edit. |
| URL fragment IPC protocol | `#ref=<url>&cookie=<sid>&title=<str>` | `extract_real_download_link_from_html` (`L1570`), `unrestrict_terabox` caller (`L1691`), `unrestrict_mega` caller (`L1706`), `DocumentaryArea` (`L1815`), `OK.ru` (`L1856`) | `unrestrict_direct_link` (`L1737-1741`), `probe_command_handler` (`L3254-3261`), `process_download_and_upload` (`L5166-5178`) | Resolvers pack `Referer`, `PHPSESSID`, and extracted title into the URL fragment; consumers split on `#` and `parse_qs`. |
| Delivery cache URL key | `(url or "").strip()` with fragment preserved | `handle_url_intake` (`L3583`), `process_download_and_upload` (`L5157`) | `db_record_delivery` (`L864`), `db_get_delivery` (`L887`), `test_fwdcache.py:362-389` | AN1 links carry version/session data in `#fragment`; stripping `#` breaks `fwdcache` isolation. |
| Stale forward error markers | `"MessageIdInvalid"`, `"message_id_invalid"`, `"message to forward not found"`, `"message id invalid"`, `"message_not_found"` | Pyrogram RPC exceptions | `is_message_not_found_error` (`L3006-3026`) -> `handle_url_intake` (`L3597`) | Only these markers delete cached delivery rows and trigger fresh download. |
| TLS cert verification markers | `"CERTIFICATE_VERIFY_FAILED"`, `"SSLCertVerificationError"`, `CurlError.code == 60` | `ssl` / `aiohttp` / `curl_cffi` exceptions | `is_cert_verification_error` (`L5077-5132`) -> `L5299, 5460, 5620` | Strictly gates the single unverified TLS retry (Section B.7). |
| TLS skipped notice | `TLS_VERIFICATION_SKIPPED_NOTICE` (`L5075`) | `bot.py:5075` | Appended at `L4331, 4405, 5803, 5874, 5949`; asserted in `test_sslretry.py:191-193, 441` | Exact bilingual line required on success card after unverified retry. |
| TLS warning log prefix | `"TLS certificate verification failed for host ..."` on logger `"bot"` | `bot.py:5301, 5462, 5622` | `test_sslretry.py:168, 196, 423, 444` (`self.assertLogs("bot", level="WARNING")`) | Logger hierarchy must remain rooted at `"bot"` and preserve warning text. |
| Forward failure warning log | `"Forward failed for delivery id=... Deleting stale row..."` on logger `"bot"` | `bot.py:3598-3601` | `test_fwdcache.py:149, 165` (`self.assertLogs("bot", level="WARNING")`) | Logger `"bot"` and substring asserted by test. |
| Queue task discriminators | `"torrent"`, `"zip_bundle"`, `"single"` | `handle_document_torrent` (`L3960`), `handle_all_messages` (`L3990, 4017, 4042`) | `handle_queued_task` (`L4047, 4050, 4053`) | Tuple tag routing on `request_queue`. |
| ZIP bundle intake sentinel | `"[ZIP]"` (case-insensitive first line) | User message | `handle_all_messages` (`L3996`: `lines[0].upper() == "[ZIP]"`) | Triggers `process_zip_bundle`. |
| Pending download statuses | `"pending"`, `"approved"`, `"done"`, `"cancelled"`, `"expired"` | `db_add_pending_download`, `callback_handler`, `cleanup_expired_pending_downloads` | `callback_handler` (`L3698-3705, 3733-3737`), `cleanup_expired_pending_downloads` (`L980`), `test_dedupguard.py`, `test_dupfix.py` | State machine strings stored in `pending_downloads.status`. |
| Dashboard HTML token | `"__SECRET_KEY__"` | `DASHBOARD_HTML_TEMPLATE` (`L1178`) | `handle_dashboard_view` (`L1312`: `.replace("__SECRET_KEY__", DASHBOARD_SECRET)`) | Injects auth key into dashboard JS polling calls. |
| Decorative icon filter | `("🌌", "⚡", "👑", "🚀", "🔥")` | `progress_bar` (`L2225`) | Suppresses legacy decorative icons in progress header | Deflair presentation guard. |
| `BLITZVERIFY` omit sentinels | `("unknown", "-", "n/a", "none")` (lowercased) | `format_blitzverify_block.is_valid_val` (`L2912, 2964, 2971`) | Omits unavailable metadata lines in `BLITZVERIFY v1` | Asserted in `test_blitzverify.py:111-134`. |
| APK bundle rule labels | `"manifest package match"`, `"base APK (...)"`, `"largest APK entry (...)"`, `"no APK entry found in bundle"` (and Arabic pairs) | `inspect_apk` (`L2589-2626`) | `format_apk_inspection_card` (`L2727`), `test_apkinspect_regression.py:60,67`, `test_dedupguard.py:326` | Asserted by regression tests. |
| Binary APK Sig Block magic | `b"APK Sig Block 42"`, `0x7109871a` (v2), `0xf05368c0` (v3) | Android APK Signing Block spec | `extract_v2_v3_cert` (`L2473, 2494, 2496`) | Binary signature extraction contract. |

### 6.2 Strings Asserted Directly by `tests/*.py`

1. **`BLITZVERIFY v1` contract (`test_blitzverify.py`, `test_fwdcache.py`, `test_nocard.py`, `test_apkinspect_regression.py`, `test_end_to_end_simulation.py`)**:
   - Exact header `"BLITZVERIFY v1"`, fenced wrapper `"```\n...\n```"`, `ParseMode.MARKDOWN`, exact ordered field labels `package:`, `version_name:`, `version_code:`, `size_bytes:`, `min_sdk:`, `target_sdk:`, `file_sha256:` (lowercase hex), `cert_sha256:` (lowercase hex), `inspected_at:` (`YYYY-MM-DD HH:MM` in `Africa/Cairo`).
   - Negative assertion across 4 test files: `"بطاقة فحص APK"` / `"🛡️ بطاقة فحص APK"` must NEVER appear in chat replies.
2. **Signer-change warning (`test_nocard.py:53-56, 225-229`)**:
   - `"⚠️ تنبيه: توقيع النسخة دي مختلف عن النسخة اللي فاتت من نفس التطبيق / Warning: this version is signed differently from the previous version of this app\n{package} ({prev_vc} → {curr_vc})"` sent with `ParseMode.DISABLED`.
3. **Duplicate warning card & buttons (`test_dedupguard.py:188-206`, `test_end_to_end_simulation.py:131`)**:
   - `"تنبيه: تم تنزيل هذا التطبيق مسبقاً بنفس الإصدار!"`, `"Warning: Duplicate APK Download Detected!"`, `"نفس شهادة التوقيع الأصلية"`, `"Same original signing certificate"`, button labels `"✅ نزّله تاني"` (`dup_go_<id>`) and `"🛑 إلغاء"` (`dup_no_<id>`).
4. **Delivery forward cache note & button (`test_fwdcache.py:117-126, 304`)**:
   - `"Forwarded your earlier download instead of re-downloading"`, `"Cairo"`, button label `"⬇️ نزّله من جديد"` (`fwd_fresh_<id>`).
5. **Upload & status messages (`test_nocard.py:332-333`, `test_end_to_end_simulation.py:78, 105`, `test_sslretry.py:255, 310, 369`)**:
   - `"جاري الرفع"`, `"تمت العملية بنجاح"`, `"Network Connection Error"`.
6. **Raw source-text assertions (`test_dashoff.py:35-54`, `test_dedupguard.py:286-289`)**:
   - `test_dashoff.py` opens `"bot.py"` directly and asserts absence of `"btn_get_dashboard"`, `"dashboard_command"`, `'BotCommand("dashboard"'`, and presence of `admin_kbd`, `async def handle_dashboard_view`, `async def handle_dashboard_stats_api`, `async def handle_dashboard_cancel_task_api`, `app.router.add_get("/dashboard", handle_dashboard_view)`, `app.router.add_get("/api/dashboard/stats", handle_dashboard_stats_api)`, and `get_or_create_dashboard_secret`.
   - `test_dedupguard.py` opens `"bot.py"` directly and asserts absence of `"eval("` and `"/eval"`.
7. **Legacy `format_apk_inspection_card` strings (`test_apkinspect_regression.py:78, 104-105, 117-118`, `test_dedupguard.py:345-359`)**:
   - `"لم يتم العثور على شهادة توقيع"`, `"✅ نفس الموقّع مثل الإصدار v..."`, `"✅ Same signer as v..."`, `"⚠️ موقّع مختلف عن الإصدار v..."`, `"⚠️ DIFFERENT signer than v..."`, `"Delivered Bundle Size:"`, `"حجم الحزمة (Bundle):"`, etc.

---

## 7. Defect and Risk Register (25 Verified Findings)

Per Hard Constraint 8, dead code and behavioral defects are **flagged with evidence here and never silently deleted or altered** during structural moves.

### Group A: Dead Code and Unused Definitions (8 Findings)

- **`DEF-01` [Dead Code, Test-Coupled]**: `format_apk_inspection_card` (`bot.py:2718-2880`, 163 lines).
  - *Zero-reference proof in `bot.py`*: AST scan confirms `0` runtime call sites in `bot.py` (`bot_ext_refs = []`, left behind by the `nocard` round).
  - *Test coupling*: Directly called in `tests/test_apkinspect_regression.py:77,102,103,115,116`, `tests/test_dedupguard.py:344,354`, and `tests/test_real_apk_inspection.py:69,75`. Must be preserved during restructure unless owner authorizes removing both the function and its unit tests.
- **`DEF-02` [Dead Code]**: `_owner_filter` (`bot.py:112-116`) and `owner_filter` (`bot.py:118`).
  - *Zero-reference proof*: `_owner_filter` is referenced only at `L118`; `owner_filter` has `0` references in `bot.py` and `0` in `tests/`. Every handler calls `is_admin(user_id)` manually instead.
- **`DEF-03` [Dead Constants]**: `ADMIN_ID = 1594244556` (`bot.py:105`), `MAX_SINGLE_FILE_SIZE` (`bot.py:123, 126`), and `SPLIT_PART_SIZE` (`bot.py:124, 127`).
  - *Zero-reference proof*: `0` read sites in `bot.py` and `0` in `tests/`. Upload functions define local `BOT_LIMIT_BYTES = 1950 * 1024 * 1024` and `SPLIT_CHUNK_BYTES = 1900 * 1024 * 1024` (`L4200-4201`, `L5752-5753`).
- **`DEF-04` [Unused Schema Artefacts]**: SQLite table `global_stats` (`bot.py:397-403`) and column `users.fast_speed` (`bot.py:374`).
  - *Evidence*: `global_stats` has `0` SQL reads or writes anywhere in `bot.py` (`db_get_global_stats` at `L1006-1016` queries `users` and `history`). `users.fast_speed` is selected in `db_get_user_settings` (`L526`) and whitelisted in `ALLOWED_USER_SETTINGS` (`L351`) with `0` consumers. Retained for schema compatibility (Section B.5).
- **`DEF-05` [Unused `TEXTS` Keys]**: 11 keys in `TEXTS["ar"]` and `TEXTS["en"]` (`bot.py:208, 230-238, 240` and `L291, 313-321, 323`) have `0` `tr(...)` call sites: `btn_lang`, `dup_warning_title`, `dup_prev_header`, `dup_prev_date`, `dup_prev_hash`, `dup_signer_match`, `dup_signer_diff`, `dup_prompt`, `btn_dup_download`, `btn_dup_cancel`, `dup_approved_notice`.
  - *Evidence*: `make_settings_keyboard` (`L2149`), `format_duplicate_warning_card` (`L3028-3075`), and `make_duplicate_keyboard` (`L3077-3085`) hardcode inline Arabic/English strings instead of calling `tr()`. Retained intact under Section B.4.
- **`DEF-06` [Unreachable Duplicate Branches]**:
  - `callback_handler` `bot.py:3901-3906` (`elif data == "btn_settings":`) is unreachable because `bot.py:3859-3865` already matches `data == "btn_settings"` and returns.
  - `callback_handler` `bot.py:3873-3875` (`if not is_admin(user_id):`) inside `btn_admin_panel` is unreachable because `bot.py:3672-3674` already rejects non-admin users at entry.
- **`DEF-07` [Orphan Callback Handler]**: `callback_handler` `bot.py:3908-3909` (`elif data == "btn_help":`) has `0` matching `InlineKeyboardButton(..., callback_data="btn_help")` definitions anywhere in `bot.py`.
- **`DEF-08` [Unused Image/Package Artefacts]**: `Dockerfile:7-8` installs `git` and `aria2`, neither invoked in `bot.py`; `requirements.txt:3` pins `pycryptodome==3.23.0`, never imported in `bot.py`; project root contains unused local session file `bot_session.session` alongside active `downloader_bot.session`.

### Group B: Section A (No Silent Failures) Violations (8 Findings)

- **`DEF-09` [Section A.1 & A.2: Stuck Status on Forward Error]**: In `handle_url_intake` (`bot.py:3590-3606`), if `forward_messages` raises any error not matched by `is_message_not_found_error` (such as `FloodWait`, `ChatForwardsRestricted`, or transient `RPCError`), `L3606` re-raises `fwd_err` into `handle_queued_task` (`bot.py:4056-4057`), which logs `Task error` and never updates `status_msg`. The owner's chat message stays permanently frozen at `"⏳ جاري معالجة الرابط... / Processing link..."` with no failure explanation.
- **`DEF-10` [Section A.1, A.2 & A.3: Upload Cancel Button Does Not Stop Upload]**: Pressing `cancel_<task_id>` (`bot.py:3678-3682`) sets `ACTIVE_TASKS[task_id]["cancelled"] = True` and shows `"🛑 Task cancelled / تم الإلغاء..."`. However, during an active Pyrogram upload (`resilient_send_media` called from `L4237, 4368, 5787, 5913`), `pyrogram_progress` either returns `None` without calling `client.stop_transmission()` (`L4222, 5772, 5893`) or in `process_single_local_file_upload` (`L4356-4357`) does not even check `cancelled`. Upload continues to 100%, delivers the file, records history/delivery, and posts `"✅ تمت العملية بنجاح"`.
- **`DEF-11` [Section A.2: Split Upload Cancel Leaves Stuck "Splitting..." Status]**: In `process_single_local_file_upload` (`bot.py:4303-4304`) and `process_download_and_upload` (`bot.py:5843-5844`), cancelling mid-split executes bare `return` without editing `status_msg` to report cancellation, leaving `"✂️ تقسيم الملف إلى N أجزاء..."` permanently displayed.
- **`DEF-12` [Section A.1 & A.4: `process_zip_bundle` Silent Drops and Corrupt HTML Entries]**: In `process_zip_bundle` (`bot.py:4451-4498`), the `CurlAsyncSession` branch (`L4454-4468`) neither checks `resp.status_code == 200` nor calls `is_valid_binary_file`, silently zipping 403/404 HTML error pages as files; the `aiohttp` branch (`L4474`) silently skips non-200 URLs with zero log line and zero user notice (and uploads a 0-file ZIP as a success if every URL fails). It also omits `db_add_history` and >1.95 GiB split checks.
- **`DEF-13` [Section A.1: `/probe` Reports `OK` on HTTP Error Codes]**: `probe_command_handler` (`bot.py:3307`) formats `f"🌐 <b>HTTP Code:</b> <code>{status} OK</code>\n"` unconditionally, reporting `404 OK` / `403 OK` / `500 OK` on broken URLs.
- **`DEF-14` [Section A.1 & A.2: `/brand @channel` Displays Hardcoded State]**: `brand_command_handler` (`bot.py:3542-3551`) updates only `channel_tag`, but replies with hardcoded lines claiming `الموضع: في النهاية (Suffix)`, `الزر التفاعلي: مفعل ✅`, and `الكابشن: مفعل ✅` even when the user's DB settings have disabled caption/button or set `prefix`/`none`.
- **`DEF-15` [Section A.4: Silent Drops & Expired Pending Status Overwrite]**:
  - `handle_all_messages` (`bot.py:3973-3975`) silently drops messages older than 300s without a log line or reply; `handle_document_torrent` (`bot.py:3957`) silently ignores non-`.torrent` documents.
  - `callback_handler` (`bot.py:3729-3751`, `dup_no_`) lacks the `if row["status"] == "expired":` guard present in `dup_go_` (`L3704-3706`), overwriting `'expired'` rows to `'cancelled'` and displaying the cancellation confirmation instead of `dup_expired_alert`.
  - `run_fresh_download` (`bot.py:3647-3665`, spawned via `asyncio.create_task` at `L3773`) has no error wrapper to update `status_msg` if lookup fails (`L3649`) after `status_msg` was created (`L3769`).
- **`DEF-16` [Section A.1 & A.4: Silent Failure if `BLITZVERIFY` Reply Fails]**: `handle_apk_inspection_card` (`bot.py:3128-3139`) catches all exceptions (including `FloodWait` without sleep/retry) when sending the signer warning or `BLITZVERIFY v1` block, logs `"BLITZVERIFY block send failed"` / `"APK inspection card failed silently"`, and sends no error notice to the owner.

### Group C: Presentation Standard / Anti-Slop Survivors (Section D) (3 Findings)

- **`DEF-17` [Web Surface Boast Text]**: `handle_health_check` (`bot.py:1032`) returns `"⚡ OMNIPOTENT OVERLORD ENGINE - ABSOLUTE POWER 100%"`, and `DASHBOARD_HTML_TEMPLATE` (`bot.py:1039, 1096`) renders `"⚡ OMNIPOTENT OVERLORD | Live Monitor & Dashboard"` and `"OMNIPOTENT OVERLORD ENGINE"`.
- **`DEF-18` [Log Banners & Frozen Legacy Identifiers]**: Startup/web logs (`bot.py:1389, 6040, 6048-6049, 6056`) and comment `L85` retain `"OMNIPOTENT OVERLORD ENGINE"` / `"OMNIPOTENT BILINGUAL ENGINE ACTIVATED!"`. (Identifiers `/omnipotent`, `/god`, `/godmode`, `TEXTS[*]["god_panel"]`, and `btn_god_panel` are frozen external contracts under Section B.2-B.4; their visible `TEXTS` values were already cleaned to `"لوحة التحكم"` / `"Control Panel"`.)
- **`DEF-19` [Dash Codepoints in Monolith]**: Dead function `format_apk_inspection_card` (`bot.py:2868, 2870`) contains literal `\u2014` characters; `extract_video_embed_from_html` (`bot.py:1490`) uses `\u2013` and `\u2014` inside regex `r'[-|...]'` to split scraped `<title>` strings. Zero active user-facing Telegram strings contain `\u2013` or `\u2014`.

### Group D: Duplicated Logic Blocks and Structural Hazards (6 Findings)

- **`DEF-20` [~260-Line Duplicated Upload Pipeline with Behavioral Drift]**: `process_single_local_file_upload` (`bot.py:4159-4424`) and `process_download_and_upload` (`bot.py:5706-5961`) duplicate APK duplicate detection, >1.95 GiB Premium upload, 1.90 GiB file splitting, <=1.95 GiB upload, `CHANNEL_ID` mirror, DB recording, and post-upload messaging, with 4 behavioral drifts:
  1. `L4175-4188` hardcodes `flow_type="torrent"` and omits `url_key=url_key` when staging a duplicate APK.
  2. `L4261-4269` omits `TLS_VERIFICATION_SKIPPED_NOTICE` on the Premium success card.
  3. `L4352, L4356` omits `make_cancel_keyboard` and `cancelled` checks on normal upload.
  4. `L4136-4424` has no `finally: ACTIVE_TASKS.pop(task_id, None)`.
- **`DEF-21` [854-Line Orchestrator & Internal Code Duplication]**: `process_download_and_upload` (`bot.py:5134-5987`, 854 lines) and `callback_handler` (`bot.py:3668-3943`, 276 lines) concentrate high cyclomatic complexity. Inside `process_download_and_upload`, the throttled turbo probe (`L5255-5350`) and the `curl_cffi` stream loop (`L5379-5550`) each copy-paste ~55-75 lines verbatim for their unverified TLS retry branch, and `_perform_aiohttp_download` (`L5563-5615`) mutates 6 outer variables via `nonlocal`.
- **`DEF-22` [4-Way Duplicated Fragment/Referer & HTTP Client Logic]**: `#ref`/`#cookie`/`#title` parsing, AN1 Referer selection, and dual `CurlAsyncSession`/`aiohttp` request branches are repeated across `unrestrict_direct_link` (`L1734-1770`), `probe_command_handler` (`L3252-3298`), `process_zip_bundle` (`L4448-4489`), and `process_download_and_upload` (`L5163-5189`).
- **`DEF-23` [Permanent `ACTIVE_TASKS` Leak on Approved Duplicate Upload]**: `run_approved_pending_upload` (`bot.py:3174`) inserts `ACTIVE_TASKS[task_id] = {"cancelled": False}` and never removes `task_id` on completion or error, leaking an `"Active Job"` entry into `ACTIVE_TASKS` and `/api/dashboard/stats` for the lifetime of the container.
- **`DEF-24` [Import-Time Side Effects & Concurrent Torrent Race]**:
  - `import bot` immediately runs `load_dotenv()`, creates directories, opens SQLite twice (`get_or_create_dashboard_secret` at `L165` runs before `init_db` sets `WAL` mode at `L360` / `L1023`), creates `asyncio.Queue()`, and binds `Client(..., workdir=DATA_DIR)`.
  - `process_torrent_download` (`L4115-4119`) collects completed files by `os.walk(DOWNLOAD_DIR)` where `mtime >= start_time`, which can cross-contaminate files if two tasks download concurrently in `DOWNLOAD_DIR`.
- **`DEF-25` [Implied-by-Accident Behaviors & Missing `.dockerignore`]**:
  1. *Handler registration order*: `handle_all_messages` (`L3965`) matches all text messages and returns on `text.startswith("/")` (`L3981`); registering it before `L3203-3566` would silently swallow all 30 bot commands.
  2. *Non-serial queue worker*: `queue_worker` (`L4062-4065`) spawns `asyncio.create_task` immediately per `request_queue.get()`, so tasks execute concurrently while `handle_all_messages` (`L4028`) computes queue positions from `request_queue.qsize()`.
  3. *Unconditional `ssl=False` outside main probe*: `unrestrict_terabox` (`L1614`), `unrestrict_1fichier` (`L1648`), `unrestrict_mega` (`L1667`), `download_multi_stream_turbo` (`L4600, 4668`), `get_ok_direct_mp4` (`L4720, 4766`), and `yt-dlp` (`L4904`) always skip certificate verification without setting `ssl_unverified`.
  4. *Missing `.dockerignore`*: `Dockerfile:19` (`COPY . .`) has no `.dockerignore` guard against copying local `.env`, `*.db`, `*.session`, `pending_downloads/`, or `tests_apk/SuperTuxKart-1.5.apk` (183.7 MB).
