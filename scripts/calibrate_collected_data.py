#!/usr/bin/env python3
"""校准已采集数据：清洗历史记录、合并重复项、重建间隔计数器。"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CSV_PATH, TOWER_CSV_PATH, GAP_COUNTER_PATH, CITY_MAP, TOP3_CITIES


def parse_dt(date_str: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def normalize_city_name(city_id: int, city_name: str | None) -> str:
    return CITY_MAP.get(city_id, city_name or f"未知({city_id})")


def load_csv_rows(path: str) -> list[list[str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def write_csv_rows(path: str, header: list[str], rows: list[list[str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def calibrate_records_csv() -> int:
    rows = load_csv_rows(CSV_PATH)
    if not rows:
        return 0

    cleaned = []
    seen = set()
    for row in rows[1:]:
        if len(row) < 4:
            continue
        date_str, time_str, city_id_str, city_name = row[:4]
        try:
            city_id = int(city_id_str)
            dt = parse_dt(date_str, time_str)
        except Exception:
            continue
        city_name = normalize_city_name(city_id, city_name)
        item = (dt, date_str, time_str, city_id, city_name)
        key = (date_str, time_str, city_id, city_name)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    cleaned.sort(key=lambda x: (x[0], x[3], x[4]))
    output_rows = [[date_str, time_str, str(city_id), city_name] for _, date_str, time_str, city_id, city_name in cleaned]
    write_csv_rows(CSV_PATH, ["date", "time", "city_id", "city_name"], output_rows)
    return len(output_rows)


def calibrate_tower_csv() -> tuple[int, datetime | None]:
    rows = load_csv_rows(TOWER_CSV_PATH)
    if not rows:
        return 0, None

    aggregated: dict[tuple[str, str, int], int] = defaultdict(int)
    city_names: dict[tuple[str, str, int], str] = {}
    latest_dt: datetime | None = None

    for row in rows[1:]:
        if len(row) < 5:
            continue
        date_str, time_str, city_id_str, city_name, attack_count_str = row[:5]
        try:
            city_id = int(city_id_str)
            attack_count = int(float(attack_count_str))
            dt = parse_dt(date_str, time_str)
        except Exception:
            continue
        city_name = normalize_city_name(city_id, city_name)
        key = (date_str, time_str, city_id)
        aggregated[key] += max(attack_count, 0)
        city_names[key] = city_name
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt

    ordered = sorted(
        aggregated.items(),
        key=lambda item: (parse_dt(item[0][0], item[0][1]), item[0][2]),
    )
    output_rows = [
        [date_str, time_str, str(city_id), city_names[(date_str, time_str, city_id)], str(attack_count)]
        for (date_str, time_str, city_id), attack_count in ordered
    ]
    write_csv_rows(TOWER_CSV_PATH, ["date", "time", "city_id", "city_name", "attack_count"], output_rows)
    return len(output_rows), latest_dt


def rebuild_gap_counter() -> dict[str, dict[str, int | str | None]]:
    """从 records.csv 的每手结果序列计算间隔手数。"""
    result = {str(cid): {"last_seen_time": None, "gap_hands": None} for cid in TOP3_CITIES}
    rows = load_csv_rows(CSV_PATH)
    if len(rows) <= 1:
        with open(GAP_COUNTER_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    parsed = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        try:
            parsed.append((row[0], row[1], int(row[2])))
        except ValueError:
            continue

    n = len(parsed)
    for cid in TOP3_CITIES:
        last_pos = None
        for idx in range(n - 1, -1, -1):
            if parsed[idx][2] == cid:
                last_pos = idx
                break
        if last_pos is None:
            continue
        date_str, time_str, _ = parsed[last_pos]
        result[str(cid)] = {
            "last_seen_time": f"{date_str} {time_str}",
            "gap_hands": n - 1 - last_pos,
        }

    with open(GAP_COUNTER_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main():
    records_count = calibrate_records_csv()
    tower_count, reference_dt = calibrate_tower_csv()
    gap_counter = rebuild_gap_counter()

    print("校准完成")
    print(f"records.csv: {records_count} 条")
    print(f"tower_records.csv: {tower_count} 条")
    if reference_dt is not None:
        print(f"参考时间: {reference_dt.strftime('%Y-%m-%d %H:%M')}")
    print("gap_counter:")
    for cid in TOP3_CITIES:
        info = gap_counter[str(cid)]
        print(f"  {CITY_MAP[cid]}: {info['gap_hands']} 手, 最后出现 {info['last_seen_time']}")


if __name__ == "__main__":
    main()
