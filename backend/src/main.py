"""
GoPro Remote — error reporting backend
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

# EC byte (bits 23–16) → category name
ERROR_CATEGORIES: dict[int, str] = {
    0x80: "ERR_CAM",
    0x40: "ERR_MSG",
    0x30: "ERR_EXT",
    0x20: "ERR_COMM",
    0x10: "ERR_SYS",
    0x00: "ERR_NULL",
}

# ---------------------------------------------------------------------------
# Local-network guard
# ---------------------------------------------------------------------------

_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
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
        raise HTTPException(status_code=403, detail="Admin access is restricted to the local network")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse(code: int) -> dict:
    """
    Decode a 32-bit error code produced by ErrorManager.raise().

    Bit layout (from ErrorManager.mc):
      31–30  BF      build flags
      29–24  GP ID   GoPro model index (6 bits)
      23–16  EC      error category byte
      15– 0  data    16-bit context payload (not stored, derivable from error_code)
    """
    return {
        "build_flags":    (code >> 30) & 0x3,
        "gopro_id":       (code >> 24) & 0x3F,
        "error_category": (code >> 16) & 0xFF,
    }


def _enrich(e: ErrorReport) -> dict:
    gid = e.gopro_id or 0
    code = e.error_code
    return {
        "id":             e.id,
        "timestamp":      e.timestamp.isoformat(),
        "version":        e.version,
        "error_code":     f"0x{code:08X}",
        "error_hex":      f"0x{(code >> 16) & 0xFFFF:04X}_{code & 0xFFFF:04X}",
        "build_flags":    BUILD_FLAGS.get(e.build_flags, f"0b{e.build_flags:02b}"),
        "gopro_id":       e.gopro_id,
        "gopro_model":    GOPRO_MODEL_NAMES[gid] if gid < len(GOPRO_MODEL_NAMES) else f"id:{gid}",
        "error_category": ERROR_CATEGORIES.get(e.error_category, f"0x{e.error_category:02X}"),
        "error_data":     f"0x{code & 0xFFFF:04X}",
    }


# ---------------------------------------------------------------------------
# App & routers
# ---------------------------------------------------------------------------

app = FastAPI(title="GoPro Remote — Error Reporter")
init_db()

# All /admin routes share the local-network dependency
admin = APIRouter(prefix="/admin", dependencies=[Depends(require_local)])

_SORTABLE = {
    "timestamp":      ErrorReport.timestamp,
    "version":        ErrorReport.version,
    "error_category": ErrorReport.error_category,
    "gopro_id":       ErrorReport.gopro_id,
    "build_flags":    ErrorReport.build_flags,
}

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ReportBody(BaseModel):
    errors: list[int] = Field(..., description="32-bit error codes from ErrorManager.errorQueue")


class VersionCreate(BaseModel):
    version: str = Field(..., max_length=32, description="Human label, e.g. 'v4.1'")


# ---------------------------------------------------------------------------
# Public endpoint — callable from any network, authenticated by API key
# ---------------------------------------------------------------------------

@app.post("/report", status_code=204, summary="Submit error codes from the watch")
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

    for code in body.errors:
        p = _parse(code)
        db.add(ErrorReport(
            version        = key_record.version,
            error_code     = code,
            build_flags    = p["build_flags"],
            gopro_id       = p["gopro_id"],
            error_category = p["error_category"],
        ))

    db.commit()


# ---------------------------------------------------------------------------
# Admin — errors grid
# ---------------------------------------------------------------------------

@admin.get("/errors", summary="Paginated, filterable error list")
async def list_errors(
    db: Session = Depends(get_db),
    sort_by: str = "timestamp",
    order: str   = "desc",
    version:        Optional[str] = None,
    error_category: Optional[str] = None,
    gopro_id:       Optional[int] = None,
    limit:  int = 100,
    offset: int = 0,
):
    q = db.query(ErrorReport)

    if version:
        q = q.filter(ErrorReport.version == version)
    if error_category:
        # Accept both "ERR_COMM" and "0x20"
        cat_raw = next(
            (k for k, v in ERROR_CATEGORIES.items() if v == error_category),
            None,
        )
        if cat_raw is None:
            try:
                cat_raw = int(error_category, 16)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unknown error_category: {error_category!r}")
        q = q.filter(ErrorReport.error_category == cat_raw)
    if gopro_id is not None:
        q = q.filter(ErrorReport.gopro_id == gopro_id)

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
# Admin — aggregated stats
# ---------------------------------------------------------------------------

@admin.get("/stats", summary="Aggregated counts for dashboard widgets")
async def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(ErrorReport.id)).scalar()

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
# Admin — API key management
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
        "key":        key,          # shown only once — store it now
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
