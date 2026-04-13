from __future__ import annotations
from contextlib import contextmanager
from app.db.session import SessionLocal

@contextmanager
def db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
