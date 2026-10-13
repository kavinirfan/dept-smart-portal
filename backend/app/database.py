import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# SQLite by default so the prototype runs with zero setup.
# Point DATABASE_URL at PostgreSQL (postgresql+psycopg://user:pass@host/db) for deployment.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portal.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
