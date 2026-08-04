#!/usr/bin/env python3
"""Prediction flywheel: persist snapshots, resolve outcomes, and reflect by gap."""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from config import TOP3_IDS, TOP3_NAMES, FLYWHEEL_LOG_PATH, FLYWHEEL_SUMMARY_PATH


def _read_log():
    items = []
    if os.path.exists(FLYWHEEL_LOG_PATH):
        with open(FLYWHEEL_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def _write_log(items):
    os.makedirs(os.path.dirname(FLYWHEEL_LOG_PATH), exist_ok=True)
    tmp = FLYWHEEL_LOG_PATH + f".tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    os.replace(tmp, FLYWHEEL_LOG_PATH)


def _gap_before(records, cursor, city_id):
    for i in range(min(cursor, len(records)) - 1, -1, -1):
        if records[i][2] == city_id:
            return cursor - 1 - i
    return None


def _reflect(items):
    stats = defaultdict(lambda: {"n": 0, "hits": 0, "sum_pred": 0.0, "sum_brier": 0.0, "sum_error": 0.0, "bands": defaultdict(lambda: {"n": 0, "hits": 0, "sum_pred": 0.0})})
    for item in items:
        if item.get("status") != "resolved":
            continue
        for city, result in item.get("cities", {}).items():
            s = stats[city]
            p = float(result.get("final_probability", result.get("probability", 0.0)))
            y = int(result.get("actual", 0))
            # 反思应按“预测发生时的当前间隔”分组。命中后再计算的间隔会在
            # 命中城市上归零，导致所有命中样本错误集中到 0-10 档。
            gap = result.get("gap_before_prediction", result.get("gap"))
            s["n"] += 1
            s["hits"] += y
            s["sum_pred"] += p
            s["sum_brier"] += (p - y) ** 2
            s["sum_error"] += y - p
            band = "unknown" if gap is None else ("0-10" if gap <= 10 else "11-20" if gap <= 20 else "21-40" if gap <= 40 else "41-80" if gap <= 80 else "81+")
            b = s["bands"][band]
            b["n"] += 1
            b["hits"] += y
            b["sum_pred"] += p
    output = {}
    for city, s in stats.items():
        n = s["n"]
        bands = {}
        for band, b in s["bands"].items():
            bands[band] = {**b, "hit_rate": b["hits"] / b["n"] if b["n"] else 0.0, "mean_probability": b["sum_pred"] / b["n"] if b["n"] else 0.0}
        output[city] = {"n": n, "hits": s["hits"], "hit_rate": s["hits"] / n if n else 0.0, "mean_probability": s["sum_pred"] / n if n else 0.0, "brier": s["sum_brier"] / n if n else 0.0, "mean_error": s["sum_error"] / n if n else 0.0, "bands": bands}
    return output


def adaptive_weights(summary):
    """Return bounded experience weights; require enough resolved samples first."""
    weights = {}
    for city, metric in summary.items():
        base = 0.65
        if metric.get("n", 0) >= 30:
            # Positive error means historical outcomes exceeded forecasts.
            base += max(-0.10, min(0.10, float(metric.get("mean_error", 0.0)) * 0.5))
        weights[city] = round(max(0.45, min(0.80, base)), 4)
    return weights


def _build_summary(items, now):
    city_summary = _reflect(items)
    weights = adaptive_weights(city_summary)
    resolved_snapshots = sum(1 for item in items if item.get("status") == "resolved")
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "resolved_snapshots": resolved_snapshots,
        "resolved_samples": sum(v["n"] for v in city_summary.values()),
        "weights": weights,
        "cities": city_summary,
    }


