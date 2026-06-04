# GoPro Remote — Error Reporting Server

FastAPI backend that receives anonymous error reports from the Garmin widget and exposes an admin API for inspection.

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

The SQLite database `gopro_errors.db` is created automatically on first run.
Interactive API docs are available at `http://localhost:8000/docs`.

---

## Public endpoint

### `POST /report`

Called by the Garmin widget when it has errors to flush. Accessible from any network; protected by a per-version API key.

**Headers**
```
X-API-Key: <key>
```

**Body**
```json
{
  "errors": [268566773, 276889735]
}
```

`errors` is the full contents of `ErrorManager.errorQueue` — a list of raw 32-bit codes.

**Response** `204 No Content`

---

## Admin endpoints

All `/admin/*` routes return `403` for requests originating outside the local network (RFC 1918 + loopback).

### `GET /admin/errors`

Returns a paginated, filterable list of every stored error.

| Query param      | Type   | Default     | Description |
|------------------|--------|-------------|-------------|
| `sort_by`        | string | `timestamp` | `timestamp`, `version`, `error_category`, `gopro_id`, `build_flags` |
| `order`          | string | `desc`      | `asc` or `desc` |
| `version`        | string | —           | Filter by app version, e.g. `v4.1` |
| `error_category` | string | —           | `ERR_CAM`, `ERR_COMM`, `ERR_SYS`, `ERR_MSG`, `ERR_EXT`, `ERR_NULL`, or raw hex `0x20` |
| `gopro_id`       | int    | —           | Filter by GoPro model index (0–21) |
| `limit`          | int    | `100`       | |
| `offset`         | int    | `0`         | |

Each error in the response includes fields derived on the fly from the stored raw code:

```json
{
  "id": 1,
  "timestamp": "2025-06-03T12:00:00",
  "version": "v4.1",
  "error_code": "0x102000F5",
  "error_hex": "0x1020_00F5",
  "build_flags": "ble",
  "gopro_id": 16,
  "gopro_model": "HERO11 Black Mini",
  "error_category": "ERR_COMM",
  "error_data": "0x00F5"
}
```

`error_hex`, `gopro_model`, and `error_data` are not stored in the database — they are derived from `error_code` at read time.

### `GET /admin/stats`

Aggregated counts grouped by version, error category, GoPro model, and build flags.

### `GET /admin/versions`

Lists all API keys (including revoked ones).

### `POST /admin/versions`

Creates an API key for a new app version. The raw key is shown only in this response — save it before distributing the build.

```json
{ "version": "v4.2" }
```

### `DELETE /admin/versions/{id}`

Revokes an API key. Existing reports from that key are retained.

---

## Error code bit layout

From `ErrorManager.mc`:

```
| 31–30 BF | 29–24 GP ID | 23–16 EC | 15–0 data |
```

| Field | Bits  | Stored | Values |
|-------|-------|--------|--------|
| BF    | 31–30 | yes    | `00`=ble, `01`=mobile_highend, `11`=mobile_lowend |
| GP ID | 29–24 | yes    | Index into `goproModelTable` in `CameraDelegate.mc` |
| EC    | 23–16 | yes    | `0x80`=ERR_CAM, `0x40`=ERR_MSG, `0x20`=ERR_COMM, `0x10`=ERR_SYS, `0x00`=ERR_NULL |
| data  | 15–0  | no     | Context-specific payload, derivable from the raw `error_code` |

---

## Integrating the Garmin widget

A minimal report flush in Monkey C (to add to `ErrorManager` or the app's `onStop`):

```monkeyc
function flushErrors() as Void {
    if (errorQueue.isEmpty()) { return; }

    Communications.makeWebRequest(
        "https://your-server/report",
        {"errors" => errorQueue},
        {
            :method       => Communications.HTTP_REQUEST_METHOD_POST,
            :headers      => {"X-API-Key" => YOUR_API_KEY},
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        },
        null  // fire-and-forget
    );
}
```
