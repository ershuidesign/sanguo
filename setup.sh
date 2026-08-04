#!/bin/bash
# 斗鱼大话三国 - 环境安装脚本
set -e

echo "=== 斗鱼大话三国 环境安装 ==="

# 安装 Python 依赖
# 优先安装可用的核心库；离线环境下如果某些包不可获取，不要直接中断整个部署流程。
python3 -m pip install --user numpy scikit-learn openpyxl requests || true
python3 -m pip install --user scipy || true

echo ""
echo "=== 安装完成 ==="
echo "请确保 Python 3.7+ 已安装"
echo "运行采集: python scripts/collect_defense_data.py"
echo "运行日报: python scripts/daily_defense_summary.py"
