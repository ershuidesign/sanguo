#!/usr/bin/env python3
"""最简单的本地网页：展示日报里的“快速预测”表格，并支持一键刷新。"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import json
import os
import time
from zipfile import BadZipFile
from datetime import datetime

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"
PROJECT_VERSION = "1.0"
WEB_HEADER_MAP = {
    "目标": "目标",
    "当前间隔(手)": "当前间隔",
    "校准概率": "综合预测概率",
    "概率等级": "概率等级",
    "历史中位间隔": "历史中位间隔",
    "5手累计": "5手累计",
}


def find_latest_report():
    candidates = sorted(OUTPUT_DIR.glob("defense_summary_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _fmt_percent(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "-"


def load_quick_prediction():
    if load_workbook is None:
        return {"error": "缺少 openpyxl，无法读取 Excel。"}

    report = find_latest_report()
    if report is None:
        return {"error": "没有找到日报文件，请先运行 daily_defense_summary.py。"}

    wb = None
    for attempt in range(3):
        try:
            wb = load_workbook(report, data_only=True)
            break
        except (BadZipFile, PermissionError, OSError):
            if attempt == 2:
                return {"error": "日报正在更新，请稍后刷新。"}
            time.sleep(0.15)
    if "快速预测" not in wb.sheetnames:
        return {"error": "日报里没有“快速预测”页。"}

    ws = wb["快速预测"]
    title = ws.cell(row=1, column=1).value or "快速预测"
    headers = []
    for c in range(1, ws.max_column + 1):
        value = ws.cell(row=3, column=c).value
        if value in (None, ""):
            break
        headers.append(value)

    visible_headers = [header for header in headers if header in WEB_HEADER_MAP]
    display_headers = [WEB_HEADER_MAP[header] for header in visible_headers]

    rows = []
    for r in range(4, ws.max_row + 1):
        first = ws.cell(row=r, column=1).value
        if first in (None, ""):
            continue
        row = {}
        for c, header in enumerate(headers, 1):
            if header not in visible_headers:
                continue
            value = ws.cell(row=r, column=c).value
            display_header = WEB_HEADER_MAP[header]
            if header in ("预测概率", "校准概率", "校准前后差值", "经验间隔概率", "间隔分位", "5手累计"):
                row[display_header] = _fmt_percent(value)
            elif header == "相对倍率":
                row[display_header] = round(float(value), 2) if value is not None else None
            else:
                row[display_header] = value
        rows.append(row)

    return {
        "title": title,
        "report": report.name,
        "updated_at": datetime.fromtimestamp(report.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "headers": display_headers,
        "rows": rows,
    }


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>快速预测</title>
  <style>
    :root {
      --bg: #f4f0e8;
      --panel: rgba(255,255,255,0.86);
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #1d4ed8;
      --border: #d6d3d1;
      --shadow: 0 12px 32px rgba(0,0,0,0.10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(29,78,216,0.16), transparent 30%),
        radial-gradient(circle at top right, rgba(245,158,11,0.16), transparent 28%),
        linear-gradient(180deg, #faf7f2, #f1efe9 55%, #ece7de);
      min-height: 100vh;
    }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 28px 18px 40px; }
    .hero {
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(214,211,209,0.75);
      box-shadow: var(--shadow);
      border-radius: 20px;
      padding: 24px;
      margin-bottom: 18px;
    }
    h1 { margin: 0 0 10px; font-size: 30px; letter-spacing: 0.02em; }
    .sub { color: var(--muted); line-height: 1.6; font-size: 14px; }
    .toolbar { display: flex; gap: 12px; align-items: center; margin-top: 18px; flex-wrap: wrap; }
    .meta { color: var(--muted); font-size: 13px; }
    .refresh-progress { width: 100%; margin-top: 12px; }
    .refresh-countdown {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }
    .refresh-seconds {
      min-width: 48px;
      padding: 3px 9px;
      color: #0369a1;
      background: rgba(14,165,233,0.10);
      border: 1px solid rgba(14,165,233,0.30);
      border-radius: 7px;
      font-weight: 700;
      text-align: center;
      font-variant-numeric: tabular-nums;
    }
    .refresh-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 10px rgba(16,185,129,0.85);
    }
    .refresh-track {
      height: 3px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(14,165,233,0.12);
    }
    .refresh-bar {
      width: 100%;
      height: 100%;
      transform-origin: left center;
      background: linear-gradient(90deg, #0ea5e9, #06b6d4);
      transition: transform 0.25s linear;
    }
    .card {
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(214,211,209,0.75);
      box-shadow: var(--shadow);
      border-radius: 20px;
      overflow: hidden;
    }
    table { width: 100%; border-collapse: collapse; }
    thead th {
      background: #22304a;
      color: #fff;
      text-align: left;
      font-weight: 600;
      padding: 14px 12px;
      font-size: 14px;
      white-space: nowrap;
    }
    tbody td {
      border-top: 1px solid var(--border);
      padding: 13px 12px;
      font-size: 14px;
      white-space: nowrap;
    }
    tbody tr:hover { background: rgba(29,78,216,0.04); }
    .pill {
      display: inline-block;
      padding: 4px 9px;
      border-radius: 999px;
      background: rgba(29,78,216,0.10);
      color: #1e3a8a;
      font-weight: 600;
    }
    .err { color: #b91c1c; padding: 18px 0; }
    .footer { color: var(--muted); font-size: 12px; padding: 10px 2px 0; }
    .table-wrap { overflow-x: auto; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1 id="title">快速预测</h1>
      <div class="sub" id="subtitle">正在读取最新日报...</div>
      <div class="toolbar">
        <div class="meta" id="status">等待加载</div>
      </div>
      <div class="refresh-progress">
        <div class="refresh-countdown">
          <span id="countdownLabel">距数据更新还有</span>
          <span class="refresh-seconds" id="countdownSeconds">--s</span>
          <span class="refresh-dot"></span>
        </div>
        <div class="refresh-track"><div class="refresh-bar" id="refreshBar"></div></div>
      </div>
    </div>
    <div class="card">
      <div class="table-wrap">
        <table>
          <thead><tr id="thead"></tr></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </div>
    <div class="footer">本地页面自动读取最新的 `defense_summary_*.xlsx` · 项目版本 1.0</div>
  </div>
  <script>
    const title = document.getElementById('title');
    const subtitle = document.getElementById('subtitle');
    const statusEl = document.getElementById('status');
    const countdownLabel = document.getElementById('countdownLabel');
    const countdownSeconds = document.getElementById('countdownSeconds');
    const refreshBar = document.getElementById('refreshBar');
    const thead = document.getElementById('thead');
    const tbody = document.getElementById('tbody');
    let autoTimer = null;
    let countdownTimer = null;
    let autoBusy = false;
    let nextRefreshAt = null;
    let lastUpdatedAt = '';
    const REPORT_WAIT_MS = 20000;
    const REPORT_POLL_MS = 1000;
    function renderTable(data) {
      thead.innerHTML = '';
      tbody.innerHTML = '';
      (data.headers || []).forEach(h => {
        const th = document.createElement('th');
        th.textContent = h || '';
        thead.appendChild(th);
      });
      (data.rows || []).forEach(row => {
        const tr = document.createElement('tr');
        (data.headers || []).forEach(h => {
          const td = document.createElement('td');
          const value = row[h];
          if (h === '概率等级' && value) {
            const span = document.createElement('span');
            span.className = 'pill';
            span.textContent = value;
            td.appendChild(span);
          } else {
            td.textContent = value === null || value === undefined ? '' : value;
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }

    function clearAutoTimer() {
      if (autoTimer) {
        clearTimeout(autoTimer);
        autoTimer = null;
      }
      if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
      }
    }

    function updateCountdown() {
      if (!nextRefreshAt) return;
      const remainingMs = Math.max(0, nextRefreshAt.getTime() - Date.now());
      const remainingSeconds = Math.ceil(remainingMs / 1000);
      const progress = Math.max(0, Math.min(1, remainingMs / 60000));
      countdownLabel.textContent = autoBusy ? '正在获取最新数据' : '距数据更新还有';
      countdownSeconds.textContent = autoBusy ? '刷新中' : `${remainingSeconds}s`;
      refreshBar.style.transform = `scaleX(${autoBusy ? 0.04 : progress})`;
    }

    function scheduleAutoRefresh() {
      clearAutoTimer();
      const now = new Date();
      const next = new Date(now);
      next.setSeconds(5, 0);
      if (next <= now) {
        next.setMinutes(next.getMinutes() + 1);
      }
      const delay = next.getTime() - now.getTime();
      nextRefreshAt = next;
      updateCountdown();
      countdownTimer = setInterval(updateCountdown, 250);
      autoTimer = setTimeout(async () => {
        if (autoBusy) {
          scheduleAutoRefresh();
          return;
        }
        autoBusy = true;
        updateCountdown();
        try {
          // 05秒先读一次；日报通常在09-12秒写完，随后静默追踪新版本。
          await loadData(false, true);
        } finally {
          autoBusy = false;
          scheduleAutoRefresh();
        }
      }, delay);
      statusEl.textContent = `自动采集已开启，下次刷新时间：${next.toLocaleTimeString('zh-CN', { hour12: false })}`;
    }

    async function fetchPayload() {
      const res = await fetch('/api/quick-prediction?ts=' + Date.now(), { cache: 'no-store' });
      return res.json();
    }

    async function loadData(reschedule = true, waitForNewReport = false) {
      try {
        let data = await fetchPayload();
        if (waitForNewReport && lastUpdatedAt) {
          const deadline = Date.now() + REPORT_WAIT_MS;
          while (!data.error && data.updated_at === lastUpdatedAt && Date.now() < deadline) {
            await new Promise(resolve => setTimeout(resolve, REPORT_POLL_MS));
            data = await fetchPayload();
          }
        }
        if (data.error) throw new Error(data.error);
        title.textContent = data.title || '快速预测';
        const refreshed = data.pipeline_updated_at ? ` · 采集完成: ${data.pipeline_updated_at}` : '';
        subtitle.textContent = `来源: ${data.report} · 报表时间: ${data.updated_at}${refreshed}`;
        lastUpdatedAt = data.updated_at || lastUpdatedAt;
        renderTable(data);
      } catch (err) {
        tbody.innerHTML = '<tr><td class="err" colspan="' + Math.max((thead.children || []).length, 1) + '">' + err.message + '</td></tr>';
      } finally {
        if (reschedule) {
          scheduleAutoRefresh();
        }
      }
    }

    loadData().then(() => {
      scheduleAutoRefresh();
    });
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, content, content_type="text/html; charset=utf-8", status=200):
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(HTML)
            return
        if parsed.path == "/api/quick-prediction":
            payload = load_quick_prediction()
            self._send(json.dumps(payload, ensure_ascii=False), content_type="application/json; charset=utf-8")
            return
        self._send("Not Found", status=404)

    def log_message(self, format, *args):
        return


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main():
    host = os.environ.get("QUICK_PREDICTION_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("QUICK_PREDICTION_PORT", "8000"))
    except ValueError:
        port = 8000
    server = None
    last_error = None
    for candidate_port in range(port, port + 11):
        try:
            server = ReusableThreadingHTTPServer((host, candidate_port), Handler)
            port = candidate_port
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        raise OSError(f"无法启动本地网页服务，已尝试端口 {port}-{port + 10}: {last_error}")
    port_file = BASE_DIR / "logs" / "quick_prediction_web.port"
    port_file.parent.mkdir(parents=True, exist_ok=True)
    port_file.write_text(str(port), encoding="utf-8")
    print(f"快速预测网页已启动: http://{host}:{port}", flush=True)
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    finally:
        try:
            port_file.unlink()
        except FileNotFoundError:
            pass
        server.server_close()


if __name__ == "__main__":
    main()
