# ─────────────────────────────────────────────────────────────────────────────
# DANYSHPAN.XYZ — автоматическая настройка Ubuntu 24.04 VPS + деплой
# Запуск:  sudo bash deploy.sh   (или bash deploy.sh с правами root)
# Переменные: TELEGRAM_BOT_TOKEN="..." bash deploy.sh — задаёт токен бота
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

LOG_FILE="/var/log/danyshpan-deploy.log"
exec > >(tee -a "$LOG_FILE") 2>&1

DOMAIN="danyshpan.xyz"
APP_DIR="/opt/danyshpan"
REPO_URL="https://github.com/RKydyrali/nisprep.git"
ADMIN_EMAIL="admin@danyshpan.xyz"
NGINX_CONF_DIR="$APP_DIR/nginx/conf.d"

info()  { echo "[INFO]  $(date -u +%FT%TZ) $*"; }
warn()  { echo "[WARN]  $(date -u +%FT%TZ) $*"; }
fail()  { echo "[ERROR] $(date -u +%FT%TZ) $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Запустите от root: sudo bash deploy.sh"

# ── 1. Базовые пакеты ────────────────────────────────────────────────────────
info "Установка базовых пакетов..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git ufw apt-transport-https openssl

# ── 2. Docker (если ещё не установлен) ───────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
    info "Установка Docker..."
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true
if ! docker compose version >/dev/null 2>&1; then
    info "Установка docker compose plugin..."
    apt-get install -y docker-compose-plugin
fi
info "Docker: $(docker --version), Compose: $(docker compose version --short)"

# ── 3. UFW — только SSH/HTTP/HTTPS ───────────────────────────────────────────
info "Настройка UFW (22/80/443)..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
ufw --force enable
ufw status verbose

# ── 3.5. Swap (2GB) — защита сборки от OOM на малом VPS ──────────────────────
if [ ! -f /swapfile ]; then
    info "Создание swap-файла 2GB..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q "/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
else
    swapon /swapfile 2>/dev/null || true
fi

# ── 4. Клонирование/обновление репозитория ───────────────────────────────────
info "Репозиторий: $APP_DIR"
mkdir -p "$APP_DIR"
if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
    if [ ! -d "$APP_DIR/.git" ]; then
        git clone "$REPO_URL" "$APP_DIR"
    fi
else
    if [ -d "$APP_DIR/.git" ]; then
        git -C "$APP_DIR" pull --ff-only || warn "git pull не удался — продолжаем с текущим состоянием"
    fi
fi
cd "$APP_DIR"

# ── 5. Переменные окружения ──────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    info "Создание .env из .env.example..."
    cp .env.example .env
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" .env
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 16)|" .env
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(openssl rand -hex 12)|" .env
fi
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    sed -i "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}|" .env
    info "TELEGRAM_BOT_TOKEN установлен из окружения."
else
    warn "TELEGRAM_BOT_TOKEN не задан — бот запустится в режиме ожидания."
fi
grep -q "CHANGE_ME" .env && fail ".env содержит CHANGE_ME — проверьте и перезапустите"

# ── 6. Сборка и запуск контейнеров ───────────────────────────────────────────
info "Сборка образов (на 1 CPU это займёт несколько минут)..."
docker compose build
info "Запуск контейнеров..."
docker compose up -d

# ── 7. Ожидание health-check backend через nginx ─────────────────────────────
info "Ожидание health-check (до 5 минут)..."
HEALTHY=0
for i in $(seq 1 60); do
    if curl -fsS "http://localhost/api/v1/health" 2>/dev/null | grep -q '"status":"ok"'; then
        HEALTHY=1; break
    fi
    sleep 5
done
[ "$HEALTHY" -eq 1 ] || fail "Backend не прошёл health-check за 5 минут (см. docker compose logs backend)"
info "Backend health-check пройден."

# ── 8. SSL — Let's Encrypt ────────────────────────────────────────────────────
CERT_DIR="$APP_DIR/certbot/conf/live/$DOMAIN"

activate_nginx_http() {
    cp "$APP_DIR/nginx/templates/danyshpan.http.conf" "$NGINX_CONF_DIR/danyshpan.conf"
}
activate_nginx_ssl() {
    cp "$APP_DIR/nginx/templates/danyshpan.ssl.conf" "$NGINX_CONF_DIR/danyshpan.conf"
}

mkdir -p "$APP_DIR/certbot/www" "$APP_DIR/certbot/conf"

if [ -d "$CERT_DIR" ]; then
    info "Сертификат уже существует — включаю HTTPS-конфигурацию."
    activate_nginx_ssl
    docker compose up -d nginx
else
    info "Сертификата нет — включаю HTTP-конфигурацию и выпускаю Let's Encrypt..."
    activate_nginx_http
    docker compose up -d nginx
    sleep 5
    if docker run --rm \
        -v "$APP_DIR/certbot/www:/var/www/certbot" \
        -v "$APP_DIR/certbot/conf:/etc/letsencrypt" \
        certbot/certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --email "$ADMIN_EMAIL" --agree-tos --no-eff-email --non-interactive; then
        info "Сертификат получен. Включаю HTTPS..."
        activate_nginx_ssl
        docker compose restart nginx
    else
        warn "Выпуск сертификата не удался — проверьте DNS-запись $DOMAIN → IP сервера."
        warn "Сайт останется на HTTP. Перезапустите deploy.sh после исправления DNS."
    fi
fi

# ── 9. Cron автообновления сертификата (раз в 12 дней) ───────────────────────
if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    (crontab -l 2>/dev/null; \
     echo "0 3 */12 * * cd $APP_DIR && docker run --rm -v $APP_DIR/certbot/conf:/etc/letsencrypt -v $APP_DIR/certbot/www:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot --quiet && docker compose restart nginx") \
    | crontab -
    info "Cron обновления сертификата установлен."
fi

# ── 10. Итоговый статус ──────────────────────────────────────────────────────
info "Статус контейнеров:"
docker compose ps
echo
info "Проверка:"
curl -fsS "http://localhost/api/v1/health" || warn "health недоступен"
curl -I "https://$DOMAIN" 2>/dev/null | head -3 || warn "https пока недоступен (проверьте DNS)"
info "Деплой завершён. Сайт: https://$DOMAIN"
