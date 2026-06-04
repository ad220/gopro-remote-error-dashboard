# CLAUDE.md -- Project guidelines for AI coding sessions

## What this project is

A self-hosted error reporting system for the **GoPro Remote for Garmin** ConnectIQ widget.
The Garmin watch app collects 32-bit error codes in `ErrorManager.errorQueue` and POSTs
them here. An admin UI (local-network only) lets the developer inspect, filter, and sort reports.


## Repo layout

```
.
├── .gitignore
├── CLAUDE.md
├── backend
│   ├── README.md
│   ├── requirements.txt
│   └── src
│       ├── api.py                    FastAPI app -- all routes, parsing logic, decoding tables
│       ├── database.py               SQLAlchemy models + init_db()
│       ├── main.py                   Starts the FastAPI app
│       └── seed_reports.py           Dev script: creates API keys and sends 200 realistic reports
└── frontend
    ├── index.html
    ├── package.json
    ├── src
    │   ├── App.vue                   Sidebar shell, section switching (no vue-router)
    │   ├── api.js                    Thin fetch wrapper; all endpoint calls in one place
    │   ├── components
    │   │   ├── ErrorGrid.vue         Filterable / sortable / paginated table
    │   │   ├── StatCard.vue          Aggregated cards + version/category filters
    │   │   ├── StatsPanel.vue        Reusable breakdown card with mini bar
    │   │   └── VersionManager.vue    API key CRUD
    │   ├── main.js
    │   └── style.css                 @import "tailwindcss" + @theme tokens (--color-accent, etc.)
    └── vite.config.js                Tailwind v4 plugin + /admin proxy → localhost:8000
```

## Setting up and run the project

```bash
# Backend

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python src/seed_reports.py # optional
python src/main.py


# Frontend
cd ../frontend
npm install

npm run dev
```

## Error code bit layout

This is the most domain-specific part of the codebase. Source of truth is `ErrorManager.mc`.

```
| 31-30 BF | 29-24 GP ID | 23-16 EC byte | 15-0 data |
```

| Field  | Bits  | Notes |
|--------|-------|-------|
| BF     | 31-30 | Build flags: `00`=ble, `01`=mobile_highend, `11`=mobile_lowend |
| GP ID  | 29-24 | Index into `goproModelTable` (see `CameraDelegate.mc`) |
| EC     | 23-16 | Error category byte -- see below |
| data   | 15-0  | 16-bit context payload; data0 = bits 7-0, data1 = bits 15-8 |

### EC byte -- critical: ERR_CAM and ERR_MSG are bit masks, not fixed values

```
ERR_CAM  = 0x80   ← bit 7; sub-codes also OR'd into EC byte
ERR_MSG  = 0x40   ← bit 6; sub-codes also OR'd into EC byte
ERR_EXT  = 0x30   ← exact
ERR_COMM = 0x20   ← exact; sub-codes live in data0 instead
ERR_SYS  = 0x10   ← exact
ERR_NULL = 0x00   ← exact
```

**Detection must use bit-masking**, not dict lookup:
```python
if   ec_byte & 0x80: category = 0x80   # ERR_CAM
elif ec_byte & 0x40: category = 0x40   # ERR_MSG
else:                category = ec_byte # exact for the rest
```

`0x97` = `ERR_CAM | SUB_CAM_VAL(0x10) | extra(0x07)` → category = ERR_CAM, subtype = 0x17.
Storing the raw EC byte (0x97) as the category is a bug -- it would break grouping and filtering.

### Sub-type extraction

| Category | Formula | Named constants (from ErrorManager.mc) |
|----------|---------|----------------------------------------|
| ERR_CAM  | `ec_byte & 0x7F` | SUB_CAM_ID=0x00, VAL=0x10, NULL=0x20, AVAIL=0x30 (bits 5-4); bits 3-0 are extra context |
| ERR_MSG  | `ec_byte & 0x3F` | SUB_MSG_STATUS=0x00, QUERY=0x10, STRUCT=0x20 (bits 5-4); bits 3-0 are extra context |
| ERR_COMM | `data & 0xF0`    | SUB_BLE_STATUS=0x00, CONN=0x10, NULLQ=0x40, BADSCD=0x80, WRITE=0x90, TO=0xA0, API=0xF0 |
| others   | `None`           | No sub-type defined |

