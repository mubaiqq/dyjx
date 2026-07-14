#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/mubaiqq/dyjx.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/dyjx}"
SERVICE_NAME="${SERVICE_NAME:-dyjx}"
PORT="${PORT:-5800}"
RUN_USER="${RUN_USER:-${SUDO_USER:-${USER:-root}}}"
RUN_GROUP="${RUN_GROUP:-}"
HEALTH_URL="http://127.0.0.1:${PORT}/healthz"
BACKUP_DIR=""
SERVICE_BACKUP=""
WORK_DIR=""
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
UNIT_EXISTED=0
WAS_ENABLED=0
WAS_ACTIVE=0
INSTALL_EXISTED=0

if [ "$(id -u)" -ne 0 ]; then
    echo "[错误] 此脚本需要 root 权限，请使用 sudo 运行。" >&2
    exit 1
fi

log() { printf '\033[1;34m[dyjx]\033[0m %s\n' "$*"; }
ok() { printf '\033[1;32m[完成]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[错误]\033[0m %s\n' "$*" >&2; exit 1; }

validate_value() {
    local name="$1" value="$2" pattern="$3"
    [[ "$value" =~ $pattern ]] || fail "$name 的值不合法：$value"
}

validate_value "SERVICE_NAME" "$SERVICE_NAME" '^[A-Za-z0-9_.@-]+$'
validate_value "RUN_USER" "$RUN_USER" '^[A-Za-z_][A-Za-z0-9_-]*[$]?$'
validate_value "PORT" "$PORT" '^[0-9]{1,5}$'
validate_value "BRANCH" "$BRANCH" '^[A-Za-z0-9._/-]+$'
validate_value "INSTALL_DIR" "$INSTALL_DIR" '^/[A-Za-z0-9._/-]+$'
[ "$PORT" -ge 1 ] && [ "$PORT" -le 65535 ] || fail "PORT 必须在 1-65535 之间"
case "$INSTALL_DIR" in
    /|/bin|/boot|/dev|/etc|/home|/lib|/lib64|/opt|/proc|/root|/run|/sbin|/srv|/sys|/tmp|/usr|/var)
        fail "INSTALL_DIR 不能使用系统关键目录：$INSTALL_DIR" ;;
esac
[[ "$INSTALL_DIR" != *'/../'* && "$INSTALL_DIR" != */.. && "$INSTALL_DIR" != *'/./'* ]] || fail "INSTALL_DIR 不允许包含 . 或 .. 路径段"
[[ "$REPO_URL" != -* && "$REPO_URL" != *$'\n'* && "$REPO_URL" != *$'\r'* ]] || fail "REPO_URL 不合法"
id "$RUN_USER" >/dev/null 2>&1 || fail "运行用户不存在：$RUN_USER"
if [ -z "$RUN_GROUP" ]; then RUN_GROUP="$(id -gn "$RUN_USER")"; fi
validate_value "RUN_GROUP" "$RUN_GROUP" '^[A-Za-z_][A-Za-z0-9_-]*[$]?$'
getent group "$RUN_GROUP" >/dev/null 2>&1 || fail "运行用户组不存在：$RUN_GROUP"

install_packages() {
    local missing=() venv_test
    command -v git >/dev/null 2>&1 || missing+=(git)
    command -v curl >/dev/null 2>&1 || missing+=(curl)
    command -v flock >/dev/null 2>&1 || missing+=(util-linux)
    command -v runuser >/dev/null 2>&1 || missing+=(util-linux)
    command -v ss >/dev/null 2>&1 || missing+=(iproute2)
    if command -v python3 >/dev/null 2>&1; then
        venv_test="$(mktemp -d)"
        if ! python3 -m venv "$venv_test/venv" >/dev/null 2>&1; then missing+=(python3-venv); fi
        rm -rf "$venv_test"
    else
        missing+=(python3 python3-venv)
    fi
    if [ "${#missing[@]}" -gt 0 ]; then
        command -v apt-get >/dev/null 2>&1 || fail "缺少 ${missing[*]}，且系统不支持 apt-get 自动安装"
        log "安装系统依赖：${missing[*]}"
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates "${missing[@]}"
    fi
}

install_packages
exec 9>"/run/lock/${SERVICE_NAME}-deploy.lock"
flock -n 9 || fail "已有另一个 $SERVICE_NAME 部署任务正在运行"

if [ -f "$UNIT_FILE" ]; then UNIT_EXISTED=1; fi
if systemctl is-enabled --quiet "$SERVICE_NAME.service" 2>/dev/null; then WAS_ENABLED=1; fi
if systemctl is-active --quiet "$SERVICE_NAME.service" 2>/dev/null; then WAS_ACTIVE=1; fi
if [ -d "$INSTALL_DIR" ]; then INSTALL_EXISTED=1; fi

