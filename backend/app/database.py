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
    Base.metadata.create_all(bind=engine)
    
    # Safe column migrations for SQLite
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            # Check properties columns
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(properties)")).fetchall()]
            if "owner_user_id" not in cols:
                conn.execute(text("ALTER TABLE properties ADD COLUMN owner_user_id INTEGER"))
                conn.commit()
