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


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = [row[1] for row in connection.exec_driver_sql("PRAGMA table_info(buyer_sessions)")]
            if "bedrooms_or_more" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE buyer_sessions ADD COLUMN bedrooms_or_more BOOLEAN NOT NULL DEFAULT 0"
                )
