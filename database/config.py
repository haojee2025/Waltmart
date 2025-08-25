import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load .env from repo root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "root")
PG_DATABASE = os.getenv("PG_DATABASE", "grocery")

DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"

def create_database_if_missing():
    """Create the target database if it doesn't exist, using psycopg2."""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except Exception as e:
        print("Missing dependency: psycopg2-binary. Install it in your venv: pip install psycopg2-binary")
        raise

    url = urlparse(DATABASE_URL)
    dbname = url.path.lstrip("/")
    dsn_admin = f"dbname=postgres user={url.username} password={url.password} host={url.hostname} port={url.port}"

    conn = psycopg2.connect(dsn_admin)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    exists = cur.fetchone()
    if not exists:
        cur.execute(f'CREATE DATABASE "{dbname}"')
        print(f'✅ Created database "{dbname}".')
    else:
        print(f'ℹ️ Database "{dbname}" already exists.')
    cur.close()
    conn.close()

def test_connect():
    """Quick sanity check: connect and run SELECT 1 on the target DB."""
    print(f"Connecting to: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL, future=True)
    try:
        with engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar_one()
        print(f"DB ok, SELECT 1 => {val}")
    except SQLAlchemyError as e:
        print("DB connection FAILED 🚨")
        print(e)
        raise

if __name__ == "__main__":
    # CLI: python -m database.config create-db | test
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    if cmd in ("create", "create-db"):
        create_database_if_missing()
    test_connect()

