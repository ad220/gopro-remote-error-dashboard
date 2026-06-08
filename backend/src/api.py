"""
GoPro Remote -- error reporting backend
"""
import ipaddress
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import ApiKey, ErrorReport, SessionLocal, init_db

# ---------------------------------------------------------------------------
# Error-code decoding tables (mirrors ErrorManager.mc / CameraDelegate.mc)
# ---------------------------------------------------------------------------

# Index i corresponds to gopro_id value i stored in the DB, ordered the same
# as goproModelString in CameraDelegate.mc.
GOPRO_MODEL_NAMES: list[str] = [
    "Unknown",
    "HERO4 Silver",       # id 12
    "HERO4 Black",        # id 13
    "HERO5 Black",        # id 19
    "HERO5 Session",      # id 21
    "Fusion",             # id 22
    "HERO6 Black",        # id 24
    "HERO7 Black",        # id 30
    "HERO7 White",        # id 32
    "HERO7 Silver",       # id 33
    "HERO 2018",          # id 34
    "HERO8 Black",        # id 50
    "MAX",                # id 51
    "HERO9 Black",        # id 55
    "HERO10 Black",       # id 57
    "HERO11 Black",       # id 58
    "HERO11 Black Mini",  # id 60
    "HERO12 Black",       # id 62
    "MAX2",               # id 64
    "HERO13 Black",       # id 65
    "HERO (2024)",        # id 66
    "HERO Lit",           # id 70
]

BUILD_FLAGS: dict[int, str] = {
    0b00: "ble",
    0b01: "mobile_highend",
    0b11: "mobile_lowend",
}

# Normalised EC byte → category name.
# ERR_CAM (0x80) and ERR_MSG (0x40) are detected via bit-mask, not exact match,
# because their sub-codes are OR'd into the same EC byte (see _category()).
ERROR_CATEGORIES: dict[int, str] = {
    0x80: "ERR_CAM",
    0x40: "ERR_MSG",
    0x30: "ERR_EXT",
    0x20: "ERR_COMM",
    0x10: "ERR_SYS",
    0x00: "ERR_NULL",
}

# Human labels for sub-type values, keyed by normalised category.
#
# ERR_CAM  subtype = ec_byte & 0x7F  →  SUB_CAM_* lives in bits 5-4,
#                                       bits 3-0 are extra context.
# ERR_MSG  subtype = ec_byte & 0x3F  →  SUB_MSG_* lives in bits 5-4,
#                                       bits 3-0 are extra context.
# ERR_COMM subtype = data   & 0xF0   →  direct match to SUB_BLE_* constants.
SUBTYPE_LABELS: dict[int, dict[int, str]] = {
    0x80: {
        0x00: "CAM_ID",
        0x10: "CAM_VAL",
        0x20: "CAM_NULL",
        0x30: "CAM_AVAIL",
    },
    0x40: {
        0x00: "MSG_STATUS",
        0x10: "MSG_QUERY",
        0x20: "MSG_STRUCT",
    },
    0x20: {
        0x00: "BLE_STATUS",
        0x10: "BLE_CONN",
        0x40: "BLE_NULLQ",
        0x80: "BLE_BADSCD",
        0x90: "BLE_WRITE",
        0xA0: "BLE_TO",
        0xF0: "BLE_API",
    },
}

# ---------------------------------------------------------------------------
# Local-network guard
# ---------------------------------------------------------------------------

_PRIVATE_NETS = [
    ipaddress.ip_network("10.8.0.0/24"),
    ipaddress.ip_network("192.168.1.0/24"),
    ipaddress.ip_network("127.0.0.0/24"),
]


def _is_local(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETS)
    except ValueError:
        # "testclient" is the synthetic hostname used by Starlette's TestClient
        return ip == "testclient"


