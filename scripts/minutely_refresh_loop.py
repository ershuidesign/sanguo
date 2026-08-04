#!/usr/bin/env python3
"""每分钟到达 00.5 秒时，执行一次采集、校准、日报刷新。"""

from __future__ import annotations

import subprocess
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "minutely_refresh.log"
LOCK_PATH = LOG_DIR / "minutely_refresh.lock"
BACKFILL_MARKER = LOG_DIR / "last_backfill_at.txt"


def seconds_until_next_half_second() -> float:
    now = datetime.now()
    target = now.replace(second=0, microsecond=500_000)
    if target <= now:
        target += timedelta(minutes=1)
    return max(0.0, (target - now).total_seconds())


def run_step(label: str, script_name: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script_name)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=90,
    )
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    return result.returncode == 0, output


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n")


def should_backfill(now: datetime) -> bool:
    if not BACKFILL_MARKER.exists():
        return True
    try:
        last = datetime.fromisoformat(BACKFILL_MARKER.read_text(encoding="utf-8").strip())
        return now - last >= timedelta(hours=4)
    except (ValueError, OSError):
        return True


def refresh_once() -> bool:
    # 避免分钟刷新与网页手动刷新同时改写同一日报。
    try:
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        log("[SKIP] 上一次刷新仍在执行")
        return False
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    try:
        os.close(lock_fd)
        log(f"\n[{started}] 开始分钟刷新")
        now = datetime.now()
        if should_backfill(now):
            ok, output = run_step("回补", "backfill_recent_data.py")
            log(f"[回补] {'OK' if ok else 'FAIL'}")
            if output:
                log(output[-3000:])
            if ok:
                BACKFILL_MARKER.write_text(now.isoformat(timespec="seconds"), encoding="utf-8")
        for label, script_name in [
            ("采集", "collect_defense_data.py"),
            ("校准", "calibrate_collected_data.py"),
            ("日报", "daily_defense_summary.py"),
        ]:
            ok, output = run_step(label, script_name)
            log(f"[{label}] {'OK' if ok else 'FAIL'}")
            if output:
                log(output[-3000:])
            if not ok:
                return False
        return True
    finally:
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass


def main() -> None:
    print(f"分钟刷新循环已启动，日志: {LOG_PATH}")
    print("执行时间: 每分钟的 00.5 秒开始执行一次；按 Ctrl+C 停止")
    while True:
        time.sleep(seconds_until_next_half_second())
        try:
            refresh_once()
        except Exception as exc:
            log(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()
