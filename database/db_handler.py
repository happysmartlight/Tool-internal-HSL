"""
database/db_handler.py
SQLite persistence: calculation history + exchange rate cache.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from utils.logger import get_logger

log = get_logger(__name__)

DB_PATH = Path(__file__).parent.parent / "import_calc.db"

# ── Schema ──────────────────────────────────────────────────
_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS calculations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    label       TEXT    DEFAULT '',
    products_json TEXT  NOT NULL,
    config_json   TEXT  NOT NULL,
    rate_json     TEXT  NOT NULL,
    result_json   TEXT  NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_cache (
    currency    TEXT PRIMARY KEY,
    market_rate REAL  NOT NULL,
    bank_rate   REAL  NOT NULL,
    spread_pct  REAL  NOT NULL DEFAULT 2.0,
    updated_at  TEXT  NOT NULL
);
"""

@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    """Create tables if they don't exist."""
    with _conn() as con:
        con.executescript(_SCHEMA)
    log.info("Database initialised at %s", DB_PATH)


# ── Rate Cache ───────────────────────────────────────────────
def save_rate(currency: str, market_rate: float, bank_rate: float, spread_pct: float = 2.0):
    with _conn() as con:
        con.execute("""
            INSERT INTO rate_cache (currency, market_rate, bank_rate, spread_pct, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(currency) DO UPDATE SET
                market_rate = excluded.market_rate,
                bank_rate   = excluded.bank_rate,
                spread_pct  = excluded.spread_pct,
                updated_at  = excluded.updated_at
        """, (currency, market_rate, bank_rate, spread_pct, datetime.now().isoformat()))


def get_cached_rate(currency: str) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM rate_cache WHERE currency = ?", (currency,)
        ).fetchone()
    return dict(row) if row else None


# ── Calculation History ──────────────────────────────────────
def save_calculation(label: str, products: list, config: dict, rate: dict, result: dict) -> int:
    with _conn() as con:
        cur = con.execute("""
            INSERT INTO calculations (created_at, label, products_json, config_json, rate_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            label,
            json.dumps(products, ensure_ascii=False),
            json.dumps(config, ensure_ascii=False),
            json.dumps(rate, ensure_ascii=False),
            json.dumps(result, ensure_ascii=False),
        ))
        return cur.lastrowid


def list_calculations(limit: int = 50) -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM calculations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_calculation(calc_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        row = con.execute("SELECT * FROM calculations WHERE id = ?", (calc_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["products_list"] = json.loads(d["products_json"])
    d["config_dict"]   = json.loads(d["config_json"])
    d["rate_dict"]     = json.loads(d["rate_json"])
    d["result_dict"]   = json.loads(d["result_json"])
    return d


def delete_calculation(calc_id: int):
    with _conn() as con:
        con.execute("DELETE FROM calculations WHERE id = ?", (calc_id,))
