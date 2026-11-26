from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATA_DIR, settings

DATA_DIR.mkdir(parents=True, exist_ok=True)

db_url = settings.database_url
connect_args = {}
if db_url.startswith("sqlite"):
    db_url = "sqlite:///" + (DATA_DIR / "amlak.db").as_posix()
    connect_args["check_same_thread"] = False

engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_column(connection, table: str, name: str, ddl: str) -> None:
    columns = [row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")]
    if name not in columns:
        connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            _ensure_column(connection, "buyer_sessions", "bedrooms_or_more", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "buyer_sessions", "bedrooms_skipped", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "buyer_sessions", "area_min", "FLOAT")
            _ensure_column(connection, "buyer_sessions", "area_max", "FLOAT")
            _ensure_column(connection, "buyer_sessions", "area_skipped", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "buyer_sessions", "price_min", "BIGINT")
            _ensure_column(connection, "buyer_sessions", "price_max", "BIGINT")
            _ensure_column(connection, "buyer_sessions", "price_skipped", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "buyer_sessions", "age_min", "INTEGER")
            _ensure_column(connection, "buyer_sessions", "age_max", "INTEGER")
            _ensure_column(connection, "buyer_sessions", "age_skipped", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "listings", "building_year", "INTEGER")
            _ensure_column(connection, "listings", "category", "VARCHAR(20) NOT NULL DEFAULT ''")
            _ensure_column(connection, "listings", "deal_type", "VARCHAR(20) NOT NULL DEFAULT ''")
            _ensure_column(connection, "listings", "deposit", "BIGINT")
            _ensure_column(connection, "listings", "rent", "BIGINT")
            _ensure_column(connection, "listings", "deposit_min", "BIGINT")
            _ensure_column(connection, "listings", "deposit_max", "BIGINT")
            _ensure_column(connection, "listings", "rent_min", "BIGINT")
            _ensure_column(connection, "listings", "rent_max", "BIGINT")
            _ensure_column(connection, "listings", "rent_convertible", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "listings", "consultant_name", "VARCHAR(120) NOT NULL DEFAULT ''")
            _ensure_column(connection, "listings", "consultant_phone", "VARCHAR(11) NOT NULL DEFAULT ''")
            _ensure_column(connection, "divar_connection", "posts_url", "VARCHAR(500) NOT NULL DEFAULT ''")
            _ensure_column(connection, "divar_connection", "last_sync_at", "DATETIME")
            _ensure_column(connection, "divar_connection", "last_sync_complete", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "divar_connection", "last_sync_done", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(connection, "divar_connection", "last_sync_total", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(connection, "divar_connection", "last_sync_listed", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "divar_connection", "last_sync_report", "TEXT")
            _ensure_column(connection, "buyer_sessions", "category", "VARCHAR(20) NOT NULL DEFAULT ''")
            _ensure_column(connection, "buyer_sessions", "deal_type", "VARCHAR(20) NOT NULL DEFAULT ''")
            _ensure_column(connection, "buyer_sessions", "deposit_min", "BIGINT")
            _ensure_column(connection, "buyer_sessions", "deposit_max", "BIGINT")
            _ensure_column(connection, "buyer_sessions", "deposit_skipped", "BOOLEAN NOT NULL DEFAULT 0")
            _ensure_column(connection, "buyer_sessions", "rent_min", "BIGINT")
            _ensure_column(connection, "buyer_sessions", "rent_max", "BIGINT")
            _ensure_column(connection, "buyer_sessions", "rent_skipped", "BOOLEAN NOT NULL DEFAULT 0")
    _backfill_building_years()


def _backfill_building_years() -> None:
    from app.models import Listing
    from app.utils import build_year_from_text

    db = SessionLocal()
    try:
        rows = db.query(Listing).filter(Listing.building_year.is_(None)).all()
        changed = False
        for row in rows:
            year = build_year_from_text(row.structured_text or "")
            if year is None:
                continue
            row.building_year = year
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()
