# 斗鱼大话三国 - 上三城概率预测系统

## 项目简介

斗鱼大话三国上三城概率预测系统，通过定时采集 API 数据，运用统计分析和机器学习模型，预测上三城（洛阳、成都、建业）的出现概率。

**核心功能：**
- 每小时自动采集斗鱼大话三国 API 数据
- 每日生成包含 7 个 Sheet 的 Excel 分析报告
- 30 维弹性融合模型（逻辑回归 + 特征工程）
- 概率校准（Platt 缩放 + 保序回归）

**数据来源：**
`https://tool.100if.com/douyuDefenseTower/api/v1/report/weekly`

**7 个城池：**
洛阳(1)、成都(2)、建业(3)、荆州(4)、长安(5)、许昌(6)、汉中(7)

**上三城（稀有城池）：** 洛阳(1)、成都(2)、建业(3)

**前兆城：** 荆州(4) — 上三城出现的前兆信号

---

## 目录结构

```
sanguo_codex_package/
├── config.py                        # 集中配置文件
├── scripts/
│   ├── collect_defense_data.py      # 数据采集脚本
│   └── daily_defense_summary.py     # 日报生成脚本
├── data/
│   ├── raw_records/
│   │   ├── records.csv              # 获胜城记录（历史兼容）
│   │   ├── tower_records.csv        # 上三城进攻记录（间隔追踪）
│   │   └── gap_counter.json         # 间隔计数器
│   └── output/                      # Excel 报告输出目录
├── logs/                            # 日志目录
├── setup.sh                         # 环境安装脚本
├── crontab.txt                      # 定时任务模板
└── README.md                        # 本文档
```

---

## 部署步骤

### 1. 准备环境

```bash
# Python 3.7+ 必需
python3 --version

# 解压项目包
unzip sanguo_codex_package.zip
cd sanguo_codex_package
```

### 2. 安装依赖

```bash
bash setup.sh
```

依赖列表：`numpy`, `scipy`, `scikit-learn`, `openpyxl`, `requests`

### 3. 配置定时任务

```bash
# 编辑 crontab
crontab -e

# 粘贴 crontab.txt 内容，修改路径为实际部署路径
```

或手动运行：
```bash
# 采集数据
python scripts/collect_defense_data.py

# 生成日报
python scripts/daily_defense_summary.py
```

---

## 脚本使用说明

### calibrate_collected_data.py — 校准已采集数据

```bash
python scripts/calibrate_collected_data.py
```

**功能：**
- 清洗 `records.csv` 和 `tower_records.csv`
- 合并重复记录
- 重新计算 `gap_counter.json`
- 适合在修复采集异常后手动执行一次

### collect_defense_data.py — 数据采集

```bash
python scripts/collect_defense_data.py
```

**功能：**
- 请求 API 获取最新数据
- 从 `report_minute_tower` 提取上三城进攻记录（**过滤未来分钟**）
- 从 `report_minute` 提取获胜城记录（兼容历史数据）
- 重建间隔计数器 `gap_counter.json`

**输出示例：**
```
[2024-01-15 14:05:01] 采集完成
tower新增3条(累计128) | minute新增5条(累计1520) | 上三城间隔: 洛阳: 45手  成都: 23手  建业: 67手
```

**关键逻辑：**
- `process_tower_data()`: 从 `report_minute_tower` 提取上三城进攻，**必须过滤未来分钟** (`mm <= current_minute`)
- `process_report_minute()`: 从 `report_minute` 提取获胜城记录（兼容历史）
- `update_gap_counter_from_tower()`: 从 tower CSV 重建间隔计数器

### daily_defense_summary.py — 日报生成

```bash
# 默认分析今天的数据
python scripts/daily_defense_summary.py

# 指定日期
python scripts/daily_defense_summary.py 2024-01-15
```

**输出：**
- Excel 报告保存到 `data/output/defense_summary_YYYY-MM-DD.xlsx`
- 摘要打印到 stdout

### 极高预警通知（微信 + Bark）

当洛阳、成都、建业任一城池的`概率等级 = 极高`时，系统可自动双通道推送：
- 微信：`Server酱 Turbo`
- iPhone：`Bark`

配置方式：

```bash
export WECHAT_SCTKEY="你的Server酱SendKey"
export BARK_PUSH_URL="https://api.day.app/你的BarkKey"
```

也可以直接写入项目配置文件：

`data/notification_config.json`

```json
{
  "wechat_sctkey": "你的Server酱SendKey",
  "bark_push_url": "https://api.day.app/你的BarkKey/"
}
```

优先级说明：
- 环境变量优先
- 若未设置环境变量，则自动读取 `data/notification_config.json`

然后照常运行：

```bash
python scripts/daily_defense_summary.py
```

通知内容包含：
- 城池名
- 概率等级
- 当前间隔
- 综合预测概率
- 历史中位间隔
- 5手累计

