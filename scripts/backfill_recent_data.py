#!/usr/bin/env python3
"""回补官网近8小时数据，修复短时网络失败造成的分钟遗漏。"""

from __future__ import annotations

import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from collect_defense_data import (
    ensure_dirs,
    fetch_report,
    process_report_minute,
    process_tower_data,
    append_tower_records,
    update_gap_counter_from_records,
)


def main() -> None:
    ensure_dirs()
    report = fetch_report()
    if report is None:
        raise RuntimeError("官网 API 请求失败，回补未执行")
    now = datetime.now()
    tower_count = append_tower_records(process_tower_data(report, now))
    minute_count = process_report_minute(report, now)
    gaps = update_gap_counter_from_records()
    print(f"回补完成: tower补回{tower_count}条, minute补回{minute_count}条")
    print("间隔: " + "  ".join(f"{k}:{v.get('gap_hands')}手" for k, v in sorted(gaps.items())))


if __name__ == "__main__":
    main()
