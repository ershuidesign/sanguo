#!/usr/bin/env python3
"""斗鱼大话三国数据采集脚本 - 每小时采集API数据，基于report_minute_tower追踪上三城进攻间隔

数据来源：https://tool.100if.com/douyuDefenseTower/api/v1/report/weekly
上三城（固定）：洛阳(1)、成都(2)、建业(3)
用户重点关注：洛阳和成都

核心修复：改用 report_minute_tower（上三城每分钟进攻次数）追踪间隔，
而非 report_minute（每分钟获胜城），与网站"间隔手数"定义一致。

独立版本：移除 codeact_sdk 依赖，纯 Python 脚本
"""

import urllib.request
import json
import csv
import os
import sys
import time
import ssl
from datetime import datetime, timedelta

# 导入集中配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    API_URL_TEMPLATE, DATA_DIR, RAW_DIR, CSV_PATH, TOWER_CSV_PATH, GAP_COUNTER_PATH,
    CITY_MAP, TOP3_CITIES, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_BASE_DELAY, USER_AGENT
)


# ============ API 请求 ============
def fetch_report():
    """请求API，返回完整data[0]（含report_minute_tower）"""
    last_error = None
    ssl_context = None
    try:
        import certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        # 在证书链不完整的环境中，退回到不校验证书的上下文，
        # 以保证脚本可在本地环境继续运行。
        ssl_context = ssl._create_unverified_context()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ts = int(time.time() * 1000)
            url = API_URL_TEMPLATE.format(timestamp_ms=ts)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ssl_context)
            raw = json.loads(resp.read().decode("utf-8"))

            if raw.get("status", {}).get("code") != 0:
                raise ValueError(f"API返回异常: {raw.get('status')}")

            data = raw.get("data", [])
            if not data:
                raise ValueError("API返回data为空")

            return data[0]

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY ** attempt
                print(f"[第{attempt}/{MAX_RETRIES}次重试] API请求失败: {e}，等待{delay}秒后重试...")
                time.sleep(delay)
            else:
                print(f"[第{attempt}/{MAX_RETRIES}次重试] API请求失败: {e}，已达最大重试次数")

    print(f"API请求最终失败: {last_error}")
    return None


# ============ CSV 操作 ============
def ensure_dirs():
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "time", "city_id", "city_name"])
    if not os.path.exists(TOWER_CSV_PATH):
        with open(TOWER_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "time", "city_id", "city_name", "attack_count"])


def parse_minute_to_minutes(time_str):
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def process_tower_data(report_data, now=None):
    """
    从 report_minute_tower 提取上三城进攻记录。
    report_minute_tower: {city_id: {minute: attack_count}}
    返回: [(date_str, time_str, city_id, city_name, attack_count), ...] 按时间正序

    关键修复：API返回的minute数据包含未来分钟（服务器时间偏差），
    只采集 <= 当前分钟的记录，过滤掉未来数据。
    """
    if now is None:
        now = datetime.now()

    tower = report_data.get("report_minute_tower", {})
    current_hour = now.hour
    current_minute = now.minute
    current_date = str(now.date())

    records = []
    for cid_str, minute_data in tower.items():
        cid = int(cid_str)
        if cid not in TOP3_CITIES:
            continue
        city_name = CITY_MAP.get(cid, f"未知({cid})")
        for mm_str, count in minute_data.items():
            mm = int(mm_str)
            # 关键过滤：只取当前分钟及之前的数据，排除API返回的未来分钟
            if count > 0 and mm <= current_minute:
                time_str = f"{current_hour:02d}:{mm:02d}"
                records.append((current_date, time_str, cid, city_name, int(count)))

    # 按时间正序
    records.sort(key=lambda x: (x[0], x[1]))
    return records


