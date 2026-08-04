#!/usr/bin/env python3
"""
斗鱼大话三国 - 集中配置文件
所有路径基于本文件所在目录动态计算，确保可移植性
"""
import os
import json

# ============================================================
# 基础路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw_records")
SUMMARY_DIR = os.path.join(DATA_DIR, "daily_summary")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# 数据文件路径
CSV_PATH = os.path.join(RAW_DIR, "records.csv")
TOWER_CSV_PATH = os.path.join(RAW_DIR, "tower_records.csv")
GAP_COUNTER_PATH = os.path.join(RAW_DIR, "gap_counter.json")
MODEL_PARAMS_PATH = os.path.join(DATA_DIR, "model_params.json")
CALIBRATION_LOG_PATH = os.path.join(DATA_DIR, "calibration_log.csv")
CALIBRATION_MODEL_PATH = os.path.join(DATA_DIR, "calibration_model.json")
MODEL_UPDATE_TEMPLATE_PATH = os.path.join(DATA_DIR, "model_update_template.json")
FLYWHEEL_LOG_PATH = os.path.join(DATA_DIR, "prediction_flywheel.jsonl")
FLYWHEEL_SUMMARY_PATH = os.path.join(DATA_DIR, "prediction_flywheel_summary.json")
ALERT_STATE_PATH = os.path.join(DATA_DIR, "alert_state.json")
NOTIFICATION_CONFIG_PATH = os.path.join(DATA_DIR, "notification_config.json")


