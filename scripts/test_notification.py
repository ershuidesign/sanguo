#!/usr/bin/env python3
"""手动测试通知：一键同时发送微信和 Bark。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from notification_utils import send_dual_channel_alert


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"斗鱼大话三国通知测试 {now}"
    body = (
        "这是一条手动测试通知。\n"
        "如果你同时收到了微信 Server酱和 Bark，说明双通道通知已经打通。"
    )
    results = send_dual_channel_alert(title, body)
    print(json.dumps({
        "title": title,
        "body": body,
        "results": results,
    }, ensure_ascii=False, indent=2))
    if not any(item.get("ok") for item in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
