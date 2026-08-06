#!/usr/bin/env bash
# ShowCode 一键部署/运维脚本
#   sudo ./deploy.sh          # 完整部署（nginx + 后端，首次迁移用）
#   sudo ./deploy.sh start    # 仅启动后端 server.py:3000
#   sudo ./deploy.sh stop     # 停止后端
#   sudo ./deploy.sh restart  # 重启后端
#   sudo ./deploy.sh status   # 查看运行状态
#   sudo ./deploy.sh service  # 安装为 systemd 开机自启服务
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PY="python3 $DIR/server.py"
PID_FILE="/var/run/nowcoding.pid"
LOG_FILE="/var/log/nowcoding.log"
NGINX_EN="/etc/nginx/sites-enabled/nowcoding"

start_backend() {
  if pgrep -f "$PY" >/dev/null; then echo "后端已在运行"; return; fi
  mkdir -p /var/log
  touch "$LOG_FILE"
  chown "$SUDO_USER:$SUDO_USER" "$LOG_FILE" 2>/dev/null || true
  nohup $PY > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 1
  pgrep -f "$PY" >/dev/null && echo "后端已启动 (PID $(cat $PID_FILE))，日志 $LOG_FILE" || { echo "启动失败，查 $LOG_FILE"; exit 1; }
}

stop_backend() {
  pkill -f "$PY" 2>/dev/null && echo "后端已停止" || echo "后端未运行"
}

case "${1:-deploy}" in
  start)   start_backend ;;
  stop)    stop_backend ;;
  restart) stop_backend; sleep 1; start_backend ;;
  status)  pgrep -fa "$PY" | grep -v grep || echo "未运行" ;;
  service)
    cat > /tmp/nowcoding.service << EOF
[Unit]
Description=ShowCode Backend (server.py:3000)
After=network.target
[Service]
Type=simple
ExecStart=$PY
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
    cp /tmp/nowcoding.service /etc/systemd/system/nowcoding.service
    systemctl daemon-reload
    systemctl enable --now nowcoding
    echo "已安装并启动 systemd 服务"
    ;;
  deploy)
    [ "$EUID" -ne 0 ] && { echo "请用 sudo 运行：sudo $0"; exit 1; }
    echo "[1/2] 配置 nginx..."
    [ -e "$NGINX_EN" ] && [ ! -L "$NGINX_EN" ] && cp "$NGINX_EN" "${NGINX_EN}.bak.$(date +%s)"
    ln -sf "$DIR/nginx.nowcoding.conf" "$NGINX_EN"
    nginx -t
    systemctl reload nginx || service nginx reload
    echo "[2/2] 启动后端..."
    start_backend
    echo "完成 → http://$(hostname -I | awk '{print $1}')/"
    ;;
  *) echo "用法: sudo $0 [deploy|start|stop|restart|status|service]"; exit 1 ;;
esac