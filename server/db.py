import os
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# load root .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "root")
PG_DATABASE = os.getenv("PG_DATABASE", "grocery")

def get_conn(dbname: str = PG_DATABASE):
    return psycopg2.connect(
        dbname=dbname, user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT
    )
