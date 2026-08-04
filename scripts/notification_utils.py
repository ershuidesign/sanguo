#!/usr/bin/env python3
"""通知工具：微信 Server酱 + Bark 双通道。"""

from __future__ import annotations

import urllib.parse
import urllib.request
import ssl

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WECHAT_SCTKEY, BARK_PUSH_URL


def _https_context():
    """使用 certifi 的 CA 列表，修复部分 macOS Python 缺少系统证书的问题。"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def send_wechat_alert(title: str, body: str) -> dict:
    if not WECHAT_SCTKEY:
        return {"channel": "wechat", "ok": False, "reason": "missing_sctkey"}
    api_url = f"https://sctapi.ftqq.com/{WECHAT_SCTKEY}.send"
    payload = urllib.parse.urlencode({"title": title, "desp": body}).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12, context=_https_context()) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
        return {"channel": "wechat", "ok": True, "response": text[:300]}
    except Exception as exc:
        return {"channel": "wechat", "ok": False, "reason": str(exc)}


def send_bark_alert(title: str, body: str) -> dict:
    if not BARK_PUSH_URL:
        return {"channel": "bark", "ok": False, "reason": "missing_bark_url"}
    params = urllib.parse.urlencode({
        "title": title,
        "body": body,
        "group": "斗鱼大话三国",
        "level": "active",
        "icon": "https://raw.githubusercontent.com/Finb/Bark/master/Resources/Assets.xcassets/AppIcon.appiconset/Icon-App-60x60@3x.png",
    })
    url = f"{BARK_PUSH_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "sanguo-alert/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12, context=_https_context()) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
        return {"channel": "bark", "ok": True, "response": text[:300]}
    except Exception as exc:
        return {"channel": "bark", "ok": False, "reason": str(exc)}


def send_dual_channel_alert(title: str, body: str) -> list[dict]:
    return [send_wechat_alert(title, body), send_bark_alert(title, body)]