def require_local(request: Request) -> None:
    if not _is_local(request.client.host):
        raise HTTPException(
            status_code=403,
            detail="Admin access is restricted to the local network",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Error-code parsing
# ---------------------------------------------------------------------------

def _category(ec_byte: int) -> int:
    """
    Return the normalised category stored in the DB.

    ERR_CAM (0x80) and ERR_MSG (0x40) act as bit-masks: their sub-codes are
    also shifted to bits 23-16 and OR'd in, so the EC byte looks like e.g.
    0x97 = ERR_CAM | SUB_CAM_VAL | 0x07.  We detect them with bit-tests so
    that any EC byte with bit 7 set maps to ERR_CAM, bit 6 to ERR_MSG, etc.
    The remaining categories have fixed, non-overlapping EC bytes.
    """
    if ec_byte & 0x80:
        return 0x80   # ERR_CAM
    if ec_byte & 0x40:
        return 0x40   # ERR_MSG
    return ec_byte    # ERR_COMM/SYS/NULL/EXT -- exact value


def _subtype(category: int, ec_byte: int, data: int) -> int | None:
    """
    Extract the sub-type value for the three categories that define one.

    ERR_CAM / ERR_MSG: remaining EC bits after the category mask.
      The named SUB_* constant occupies bits 5-4; bits 3-0 are extra context.
    ERR_COMM: upper nibble of data0 (bits 7-4), matching SUB_BLE_* constants.
    """
    if category == 0x80:
        return ec_byte & 0x70
    if category == 0x40:
        return ec_byte & 0x30
    if category == 0x20:
        return data & 0xF0
    return None


def _subtype_label(category: int, subtype: int | None) -> str | None:
    if subtype is None:
        return None
    labels = SUBTYPE_LABELS.get(category, {})
    return labels.get(subtype, f"0x{subtype:02X}")



def _index(category: int, ec_byte: int, data: int) -> int | None:
    if category in (0x80, 0x40):
        return ec_byte & 0x0F
    if category in (0x20, 0x10):
        return data & 0x0F
    if category == 0x00:
        return data & 0xFF
    return None


def _parse(code: int) -> dict:
    build_flags = (code >> 30) & 0x3
    gopro_id    = (code >> 24) & 0x3F
    ec_byte     = (code >> 16) & 0xFF
    data        = code & 0xFFFF

    category = _category(ec_byte)

    return {
        "build_flags":      build_flags,
        "gopro_id":         gopro_id,
        "error_category":   category,
        "error_subtype":    _subtype(category, ec_byte, data),
        "error_index":      _index(category, ec_byte, data),
    }


def _subtype_label(category: int, subtype: int | None) -> str | None:
    if subtype is None:
        return None
    labels = SUBTYPE_LABELS.get(category, {})
    if category in (0x80, 0x40):
        # Named sub-code is in bits 5-4; bits 3-0 are extra context
        base  = subtype & 0x30
        extra = subtype & 0x0F
        name  = labels.get(base, f"0x{subtype:02X}")
        return f"{name}+{extra:X}" if extra else name
    # ERR_COMM: direct match
    return labels.get(subtype, f"0x{subtype:02X}")


def _enrich(e: ErrorReport) -> dict:
    code = e.error_code
    return {
        "id":               e.id,
        "timestamp":        e.timestamp.isoformat(),
        "version":          e.version,
        "error_hex":        f"0x{(code >> 16) & 0xFFFF:04X}_{code & 0xFFFF:04X}",
        "build_flags":      e.build_flags,
        "gopro_id":         e.gopro_id or 0,
        "error_category":   e.error_category or 0,
        "error_subtype":    e.error_subtype,
        "error_index":      e.error_index,
        "batch_id":         e.batch_id,
    }


# ---------------------------------------------------------------------------
# Shared filter helper
# ---------------------------------------------------------------------------

def _apply_category_filter(q, error_category: str):
    """
    Filter a query by error category name (e.g. "ERR_CAM") or raw hex ("0x80").
    Works correctly after normalisation: all ERR_CAM rows share error_category=0x80.
    """
    cat_raw = next(
        (k for k, v in ERROR_CATEGORIES.items() if v == error_category), None
    )
    if cat_raw is None:
        try:
            cat_raw = int(error_category, 16)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Unknown error_category: {error_category!r}"
            )
    return q.filter(ErrorReport.error_category == cat_raw)


# ---------------------------------------------------------------------------
# App & routers
# ---------------------------------------------------------------------------

app = FastAPI(title="GPRMT - Error dashboard")
init_db()

# All /admin routes share the local-network dependency
admin = APIRouter(prefix="/admin", dependencies=[Depends(require_local)])

_SORTABLE = {
    "timestamp":        ErrorReport.timestamp,
    "version":          ErrorReport.version,
    "error_category":   ErrorReport.error_category,
    "error_subtype":    ErrorReport.error_subtype,
    "error_index":      ErrorReport.error_index,
    "gopro_id":         ErrorReport.gopro_id,
    "build_flags":      ErrorReport.build_flags,
    "batch_id":         ErrorReport.batch_id,
}

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ReportBody(BaseModel):
    errors: list[int] = Field(..., description="32-bit error codes from ErrorManager.errorQueue")


class VersionCreate(BaseModel):
    version: str = Field(..., max_length=32, description="Human label, e.g. 'v4.1'")


# ---------------------------------------------------------------------------
# Public endpoint -- callable from any network, authenticated by API key
# ---------------------------------------------------------------------------

