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
    sed -i 's/\r$//' .env
    PG_PASS=$(openssl rand -hex 16)
    JWT_SEC=$(openssl rand -hex 32)
    ADMIN_PW=$(openssl rand -hex 12)
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" .env
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SEC}|" .env
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PW}|" .env
    sed -i "s|CHANGE_ME|${PG_PASS}|g" .env
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

# Активируем nginx-конфиг ДО старта (http, если сертификата ещё нет)
CERT_DIR="$APP_DIR/certbot/conf/live/$DOMAIN"
mkdir -p "$APP_DIR/certbot/www" "$APP_DIR/certbot/conf"
if [ -d "$CERT_DIR" ]; then
    cp "$APP_DIR/nginx/templates/danyshpan.ssl.conf" "$NGINX_CONF_DIR/danyshpan.conf"
    info "nginx: HTTPS-конфигурация активна."
else
    cp "$APP_DIR/nginx/templates/danyshpan.http.conf" "$NGINX_CONF_DIR/danyshpan.conf"
    info "nginx: HTTP-конфигурация активна (сертификата ещё нет)."
fi

info "Запуск контейнеров..."
docker compose up -d

# ── 7. Ожидание health-check backend через nginx ─────────────────────────────
info "Ожидание health-check (до 5 минут)..."
HEALTHY=0
for i in $(seq 1 60); do
    if curl -kfsSL "https://localhost/api/v1/health" 2>/dev/null | grep -q '"status":"ok"' \
       || curl -fsSL "http://localhost/api/v1/health" 2>/dev/null | grep -q '"status":"ok"'; then
        HEALTHY=1; break
    fi
    sleep 5
done
[ "$HEALTHY" -eq 1 ] || fail "Backend не прошёл health-check за 5 минут (см. docker compose logs backend)"
info "Backend health-check пройден."

# ── 8. SSL — Let's Encrypt ────────────────────────────────────────────────────
CERT_DIR="$APP_DIR/certbot/conf/live/$DOMAIN"

if [ -d "$CERT_DIR" ]; then
    info "Сертификат уже существует — HTTPS-конфигурация уже активна."
else
    info "Выпуск Let's Encrypt сертификата для $DOMAIN..."
    sleep 5
    if docker run --rm \
        -v "$APP_DIR/certbot/www:/var/www/certbot" \
        -v "$APP_DIR/certbot/conf:/etc/letsencrypt" \
        certbot/certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --email "$ADMIN_EMAIL" --agree-tos --no-eff-email --non-interactive; then
        info "Сертификат получен. Включаю HTTPS..."
        cp "$APP_DIR/nginx/templates/danyshpan.ssl.conf" "$NGINX_CONF_DIR/danyshpan.conf"
        docker compose restart nginx
    else
        warn "Выпуск сертификата не удался — проверьте DNS-запись $DOMAIN → IP сервера."
        warn "Сайт останется на HTTP. Перезапустите deploy.sh после исправления DNS."
    fi
fi

# ── 9. Cron: обновление SSL + ежедневные бэкапы БД ───────────────────────────
install_cron_line() {
    local marker="$1" line="$2"
    local tmp
    tmp=$(mktemp)
    crontab -l 2>/dev/null | grep -vF "$marker" > "$tmp" || true
    printf '%s\n' "$line" >> "$tmp"
    crontab "$tmp"
    rm -f "$tmp"
}

# Обновление сертификата каждые 12 дней
install_cron_line "certbot renew" \
    "0 3 */12 * * cd $APP_DIR && docker run --rm -v $APP_DIR/certbot/conf:/etc/letsencrypt -v $APP_DIR/certbot/www:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot --quiet && docker compose restart nginx"
info "Cron обновления сертификата установлен."

# Ежедневный бэкап Postgres в 04:30 (retention 7 дней)
mkdir -p "$APP_DIR/backups"
install_cron_line "pg_dump" \
    "30 4 * * * docker exec danyshpan-postgres-1 pg_dump -U danyshpan -d danyshpan | gzip > $APP_DIR/backups/db-\$(date +\\%F).sql.gz && find $APP_DIR/backups -name '*.sql.gz' -mtime +7 -delete"
info "Cron бэкапа БД установлен (ежедневно 04:30, хранение 7 дней)."

# ── 10. Итоговый статус ──────────────────────────────────────────────────────
info "Статус контейнеров:"
docker compose ps
echo
info "Проверка:"
curl -fsS "http://localhost/api/v1/health" || warn "health недоступен"
curl -I "https://$DOMAIN" 2>/dev/null | head -3 || warn "https пока недоступен (проверьте DNS)"
info "Деплой завершён. Сайт: https://$DOMAIN"
