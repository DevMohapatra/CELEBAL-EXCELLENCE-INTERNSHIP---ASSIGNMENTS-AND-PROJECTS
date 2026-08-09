
import sqlite3
import time
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "logs" / "drivewise.db"


def _get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            brand TEXT,
            model TEXT,
            query TEXT,
            response_time_ms REAL,
            status TEXT,
            num_sources INTEGER,
            answer_preview TEXT,
            error TEXT
        )
    """)
    return conn


def log_query(brand, model, query, response_time_ms, status, num_sources=0, answer_preview="", error=""):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO query_log (timestamp, brand, model, query, response_time_ms, status, num_sources, answer_preview, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (time.time(), brand, model, query, response_time_ms, status, num_sources, answer_preview[:200], error),
    )
    conn.commit()
    conn.close()


def get_recent_logs(limit=20):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT timestamp, brand, model, query, response_time_ms, status, num_sources, error "
        "FROM query_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    cols = ["timestamp", "brand", "model", "query", "response_time_ms", "status", "num_sources", "error"]
    return [dict(zip(cols, r)) for r in rows]


def get_stats():
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM query_log WHERE status='failed'").fetchone()[0]
    avg_time = conn.execute("SELECT AVG(response_time_ms) FROM query_log WHERE status='success'").fetchone()[0]
    conn.close()
    return {
        "total_queries": total,
        "failed_queries": failed,
        "avg_response_time_ms": round(avg_time, 2) if avg_time else None,
    }
