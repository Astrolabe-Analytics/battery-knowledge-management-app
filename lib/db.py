"""
Database connection management for PostgreSQL + pgvector.

Provides:
- Engine creation with connection pooling
- Session factory (scoped sessions for thread safety)
- Table creation utility
- Configuration via environment variables or defaults
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/astrolabe"
)

# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,       # Verify connections are alive before using
    echo=False,               # Set True for SQL debugging
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Session:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_raw_connection():
    """Get a raw DBAPI connection for bulk operations like COPY."""
    return engine.raw_connection()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def create_all_tables():
    """Create all tables and install pgvector extension.
    Safe to call multiple times (uses IF NOT EXISTS)."""
    from .models import Base  # Import here to avoid circular imports
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)


def drop_all_tables():
    """Drop all tables. USE WITH CAUTION."""
    from .models import Base
    Base.metadata.drop_all(engine)


def check_connection() -> bool:
    """Test the database connection. Returns True if OK."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