def append_tower_records(records):
    """按日期、分钟和城池独立去重，避免同一分钟漏掉其他城池。"""
    existing = set()
    if os.path.exists(TOWER_CSV_PATH):
        with open(TOWER_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 3:
                    existing.add((row[0], row[1], row[2]))

    new_records = []
    for record in records:
        key = (record[0], record[1], str(record[2]))
        if key not in existing:
            new_records.append(record)
            existing.add(key)

    if new_records:
        with open(TOWER_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for record in new_records:
                writer.writerow(record)

    return len(new_records)


def update_gap_counter_from_records():
    """从 report_minute 的完整时间序列重建间隔，匹配官网近8小时记录。"""
    if not os.path.exists(CSV_PATH):
        return {str(cid): {"last_seen_time": None, "gap_hands": None} for cid in TOP3_CITIES}

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            try:
                rows.append((row[0], row[1], int(row[2])))
            except ValueError:
                continue

    result = {}
    n = len(rows)
    for cid in TOP3_CITIES:
        last_pos = None
        for idx in range(n - 1, -1, -1):
            if rows[idx][2] == cid:
                last_pos = idx
                break
        if last_pos is None:
            result[str(cid)] = {"last_seen_time": None, "gap_hands": None}
            continue
        date_str, time_str, _ = rows[last_pos]
        result[str(cid)] = {
            "last_seen_time": f"{date_str} {time_str}",
            "gap_hands": n - 1 - last_pos,
        }

    with open(GAP_COUNTER_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def process_report_minute(report_data, now=None):
    """合并官网近8小时记录，按日期、时间、城池去重并保持时间顺序。"""
    if now is None:
        now = datetime.now()

    report_minute = report_data.get("report_minute", [])
    if isinstance(report_minute, dict):
        report_minute = [{k: v} for k, v in sorted(report_minute.items(), reverse=True)]

    today = str(now.date())
    parsed = []
    for item in report_minute:
        for time_str, city_id in item.items():
            parts = time_str.split(":")
            entry_hh = int(parts[0])
            if entry_hh > now.hour + 1:
                date_str = str((now.date() - timedelta(days=1)))
            else:
                date_str = today
            city_name = CITY_MAP.get(city_id, f"未知({city_id})")
            parsed.append((date_str, time_str, city_id, city_name))

    parsed.reverse()

    existing = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 4:
                    try:
                        existing.append((row[0], row[1], int(row[2]), row[3]))
                    except ValueError:
                        continue

    merged = {}
    for record in existing + parsed:
        merged[(record[0], record[1], int(record[2]))] = record
    ordered = sorted(merged.values(), key=lambda x: (x[0], parse_minute_to_minutes(x[1]), int(x[2])))
    new_records = len(ordered) - len(existing)
    if ordered != existing:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "time", "city_id", "city_name"])
            writer.writerows(ordered)

    return max(0, new_records)


# ============ 主流程 ============
def main():
    """独立采集主流程 - 纯Python，无codeact_sdk依赖"""
    try:
        ensure_dirs()

        report_data = fetch_report()
        if report_data is None:
            print("ERROR: API请求失败")
            sys.exit(1)

        now = datetime.now()

        # 1. 处理 tower 数据（上三城间隔追踪）
        tower_records = process_tower_data(report_data, now)
        new_tower = append_tower_records(tower_records)

        # 2. 处理 report_minute（兼容历史）
        new_minute = process_report_minute(report_data, now)

        # 3. 更新间隔计数器（基于每手结果序列）
        gap_data = update_gap_counter_from_records()

        # 4. 输出采集结果摘要
        gap_summary = "  ".join(
            f"{CITY_MAP.get(int(k), k)}: {v['gap_hands']}手" if v['gap_hands'] is not None else f"{CITY_MAP.get(int(k), k)}: 未出现"
            for k, v in sorted(gap_data.items(), key=lambda x: int(x[0]))
        )

        total_tower = 0
        if os.path.exists(TOWER_CSV_PATH):
            with open(TOWER_CSV_PATH, "r", encoding="utf-8") as f:
                total_tower = sum(1 for _ in f) - 1

        total_minute = 0
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, "r", encoding="utf-8") as f:
                total_minute = sum(1 for _ in f) - 1

        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 采集完成")
        print(f"tower新增{new_tower}条(累计{total_tower}) | minute新增{new_minute}条(累计{total_minute}) | 上三城间隔: {gap_summary}")

    except Exception as e:
        print(f"ERROR: 采集失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
