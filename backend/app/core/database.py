from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def get_engine():
    """Create engine with appropriate settings for SQLite or PostgreSQL."""
    if settings.is_postgres:
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_size=20,
            max_overflow=10,
        )
    else:
        # SQLite — use StaticPool for testing compatibility
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # Enable WAL mode for better concurrency
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def check_db_health() -> dict:
    """Check database connectivity and return health status."""
    try:
        with engine.connect() as conn:
            if settings.is_postgres:
                result = conn.execute(text("SELECT 1"))
            else:
                result = conn.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "postgresql" if settings.is_postgres else "sqlite"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
