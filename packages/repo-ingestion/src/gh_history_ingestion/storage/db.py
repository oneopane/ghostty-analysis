from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .schema import Base


def get_engine(db_path: str | Path):
    db_path_str = str(db_path)
    if db_path_str == ":memory:":
        url = "sqlite+pysqlite:///:memory:"
    else:
        url = f"sqlite+pysqlite:///{db_path_str}"
    return create_engine(url, future=True)


def get_session(engine) -> Session:
    return Session(engine)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