def _load_notification_config():
    if not os.path.exists(NOTIFICATION_CONFIG_PATH):
        return {}
    try:
        with open(NOTIFICATION_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_NOTIFICATION_CONFIG = _load_notification_config()

# ============================================================
# API 配置
# ============================================================
API_URL_TEMPLATE = "https://tool.100if.com/douyuDefenseTower/api/v1/report/weekly?_time={timestamp_ms}"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

# ============================================================
# 城池配置
# ============================================================
CITY_MAP = {
    1: "洛阳", 2: "成都", 3: "建业", 4: "荆州", 5: "长安", 6: "许昌", 7: "汉中"
}
CITY_IDS = list(CITY_MAP.keys())

# 上三城：攻击频率最低的3个城池
TOP3_IDS = [1, 2, 3]  # 洛阳, 成都, 建业
TOP3_CITIES = [1, 2, 3]  # 别名，采集脚本使用
TOP3_NAMES = {1: "洛阳", 2: "成都", 3: "建业"}

# 前兆城配置
PRECURSOR_IDS = [4]  # 荆州
PRECURSOR_WEIGHTS = {4: 2}
PRECURSOR_NAMES = {4: "荆州"}
PRECURSOR_GAP_THRESHOLD = 20
PRECURSOR_LOOKBACK = 5
PRECURSOR_MIN_POSITIVE = 10
PRECURSOR_MIN_TOTAL = 30
STRENGTH_TIERS = ["弱", "中", "强"]

# 理论概率
THEORETICAL_PROB = {
    1: 0.031, 2: 0.056, 3: 0.083, 4: 0.131, 5: 0.190, 6: 0.277, 7: 0.231
}

# 条件概率间隔分段
GAP_BINS = [(0, 20), (21, 40), (41, 60), (61, 80), (81, 100), (101, float('inf'))]
GAP_BIN_LABELS = ["0-20", "21-40", "41-60", "61-80", "81-100", "100+"]

# 更细的间隔档位
FINE_GAP_BINS = [(0, 10), (11, 20), (21, 30), (31, 50), (51, 70), (71, 100), (101, float('inf'))]
FINE_GAP_BIN_LABELS = ["0-10", "11-20", "21-30", "31-50", "51-70", "71-100", "100+"]

# ============================================================
# 大胆模式配置
# ============================================================
BOLD_MODE = False
BOLD_FACTOR = 1.0
BOLD_DYNAMIC_AMPLIFICATION = 1.5
BOLD_RECALIBRATE = True
BOLD_BACKTEST_TRAIN_RATIO = 0.8
BOLD_GRID_SEARCH_FACTORS = [1.0, 1.2, 1.5, 2.0, 2.5, 3.0]

# ============================================================
# 校准参数
# ============================================================
EWMA_ALPHA = 0.3
BRIER_THRESHOLD = 0.1
ISOTONIC_MIN_SAMPLES = 200
ISOTONIC_MIN_POSITIVE = 30
CALIBRATION_N_BINS = 10
CALIBRATION_MIX_FACTOR = 50
CALIBRATION_ADJUSTMENT_WEIGHT = 0.35

# ============================================================
# 多特征融合模型配置
# ============================================================
FUSION_FEATURE_NAMES = [
    "gap_hands",
    "precursor_strength",
    "top3_count_10",
    "top3_count_30",
    "hour_sin",
    "hour_cos",
]
FUSION_FEATURE_DISPLAY = {
    "gap_hands": "间隔手数",
    "precursor_strength": "前兆强度分",
    "top3_count_10": "近10手上三次数",
    "top3_count_30": "近30手上三次数",
    "hour_sin": "时段正弦编码",
    "hour_cos": "时段余弦编码",
}

# 合并时段定义
PERIOD_DEFS = [
    ("凌晨", list(range(0, 6))),
    ("早", list(range(6, 9))),
    ("上午", list(range(9, 12))),
    ("午", list(range(12, 14))),
    ("下午", list(range(14, 18))),
    ("晚", list(range(18, 21))),
    ("深夜", list(range(21, 24))),
]
PERIOD_NAMES = [p[0] for p in PERIOD_DEFS]

FUSION_LOOKBACK_SHORT = 10
FUSION_LOOKBACK_MEDIUM = 30
FUSION_DAYTIME_START = 9
FUSION_DAYTIME_END = 23
FUSION_MIN_POSITIVE = 20
FUSION_MIN_TOTAL = 50
FUSION_L2_C = 5.0
FUSION_CATEGORIES = ["any_top3", "洛阳", "成都", "建业"]

# ============================================================
# 弹性交叉特征模型配置（30维）
# ============================================================
ELASTIC_FEATURE_NAMES = [
    "gap_hands",
    "precursor_strength",
    "top3_count_10",
    "top3_count_30",
    "hour_sin",
    "hour_cos",
    "gap_sqrt",
    "gap_squared",
    "gap_x_period_morning",
    "gap_x_period_afternoon",
    "gap_x_period_evening",
    "gap_x_period_night",
    "precursor_x_period_morning",
    "precursor_x_period_afternoon",
    "precursor_x_period_evening",
    "precursor_x_period_night",
    "freq10_x_period_morning",
    "freq10_x_period_afternoon",
    "freq10_x_period_evening",
    "freq10_x_period_night",
    "prev_top3_is_luoyang",
    "prev_top3_is_chengdu",
    "prev_top3_is_jianye",
    "gap_long_bonus",
    "prev_luoyang_x_gap",
    "prev_chengdu_x_gap",
    "prev_jianye_x_gap",
    "prev_luoyang_x_precursor",
    "prev_chengdu_x_precursor",
    "prev_jianye_x_precursor",
]

ELASTIC_FEATURE_DISPLAY = {
    "gap_hands": "间隔手数",
    "precursor_strength": "前兆强度分",
    "top3_count_10": "近10手上三次数",
    "top3_count_30": "近30手上三次数",
    "hour_sin": "时段正弦编码",
    "hour_cos": "时段余弦编码",
    "gap_sqrt": "间隔平方根(非线性)",
    "gap_squared": "间隔平方(非线性)",
    "gap_x_period_morning": "间隔×上午交叉",
    "gap_x_period_afternoon": "间隔×下午交叉",
    "gap_x_period_evening": "间隔×晚间交叉",
    "gap_x_period_night": "间隔×深夜交叉",
    "precursor_x_period_morning": "前兆×上午交叉",
    "precursor_x_period_afternoon": "前兆×下午交叉",
    "precursor_x_period_evening": "前兆×晚间交叉",
    "precursor_x_period_night": "前兆×深夜交叉",
    "freq10_x_period_morning": "近10手频率×上午交叉",
    "freq10_x_period_afternoon": "近10手频率×下午交叉",
    "freq10_x_period_evening": "近10手频率×晚间交叉",
    "freq10_x_period_night": "近10手频率×深夜交叉",
    "prev_top3_is_luoyang": "上一城=洛阳(马尔可夫)",
    "prev_top3_is_chengdu": "上一城=成都(马尔可夫)",
    "prev_top3_is_jianye": "上一城=建业(马尔可夫)",
    "gap_long_bonus": "长间隔加成(gap≥50)",
    "prev_luoyang_x_gap": "上一城洛阳×间隔",
    "prev_chengdu_x_gap": "上一城成都×间隔",
    "prev_jianye_x_gap": "上一城建业×间隔",
    "prev_luoyang_x_precursor": "上一城洛阳×前兆",
    "prev_chengdu_x_precursor": "上一城成都×前兆",
    "prev_jianye_x_precursor": "上一城建业×前兆",
}

ELASTIC_L2_C = 2.0
ELASTIC_MIN_POSITIVE = 30
ELASTIC_MIN_TOTAL = 100

# 子模型配置
SUB_MODEL_NAMES = ["gap_only", "precursor", "frequency", "period"]
SUB_MODEL_DISPLAY = {
    "gap_only": "间隔模型",
    "precursor": "前兆模型",
    "frequency": "频率模型",
    "period": "时段模型",
}
DYNAMIC_WEIGHT_WINDOW = 200
SELF_TEST_TRAIN_RATIO = 0.7
SELF_TEST_N_BINS = 10

# 间隔经验模型：以历史上“当前已等待手数 -> 下一手是否命中”为样本。
# 核窗口随间隔放宽，并用全局命中率做贝叶斯平滑，避免稀疏长间隔产生虚高概率。
EXPERIENCE_BLEND_WEIGHT = 0.65
EXPERIENCE_PRIOR_STRENGTH = 24.0
EXPERIENCE_MIN_BANDWIDTH = 2.0
EXPERIENCE_BANDWIDTH_RATIO = 0.18
MODEL_UPDATE_TEMPLATE_VERSION = 2

# ============================================================
# 告警通知配置
# ============================================================
WECHAT_SCTKEY = os.environ.get("WECHAT_SCTKEY", _NOTIFICATION_CONFIG.get("wechat_sctkey", "")).strip()
BARK_PUSH_URL = os.environ.get("BARK_PUSH_URL", _NOTIFICATION_CONFIG.get("bark_push_url", "")).strip()
ALERT_TRIGGER_LEVEL = "极高"
