"""PostgreSQL persistence for Render worker records and alert state."""

from __future__ import annotations

import os
from typing import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS attack_records (
    attack_time TIMESTAMPTZ NOT NULL,
    city_id INTEGER NOT NULL,
    city_name TEXT NOT NULL,
    attack_count INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'report_minute',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (attack_time, city_id)
);
CREATE INDEX IF NOT EXISTS attack_records_time_idx ON attack_records (attack_time DESC);
CREATE TABLE IF NOT EXISTS worker_state (
    state_key TEXT PRIMARY KEY,
    state_value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def connect():
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("未安装 psycopg2-binary，请先安装 requirements.txt") from exc
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL 未配置")
    return psycopg2.connect(url, connect_timeout=20)


def init_db() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)


def upsert_records(records: Iterable[tuple]) -> int:
    rows = list(records)
    if not rows:
        return 0
    from psycopg2.extras import execute_values
    values = [(f"{r[0]} {r[1]}:00+08", int(r[2]), r[3], int(r[4]) if len(r) > 4 else 1, "tower" if len(r) > 4 else "report_minute") for r in rows]
    sql = """
    INSERT INTO attack_records (attack_time, city_id, city_name, attack_count, source)
    VALUES %s
    ON CONFLICT (attack_time, city_id) DO UPDATE SET
      attack_count = EXCLUDED.attack_count,
      city_name = EXCLUDED.city_name,
      source = EXCLUDED.source,
      updated_at = NOW()
    """
    with connect() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
    return len(rows)


def set_state(key: str, value: str) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO worker_state (state_key, state_value) VALUES (%s, %s)
                ON CONFLICT (state_key) DO UPDATE SET state_value=EXCLUDED.state_value, updated_at=NOW()
            """, (key, value))
