from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# For a scalable SaaS, we'd use PostgreSQL. 
# For this implementation, I'll use SQLite by default for easy setup, 
# but it's easily switchable to Postgres via environment variable.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./scrapeverify.db")

# If it's a relative SQLite path, make it absolute to the current project directory if desired,
# but keeping it simple for dev:
if DATABASE_URL.startswith("sqlite:///./"):
    db_file = DATABASE_URL.replace("sqlite:///./", "")
    # Check if we are already in the backend directory
    current_path = Path.cwd()
    if current_path.name == "backend":
        sqlite_path = current_path / db_file
    else:
        sqlite_path = current_path / "backend" / db_file
    DATABASE_URL = f"sqlite:///{sqlite_path.absolute().as_posix()}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_legacy_schema_compatibility():
    """Patch older local SQLite databases so current models can boot cleanly."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "users" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as connection:
        if "email" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
        if "is_active" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1"))

        indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_email" not in indexes:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
        # Add role and plan columns if missing (new additions)
        if "role" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'"))
        if "plan" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN plan VARCHAR DEFAULT 'free'"))
        if "is_approved" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 1")) # Auto-approve existing users

    # ── Companies Table Migration ───────────────────────────────────────────
    inspector = inspect(engine)
    if "companies" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("companies")}
        with engine.begin() as connection:
            if "website" not in columns:
                if "source_url" in columns:
                    # Rename if we have the old name (SQLite doesn't support RENAME COLUMN easily in old versions, but let's try simple ADD first)
                    connection.execute(text("ALTER TABLE companies ADD COLUMN website VARCHAR"))
                else:
                    connection.execute(text("ALTER TABLE companies ADD COLUMN website VARCHAR"))
            if "rating" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN rating FLOAT"))
            if "reviews_count" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN reviews_count INTEGER DEFAULT 0"))
            if "category" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN category VARCHAR"))
            if "latitude" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN latitude FLOAT"))
            if "longitude" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN longitude FLOAT"))
            if "validation_details" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN validation_details JSON"))
            if "source" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN source VARCHAR"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
