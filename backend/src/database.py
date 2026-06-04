from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///errors.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ApiKey(Base):
    __tablename__ = "api_keys"

    id         = Column(Integer, primary_key=True)
    key        = Column(String(64), unique=True, index=True, nullable=False)
    version    = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    active     = Column(Integer, default=1)  # 1=active, 0=revoked


class ErrorReport(Base):
    __tablename__ = "error_reports"

    id             = Column(Integer, primary_key=True)
    timestamp      = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    version        = Column(String(32), index=True)

    # Raw 32-bit code -- error_hex / error_data / gopro_model are derivable from this
    error_code     = Column(Integer, nullable=False)

    # Pre-extracted for sorting/filtering -- see ErrorManager.mc for bit layout
    build_flags    = Column(Integer)                # bits 31-30

    gopro_id       = Column(Integer, index=True)    # bits 29-24

    # Normalised category: 0x80=ERR_CAM, 0x40=ERR_MSG, 0x20=ERR_COMM,
    # 0x10=ERR_SYS, 0x00=ERR_NULL, 0x30=ERR_EXT
    error_category = Column(Integer, index=True)    # bits 23-16 (normalised)

    # Sub-type within the category (NULL when the category has none):
    #   ERR_CAM  → ec_byte & 0x7F  (SUB_CAM_* + extra context, both << 16)
    #   ERR_MSG  → ec_byte & 0x3F  (SUB_MSG_* + extra context, both << 16)
    #   ERR_COMM → data & 0xF0     (upper nibble of data0, matches SUB_BLE_*)
    error_subtype  = Column(Integer, index=True, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
