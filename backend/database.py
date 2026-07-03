"""
SQLAlchemy database engine, session factory, and Base declarative class.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import settings

# For SQLite, the connection string from .env is relative to CWD.
# Convert it so the DB file always lives under data/.
_db_path = settings.DATA_DIR / "car_inspection.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + threads
)

# Enable WAL mode and foreign keys for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once at startup."""
    settings.ensure_directories()
    Base.metadata.create_all(bind=engine)
