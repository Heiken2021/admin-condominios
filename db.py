import os
import streamlit as st
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

def database_url():
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        value = os.getenv("DATABASE_URL")
        if not value:
            raise RuntimeError("Falta DATABASE_URL en Streamlit secrets o variables de entorno")
        return value

@st.cache_resource
def pool():
    p = ConnectionPool(
        conninfo=database_url(), min_size=1, max_size=5,
        kwargs={"row_factory": dict_row, "autocommit": False},
        open=True,
    )
    p.wait(timeout=15)
    return p

def execute(sql, params=(), returning=False):
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if returning else None
        conn.commit()
        return row

def fetch_all(sql, params=()):
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def fetch_one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None

def init_schema():
    from pathlib import Path
    script = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(script)
        conn.commit()
