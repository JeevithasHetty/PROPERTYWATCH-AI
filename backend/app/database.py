from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# For SQLite, check_same_thread=False allows multiple threads (FastAPI async requests)
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def sync_database_schema():
    """Ensure all tables and updated columns exist without disturbing existing records."""
    import app.models  # noqa: F401  (register all tables on Base before create_all)
    Base.metadata.create_all(bind=engine)
    
    # Safe column migrations for SQLite
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            # Check properties columns
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(properties)")).fetchall()]
            if "owner_user_id" not in cols:
                conn.execute(text("ALTER TABLE properties ADD COLUMN owner_user_id INTEGER"))
                conn.commit()

    _additive_columns()


_ADDITIVE = [
    ("property_snapshots", "data_origin", "VARCHAR(30) DEFAULT 'USER_UPLOAD'"),
    ("properties", "is_demo", "BOOLEAN DEFAULT 0"),
    ("insurance_policies", "structured_terms", "JSON"),
    ("claims", "loss_items", "JSON"),
]


def _additive_columns():
    """Add new nullable columns to existing databases and back-fill origin flags (non-destructive)."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    with engine.connect() as conn:
        for table, col, ddl in _ADDITIVE:
            cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
            if col not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        conn.execute(text(
            "UPDATE property_snapshots SET data_origin='DEMO_SYNTHETIC' "
            "WHERE (data_origin IS NULL OR data_origin='USER_UPLOAD') AND "
            "(image_source LIKE '%Demo%' OR image_source LIKE '%Simulat%' OR image_path LIKE '%/gee_%')"))
        conn.execute(text(
            "UPDATE properties SET is_demo=1 WHERE property_reference IN "
            "('PROP-2026-1001','PROP-2026-1002','PROP-2026-1003','PROP-2026-1004') AND is_demo=0"))
        conn.commit()