def _write_summary(summary):
    os.makedirs(os.path.dirname(FLYWHEEL_SUMMARY_PATH), exist_ok=True)
    with open(FLYWHEEL_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def _resolve_items(items, records, now):
    cursor = len(records)
    changed = False
    for item in items:
        if item.get("status") != "pending" or cursor <= int(item.get("record_cursor", 0)):
            continue
        start = int(item["record_cursor"])
        next_row = records[start] if start < len(records) else None
        if next_row is None:
            continue
        for city_id in TOP3_IDS:
            city = TOP3_NAMES[city_id]
            result = item["cities"].setdefault(city, {})
            result["actual"] = int(next_row[2] == city_id)
            result["gap_before_hit"] = _gap_before(records, start + 1, city_id)
        item["status"] = "resolved"
        item["resolved_at"] = now.isoformat(timespec="seconds")
        item["actual_record"] = {"date": next_row[0], "time": next_row[1], "city_id": next_row[2], "city_name": next_row[3]}
        changed = True
    return changed


def resolve_pending(records, now=None):
    """先结算上一轮快照，让最新真实结果参与本轮预测。"""
    now = now or datetime.now()
    items = _read_log()
    if _resolve_items(items, records, now):
        _write_log(items)
    summary = _build_summary(items, now)
    _write_summary(summary)
    return summary


def record_snapshot(records, predictions, now=None):
    """保存当前预测；同一批原始记录只保留一个待结算快照。"""
    now = now or datetime.now()
    items = _read_log()
    cursor = len(records)
    if items and items[-1].get("status") == "pending" and int(items[-1].get("record_cursor", -1)) == cursor:
        summary = _build_summary(items, now)
        _write_summary(summary)
        return summary
    any_pred = predictions.get("any_top3", {}) or {}
    any_diag = any_pred.get("experience_diagnostics", {}) or {}
    snapshot = {
        "snapshot_id": now.isoformat(timespec="milliseconds"),
        "created_at": now.isoformat(timespec="seconds"),
        "record_cursor": cursor,
        "status": "pending",
        "any_top3": {
            "probability": any_pred.get("probability"),
            "final_probability": any_pred.get("comprehensive_probability_calibrated",
                                               any_pred.get("comprehensive_probability",
                                                            any_pred.get("probability_calibrated",
                                                                         any_pred.get("probability")))),
            "three_hand_probability": any_diag.get("three_hand_probability"),
        },
        "cities": {},
    }
    for city_id in TOP3_IDS:
        city = TOP3_NAMES[city_id]
        pred = predictions.get(city, {})
        diag = pred.get("experience_diagnostics", {}) or {}
        snapshot["cities"][city] = {
            "gap": pred.get("gap"),
            "probability": pred.get("probability"),
            "model_probability": pred.get("model_probability"),
            "experience_probability": pred.get("experience_probability"),
            "final_probability": pred.get("comprehensive_probability_calibrated",
                                          pred.get("comprehensive_probability",
                                                   pred.get("probability_calibrated", pred.get("probability")))),
            "calibration_delta": pred.get("calibration_delta", 0.0),
            "similar_samples": diag.get("similar_samples", 0),
            "gap_percentile": diag.get("gap_percentile", 0.0),
            "historical_gap_median": diag.get("historical_gap_median", 0.0),
            "three_hand_probability": diag.get("three_hand_probability"),
            "three_hand_similar_samples": diag.get("three_hand_similar_samples", 0),
            "total_extreme_context_active": diag.get("total_extreme_context_active", False),
            "total_extreme_context_probability": diag.get("total_extreme_context_probability"),
            "total_extreme_context_lift": diag.get("total_extreme_context_lift"),
            "total_extreme_context_samples": diag.get("total_extreme_context_samples", 0),
            "burst_pattern": diag.get("burst_pattern", False),
            "burst_eligible": diag.get("burst_eligible", False),
            "burst_previous_gap": diag.get("burst_previous_gap"),
            "burst_samples": diag.get("burst_samples", 0),
            "burst_rate": diag.get("burst_rate", 0.0),
            "burst_lift": diag.get("burst_lift", 0.0),
            "burst_boost": diag.get("burst_boost", 0.0),
            "gap_before_prediction": _gap_before(records, cursor, city_id),
        }
    items.append(snapshot)
    _write_log(items)
    summary = _build_summary(items, now)
    _write_summary(summary)
    return summary


def record_and_resolve(records, predictions, now=None):
    """兼容入口：先结算上一轮，再保存当前预测。"""
    now = now or datetime.now()
    resolve_pending(records, now)
    return record_snapshot(records, predictions, now)


if __name__ == "__main__":
    print("飞轮模块需要由日报脚本调用，以保存预测快照并按下一手真实记录结算。")