去重规则：
- 如果同一轮极高状态未变化，不会重复推送
- 只有极高目标、间隔或概率发生变化时，才会再次推送

### 手动测试通知

如果你想立即验证双通道是否打通，可以手动执行：

```bash
python scripts/test_notification.py
```

### GitHub Actions 部署

仓库已提供 `.github/workflows/collect.yml`：默认每 5 分钟执行采集、校准、日报和通知，并将新的 `data/` 文件提交回 `main`。GitHub Actions 不能保证每分钟 0.5 秒执行；需要严格每分钟运行时，应使用本机常驻循环或云端 Worker。

在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 添加：

- `WECHAT_SCTKEY`
- `BARK_PUSH_URL`

保存后可在 `Actions -> Test notifications -> Run workflow` 手动测试双通道通知。`Collect and predict` 也支持 `Run workflow` 手动执行。

执行后会：
- 给微信 Server酱发送一条测试消息
- 给 Bark 发送一条测试消息
- 终端输出两边的发送结果

---

## 数据文件格式

### records.csv（获胜城记录）

| 字段 | 说明 | 示例 |
|------|------|------|
| date | 日期 | 2024-01-15 |
| time | 时间 | 14:05 |
| city_id | 城池ID | 1 |
| city_name | 城池名 | 洛阳 |

### tower_records.csv（上三城进攻记录）

| 字段 | 说明 | 示例 |
|------|------|------|
| date | 日期 | 2024-01-15 |
| time | 时间 | 14:05 |
| city_id | 城池ID (1/2/3) | 1 |
| city_name | 城池名 | 洛阳 |
| attack_count | 进攻次数 | 3 |

### gap_counter.json（间隔计数器）

```json
{
  "1": {"last_seen_time": "2024-01-15 13:20", "gap_hands": 45},
  "2": {"last_seen_time": "2024-01-15 14:00", "gap_hands": 5},
  "3": {"last_seen_time": "2024-01-15 12:30", "gap_hands": 95}
}
```

---

## 模型架构说明

### 30 维弹性融合模型

基于逻辑回归的 30 维特征工程模型，分为以下几类特征：

| 类别 | 维度数 | 特征 |
|------|--------|------|
| 基线特征 | 6 | 间隔手数、前兆强度、近10/30手频率、时段正弦/余弦编码 |
| 非线性特征 | 2 | 间隔平方根、间隔平方 |
| 时段交叉 | 12 | 间隔×时段、前兆×时段、频率×时段（各4个时段） |
| 马尔可夫特征 | 3 | 上一城是否为洛阳/成都/建业 |
| 长间隔加成 | 1 | gap≥50 时启用 |
| 交叉特征 | 6 | 上一城×间隔、上一城×前兆 |

### 模型训练策略

1. **优先 30 维弹性模型**：需要 `ELASTIC_MIN_POSITIVE=30` 正例、`ELASTIC_MIN_TOTAL=100` 总样本
2. **降级 6 维基线模型**：弹性模型样本不足时自动降级
3. **兜底指数衰减模型**：所有模型均不可用时使用理论概率 + 指数衰减

### 概率校准

- **Platt 缩放**：逻辑回归拟合校准曲线
- **保序回归**：非参数校准方法
- **EWMA 平滑**：α=0.3 的时间加权移动平均

### Excel 报告（7 个 Sheet）

| Sheet | 内容 |
|-------|------|
| 快速预测 | 当前概率、校准概率、累计概率 |
| 城池统计 | 各城攻击次数、实际/理论概率、卡方检验 |
| 间隔统计 | 上三城间隔均值/中位/极值 |
| 条件概率 | 按间隔分段的条件概率 |
| 特征分析 | 模型特征重要性排序 |
| 时段分析 | 分时段上三城命中率 |
| 模型自检 | 数据量、模型状态、建议 |

---

## API 数据源

**接口地址：**
```
GET https://tool.100if.com/douyuDefenseTower/api/v1/report/weekly?_time={timestamp_ms}
```

**响应结构：**
```json
{
  "status": {"code": 0},
  "data": [{
    "report_minute_tower": {
      "1": {"0": 0, "1": 2, "2": 0, ...},  // 洛阳每分钟的进攻次数
      "2": {"0": 1, "1": 0, ...},           // 成都
      "3": {"0": 0, "1": 0, ...}            // 建业
    },
    "report_minute": [
      {"14:05": 1},  // 该分钟获胜城为洛阳
      {"14:04": 5},
      ...
    ]
  }]
}
```

**注意事项：**
- `report_minute_tower` 可能包含未来分钟数据（服务器时间偏差），采集时必须过滤
- 理论概率分布：洛阳 3.1%、成都 5.6%、建业 8.3%、荆州 13.1%、长安 19.0%、许昌 27.7%、汉中 23.1%

---

## 许可与声明

本项目仅供学习和研究使用。预测结果基于历史数据统计分析，不构成任何投资或决策建议。
