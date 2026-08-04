#!/usr/bin/env python3
"""常驻 Render Worker：每分钟采集、持久化、回补并生成预测通知。"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = BASE_DIR / "scripts"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(SCRIPTS))

from config import CSV_PATH, TOWER_CSV_PATH
from database import init_db, set_state, upsert_records


def run(script: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script)], cwd=str(BASE_DIR),
        text=True, capture_output=True, timeout=150,
    )
    output = "\n".join(x for x in (result.stdout, result.stderr) if x)
    if result.returncode:
        raise RuntimeError(f"{script} 失败: {output[-1200:]}")
    return output[-1200:]


def csv_rows(path: str):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                if "attack_count" in r:
                    rows.append((r["date"], r["time"], int(r["city_id"]), r["city_name"], int(r["attack_count"])))
                else:
                    rows.append((r["date"], r["time"], int(r["city_id"]), r["city_name"]))
            except (KeyError, ValueError):
                continue
    return rows


def persist_local_records() -> None:
    upsert_records(csv_rows(CSV_PATH))
    upsert_records(csv_rows(TOWER_CSV_PATH))


def due_backfill(last_backfill: datetime | None, now: datetime) -> bool:
    return last_backfill is None or now - last_backfill >= timedelta(hours=4)


def main() -> None:
    init_db()
    persist_local_records()
    last_backfill = None
    print("Render Worker 已启动：每分钟采集，每4小时回补", flush=True)
    while True:
        started = datetime.now()
        try:
            if due_backfill(last_backfill, started):
                print(run("backfill_recent_data.py"), flush=True)
                persist_local_records()
                last_backfill = started
                set_state("last_backfill_at", started.isoformat(timespec="seconds"))
            print(run("collect_defense_data.py"), flush=True)
            persist_local_records()
            print(run("calibrate_collected_data.py"), flush=True)
            print(run("daily_defense_summary.py"), flush=True)
            set_state("last_success_at", datetime.now().isoformat(timespec="seconds"))
        except Exception as exc:
            print(f"Worker 本轮失败: {exc}", flush=True)
            set_state("last_error", str(exc)[-1000:])
        elapsed = (datetime.now() - started).total_seconds()
        time.sleep(max(1, 60 - elapsed))


if __name__ == "__main__":
    main()
