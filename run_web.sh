#!/bin/bash
set -e
cd "$(dirname "$0")"
LOG_FILE="logs/quick_prediction_web.log"
PID_FILE="logs/quick_prediction_web.pid"
PORT_FILE="logs/quick_prediction_web.port"
LAUNCHD_LABEL="local.sanguo.quick-prediction-web"
LAUNCHD_PLIST="$PWD/logs/$LAUNCHD_LABEL.plist"
HOST="${QUICK_PREDICTION_HOST:-127.0.0.1}"
PORT="${QUICK_PREDICTION_PORT:-8002}"
PYTHON_BIN="$(command -v python3)"
SCREEN_NAME="sanguo_quick_web"

wait_until_ready() {
  for _ in $(seq 1 30); do
    if [ -f "$PORT_FILE" ] && curl -fsS --max-time 2 "http://127.0.0.1:$(cat "$PORT_FILE")/api/quick-prediction" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  if [ -f "$PORT_FILE" ] && curl -fsS --max-time 2 "http://127.0.0.1:$(cat "$PORT_FILE")/api/quick-prediction" >/dev/null 2>&1; then
    echo "快速预测网页已在运行: http://127.0.0.1:$(cat "$PORT_FILE")"
    exit 0
  fi
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
fi

if command -v screen >/dev/null 2>&1; then
  screen -S "$SCREEN_NAME" -X quit >/dev/null 2>&1 || true
  screen -dmS "$SCREEN_NAME" bash -lc "cd \"$PWD\" && QUICK_PREDICTION_HOST=\"$HOST\" QUICK_PREDICTION_PORT=\"$PORT\" \"$PYTHON_BIN\" scripts/quick_prediction_web.py >> \"$LOG_FILE\" 2>&1"
elif command -v launchctl >/dev/null 2>&1 && [ "$(uname)" = "Darwin" ]; then
  cat > "$LAUNCHD_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LAUNCHD_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd "$PWD" && while true; do "$PYTHON_BIN" scripts/quick_prediction_web.py; sleep 1; done</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>QUICK_PREDICTION_HOST</key>
    <string>$HOST</string>
    <key>QUICK_PREDICTION_PORT</key>
    <string>$PORT</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$PWD/$LOG_FILE</string>
  <key>StandardErrorPath</key>
  <string>$PWD/$LOG_FILE</string>
  <key>WorkingDirectory</key>
  <string>$PWD</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)" "$LAUNCHD_PLIST" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
  launchctl kickstart -k "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
else
  # Keep the local page alive when launched outside launchd/screen.
  nohup bash -lc 'while true; do QUICK_PREDICTION_HOST="$1" QUICK_PREDICTION_PORT="$2" python3 scripts/quick_prediction_web.py >> "$3" 2>&1; sleep 1; done' _ "$HOST" "$PORT" "$LOG_FILE" >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
fi

if ! wait_until_ready; then
  echo "网页启动失败或没有通过健康检查，请查看 $LOG_FILE" >&2
  tail -20 "$LOG_FILE" >&2
  exit 1
fi

echo "快速预测网页已启动"
if [ -f "$PORT_FILE" ]; then
  echo "访问地址: http://127.0.0.1:$(cat "$PORT_FILE")"
fi