@app.post("/report", summary="Submit error codes from the watch")
async def report_errors(
    request: Request,
    body: ReportBody,
    db: Session = Depends(get_db),
):
    raw_key = request.headers.get("X-API-Key", "")
    key_record = (
        db.query(ApiKey)
        .filter(ApiKey.key == raw_key, ApiKey.active == 1)
        .first()
    )
    if not key_record:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")

    next_batch = (db.query(func.max(ErrorReport.batch_id)).scalar() or 0) + 1
    for code in body.errors:
        p = _parse(code)
        db.add(ErrorReport(
            version         = key_record.version,
            error_code      = code,
            build_flags     = p["build_flags"],
            gopro_id        = p["gopro_id"],
            error_category  = p["error_category"],
            error_subtype   = p["error_subtype"],
            error_index     = p["error_index"],
            batch_id        = next_batch,
        ))

    db.commit()


# ---------------------------------------------------------------------------
# Admin -- errors grid
# ---------------------------------------------------------------------------

@admin.get("/errors", summary="Paginated, filterable error list")
async def list_errors(
    db:             Session = Depends(get_db),
    sort_by:        str = "timestamp",
    order:          str = "desc",
    version:        Optional[str] = None,
    error_category: Optional[str] = None,
    error_subtype:  Optional[int] = None,
    gopro_id:       Optional[int] = None,
    batch_id:       Optional[int] = None,
    limit:          int = 100,
    offset:         int = 0,
):
    q = db.query(ErrorReport)

    if version:
        q = q.filter(ErrorReport.version == version)
    if error_category:
        q = _apply_category_filter(q, error_category)
    if error_subtype is not None:
        q = q.filter(ErrorReport.error_subtype == error_subtype)
    if gopro_id is not None:
        q = q.filter(ErrorReport.gopro_id == gopro_id)
    if batch_id is not None:
        q = q.filter(ErrorReport.batch_id == batch_id)

    col = _SORTABLE.get(sort_by, ErrorReport.timestamp)
    q = q.order_by(col.desc() if order == "desc" else col.asc())

    total = q.count()
    rows  = q.offset(offset).limit(limit).all()

    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "errors": [_enrich(e) for e in rows],
    }


# ---------------------------------------------------------------------------
# Admin -- stats (with optional filters)
# ---------------------------------------------------------------------------

@admin.get("/stats", summary="Aggregated counts for dashboard widgets")
async def get_stats(
    db: Session = Depends(get_db),
    version:        Optional[str] = None,
    error_category: Optional[str] = None,
):
    q = db.query(ErrorReport)

    if version:
        q = q.filter(ErrorReport.version == version)
    if error_category:
        q = _apply_category_filter(q, error_category)

    total = q.with_entities(func.count(ErrorReport.id)).scalar()

    def _group(col, label_fn=None):
        rows = db.query(col, func.count(ErrorReport.id)).group_by(col).all()
        return {(label_fn(k) if label_fn else k): v for k, v in rows}

    return {
        "total_reports":     total,
        "by_version":        _group(ErrorReport.version),
        "by_error_category": _group(
            ErrorReport.error_category,
            lambda k: ERROR_CATEGORIES.get(k, f"0x{k:02X}"),
        ),
        "by_gopro_model": _group(
            ErrorReport.gopro_id,
            lambda k: GOPRO_MODEL_NAMES[k] if 0 <= k < len(GOPRO_MODEL_NAMES) else f"id:{k}",
        ),
        "by_build_flags": _group(
            ErrorReport.build_flags,
            lambda k: BUILD_FLAGS.get(k, f"0b{k:02b}"),
        ),
    }


# ---------------------------------------------------------------------------
# Admin -- API key management
# ---------------------------------------------------------------------------

@admin.get("/versions", summary="List all version API keys")
async def list_versions(db: Session = Depends(get_db)):
    keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    return [
        {
            "id":         k.id,
            "version":    k.version,
            "key":        k.key,
            "created_at": k.created_at.isoformat(),
            "active":     bool(k.active),
        }
        for k in keys
    ]


@admin.post("/versions", status_code=201, summary="Generate an API key for a new app version")
async def create_version(body: VersionCreate, db: Session = Depends(get_db)):
    key = secrets.token_hex(32)  # 256-bit token
    record = ApiKey(key=key, version=body.version)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id":         record.id,
        "version":    record.version,
        "key":        key,          # shown only once -- store it now
        "created_at": record.created_at.isoformat(),
    }


@admin.delete("/versions/{version_id}", status_code=204, summary="Revoke an API key")
async def revoke_version(version_id: int, db: Session = Depends(get_db)):
    record = db.query(ApiKey).filter(ApiKey.id == version_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Version not found")
    record.active = 0
    db.commit()


# Mount admin router
app.include_router(admin)