rollback() {
    local exit_code=$?
    trap - ERR
    echo >&2
    printf '\033[1;31m[失败]\033[0m 部署未完成，正在恢复部署前状态...\n' >&2
    systemctl stop "$SERVICE_NAME.service" >/dev/null 2>&1 || true
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        rm -rf -- "$INSTALL_DIR"
        mv -- "$BACKUP_DIR" "$INSTALL_DIR"
    elif [ "$INSTALL_EXISTED" -eq 0 ]; then
        rm -rf -- "$INSTALL_DIR"
    fi
    if [ "$UNIT_EXISTED" -eq 1 ] && [ -f "$SERVICE_BACKUP" ]; then
        cp -- "$SERVICE_BACKUP" "$UNIT_FILE"
    else
        rm -f -- "$UNIT_FILE"
    fi
    systemctl daemon-reload || true
    if [ "$WAS_ENABLED" -eq 1 ]; then systemctl enable "$SERVICE_NAME.service" >/dev/null 2>&1 || true
    else systemctl disable "$SERVICE_NAME.service" >/dev/null 2>&1 || true; fi
    if [ "$WAS_ACTIVE" -eq 1 ]; then
        systemctl restart "$SERVICE_NAME.service" >/dev/null 2>&1 || true
        for _ in $(seq 1 10); do
            curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1 && break
            sleep 1
        done
    else
        systemctl stop "$SERVICE_NAME.service" >/dev/null 2>&1 || true
    fi
    exit "$exit_code"
}
trap rollback ERR

CURRENT_PID="$(systemctl show -p MainPID --value "$SERVICE_NAME.service" 2>/dev/null || true)"
LISTENER="$(ss -ltnp "sport = :$PORT" 2>/dev/null | sed -n '2p' || true)"
if [ -n "$LISTENER" ]; then
    if [ -z "$CURRENT_PID" ] || [ "$CURRENT_PID" = 0 ] || [[ "$LISTENER" != *"pid=$CURRENT_PID,"* ]]; then
        fail "端口 $PORT 已被其他进程占用：$LISTENER"
    fi
fi

PARENT_DIR="$(dirname "$INSTALL_DIR")"
mkdir -p -- "$PARENT_DIR"
WORK_DIR="$(mktemp -d "$PARENT_DIR/.${SERVICE_NAME}-deploy.XXXXXX")"
cleanup() { [ -n "$WORK_DIR" ] && rm -rf -- "$WORK_DIR"; }
trap cleanup EXIT
if [ "$UNIT_EXISTED" -eq 1 ]; then
    SERVICE_BACKUP="$WORK_DIR/service.backup"
    cp -- "$UNIT_FILE" "$SERVICE_BACKUP"
fi

log "下载 GitHub 最新代码（$BRANCH）"
git clone --depth 1 --branch "$BRANCH" -- "$REPO_URL" "$WORK_DIR/source"
rm -rf -- "$WORK_DIR/source/.git"
chown -R "$RUN_USER:$RUN_GROUP" "$WORK_DIR"

log "以 $RUN_USER 用户创建虚拟环境并安装依赖"
runuser -u "$RUN_USER" -- python3 -m venv "$WORK_DIR/source/venv"
runuser -u "$RUN_USER" -- "$WORK_DIR/source/venv/bin/pip" install --disable-pip-version-check --no-cache-dir -r "$WORK_DIR/source/requirements.txt"
runuser -u "$RUN_USER" -- "$WORK_DIR/source/venv/bin/python" -m py_compile "$WORK_DIR/source/app.py"

if [ "$INSTALL_EXISTED" -eq 1 ]; then
    BACKUP_DIR="$(mktemp -d "${INSTALL_DIR}.rollback.XXXXXX")"
    rmdir "$BACKUP_DIR"
    log "检测到旧版本，准备无数据覆盖更新"
    mv -- "$INSTALL_DIR" "$BACKUP_DIR"
else
    log "执行首次安装"
fi
mv -- "$WORK_DIR/source" "$INSTALL_DIR"
chown -R "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR"

cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Douyin Video and Gallery Parser
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
Environment=HOST=127.0.0.1
Environment=PORT=$PORT
ExecStart=$INSTALL_DIR/venv/bin/python -m gunicorn --workers 2 --bind 127.0.0.1:$PORT --access-logfile - app:app
Restart=always
RestartSec=3
TimeoutStopSec=20
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

systemd-analyze verify "$UNIT_FILE"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service" >/dev/null
systemctl restart "$SERVICE_NAME.service"

log "等待服务启动并执行健康检查"
HEALTH_OK=0
for _ in $(seq 1 30); do
    if systemctl is-active --quiet "$SERVICE_NAME.service" &&
       [ "$(curl -fsS --max-time 3 "$HEALTH_URL" 2>/dev/null)" = '{"service":"dyjx","status":"ok"}' ]; then
        HEALTH_OK=1
        break
    fi
    sleep 1
done
if [ "$HEALTH_OK" -ne 1 ]; then
    systemctl status "$SERVICE_NAME.service" --no-pager || true
    journalctl -u "$SERVICE_NAME.service" -n 30 --no-pager || true
    printf '\033[1;31m[错误]\033[0m 健康检查失败：%s\n' "$HEALTH_URL" >&2
    false
fi

trap - ERR
if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then rm -rf -- "$BACKUP_DIR"; fi
ok "安装/更新成功"
printf '\n服务名称：%s\n安装目录：%s\n监听地址：http://127.0.0.1:%s/\n健康检查：%s\n开机自启：已启用\n\n' \
    "$SERVICE_NAME.service" "$INSTALL_DIR" "$PORT" "$HEALTH_URL"
printf '常用命令：\n  systemctl status %s\n  journalctl -u %s -f\n  systemctl restart %s\n' \
    "$SERVICE_NAME" "$SERVICE_NAME" "$SERVICE_NAME"
