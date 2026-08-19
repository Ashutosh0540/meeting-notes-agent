import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
except SQLAlchemyError:
    engine = None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    if engine is None:
        return
    import app.models  # Register models before creating tables.

    Base.metadata.create_all(bind=engine)