When labelling CAM/MSG subtypes, mask to `subtype & 0x30` to get the named code,
then show `+N` suffix if `subtype & 0x0F` is non-zero (e.g. `CAM_VAL+7`).


## Database schema -- what is stored vs derived

```
ErrorReport:
  id, timestamp, version          -- always stored
  error_code                      -- raw 32-bit int; source of truth
  build_flags, gopro_id           -- extracted for sorting/filtering
  error_category                  -- normalised base mask (0x80 for ALL ERR_CAM)
  error_subtype                   -- see table above; NULL for ERR_SYS/NULL/EXT

NOT stored (derived from error_code in _enrich()):
  error_hex, error_data, gopro_model, error_subtype_label
```

`device` (Garmin watch model) is **not available** from the ConnectIQ API and is intentionally absent.


## Backend conventions

- All admin routes live in the `admin = APIRouter(prefix="/admin")` with `require_local` as a
  router-level dependency -- do not add it per-endpoint.
- `_parse(code)` → what gets stored. `_enrich(row)` → what gets returned to the client.
  Keep derived fields out of `_parse`.
- `_apply_category_filter(q, str)` is the shared helper for filtering by category in both
  `/admin/errors` and `/admin/stats`. Always use it instead of inline filter logic.
- Stats queries must use `q.with_entities(...)` on the already-filtered base query `q`,
  not a fresh `db.query(...)`.
- The DB is SQLite. No migrations tooling -- `init_db()` calls `create_all()` on startup.
  Schema changes require dropping and recreating the DB during development.


## Frontend conventions

- **No vue-router.** Section switching is `v-if` in `App.vue`. Add sections there.
- **Tailwind v4.** Use `@reference "../style.css"` at the top of any `<style scoped>` block
  that uses `@apply`, or the build will fail silently with missing utilities.
- Custom theme tokens are in `src/style.css` under `@theme` (`--color-accent`, etc.).
  Use `text-accent`, `bg-accent` etc. in templates.
- `api.js` is the only place that calls `fetch`. Keep all endpoint logic there.
- Filter state in components uses `reactive({})`. Use explicit `watch` with `{ immediate: true }`
  rather than `watchEffect` to avoid double-fetch on multi-field filter resets.
- The Vite dev server proxies `/admin/*` to `http://localhost:8000`. Production build outputs
  to `../static/` and is served by FastAPI's `StaticFiles` mount.


## Key decisions (don't revisit without good reason)

- **API key per app version**, not per device. One key is baked into each build.
- **Admin is local-network only** -- no auth, no HTTPS required. The check is in
  `require_local()` via `ipaddress` -- private ranges + `127.0.0.0/8`.
- **`error_category` stores the normalised base mask**, not the raw EC byte. This is
  intentional: it makes `GROUP BY` and `WHERE error_category = 0x80` work correctly
  across all ERR_CAM variants. The raw EC byte is always recoverable from `error_code`.
- **No `device` field** -- not accessible from the ConnectIQ API.


## Known Monkey C quirk (for reference)

In `ErrorManager.mc`, the expression `0x3F & goproId.toNumber() << 24` should probably be
`(0x3F & goproId.toNumber()) << 24`. Due to operator precedence, the current form evaluates
as `0x3F & (goproId << 24)`, which is always 0 for IDs ≥ 1.  The test suite in the Garmin
project was written assuming the "correct" form, so the stored gopro_id values in this backend
are extracted as `(code >> 24) & 0x3F`, which matches what the tests expect.


## Adding a new feature -- checklist

- **New filter on errors grid**: add param to `list_errors`, add to `_SORTABLE` if sortable,
  add column to `ErrorGrid.vue` columns array, add `<select>` to filter bar.
- **New stat breakdown**: add `_group(ErrorReport.new_col, ...)` in `get_stats`, add a
  `<StatCard>` in `StatsPanel.vue`.
- **New error category sub-code**: add to `SUBTYPE_LABELS` in `main.py` and update the
  corresponding block in `seed_reports.py`.
- **Schema change**: add column to `database.py`, add to `_parse()` insert, add to `_enrich()`
  if it should be returned, drop and recreate the DB.

## Dashes syntax

In this project, whether in code, comments, or documentation, never use em dashes ("—" or "–"), always use simple or in extreme cases double dash ("-" or "--")
