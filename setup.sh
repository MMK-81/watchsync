#!/usr/bin/env bash
# WatchSync نصب خودکار on /opt/watchsync
set -euo pipefail

cd "$(dirname "$0")"
set -a
. ./.env
set +a

SRC_DIR="$PWD/src"
BG_DIR="$PWD/bgutil"
CADDY_FILE="/opt/filemanager/Caddyfile"

echo "==> بررسی پیشنیازها"
command -v docker >/dev/null || { echo "Docker پیدا نشد"; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose v2 پیدا نشد"; exit 1; }
docker network inspect filemanager_default >/dev/null 2>&1 || {
  echo "شبکه filemanager_default پیدا نشد؛ ابتدا استک filemanager را بالا بیاورید"; exit 1;
}

patch_line() {
  local file="$1" from="$2" to="$3"
  if [ -f "$file" ] && grep -Fq "$from" "$file"; then
    sed -i "s|^${from}|${to}|" "$file"
    echo "   patch: $(basename "$file") -> ${to}"
  fi
}

echo "==> دانلود سورس WatchSync"
if [ ! -d "$SRC_DIR/.git" ]; then
  git clone --depth 1 https://github.com/Houdini99/WatchSync.git "$SRC_DIR"
else
  echo "   سورس از قبل موجود است"
fi

echo "==> جایگزینی مشخصات مسئول حریم خصوصی در صفحه /privacy"
PRIVACY="$SRC_DIR/frontend/src/components/Privacy.tsx"
[ -f "$PRIVACY" ] || { echo "Privacy.tsx پیدا نشد"; exit 1; }
TODAY="$(date +'%-d %B %Y')"
sed -i "s|name: '\[Your full name\]'|name: '${CONTROLLER_NAME}'|" "$PRIVACY"
sed -i "s|email: 'privacy@example.com'|email: '${CONTROLLER_EMAIL}'|" "$PRIVACY"
sed -i "s|const LAST_UPDATED = .*|const LAST_UPDATED = { de: '${TODAY}', en: '${TODAY}' };|" "$PRIVACY"

echo "==> تغییر ایمیجهایbase به آینه ECR (Docker Hub روی سرور قابلاعتماد نیست)"
patch_line "$SRC_DIR/backend/Dockerfile"  'FROM rust:1.90-bookworm'  'FROM public.ecr.aws/docker/library/rust:1.90-bookworm'
patch_line "$SRC_DIR/backend/Dockerfile"  'FROM debian:bookworm-slim' 'FROM public.ecr.aws/docker/library/debian:bookworm-slim'
patch_line "$SRC_DIR/frontend/Dockerfile" 'FROM node:20-alpine'       'FROM public.ecr.aws/docker/library/node:20-alpine'
patch_line "$SRC_DIR/frontend/Dockerfile" 'FROM nginx:1.27-alpine'    'FROM public.ecr.aws/docker/library/nginx:1.27-alpine'
patch_line "$SRC_DIR/resolver/Dockerfile" 'FROM python:3.12-slim'     'FROM public.ecr.aws/docker/library/python:3.12-slim'

echo "==> اعمال پچهای سازگاری resolver (YouTube + Aparat)"
python3 resolver-patch.py "$SRC_DIR/resolver/app.py"

echo "==> اعمال پچ backend (پخش YouTube از طریقproxy سرور)"
python3 backend-patch.py "$SRC_DIR/backend/src/media.rs"

echo "==> دانلود سورس bgutil نسخه 1.2.2"
if [ ! -d "$BG_DIR/.git" ]; then
  git clone --depth 1 --branch 1.2.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$BG_DIR"
else
  echo "   سورس bgutil از قبل موجود است"
fi
patch_line "$BG_DIR/server/Dockerfile" 'FROM node:20-slim AS build' 'FROM public.ecr.aws/docker/library/node:20-slim AS build'
patch_line "$BG_DIR/server/Dockerfile" 'FROM node:20-slim'          'FROM public.ecr.aws/docker/library/node:20-slim'

echo "==> ساخت ایمیجها (اولین بار چند دقیقه طول میکشد)"
docker build -t watchsync-server:latest   "$SRC_DIR/backend"
docker build -t watchsync-resolver:latest "$SRC_DIR/resolver"
docker build -t watchsync-client:latest   "$SRC_DIR/frontend"
docker build -t watchsync-bgutil:1.2.2    "$BG_DIR/server"

echo "==> بالا آوردن استک"
docker compose up -d

echo "==> اضافه کردن سایت watch.darkfamily.ir به Caddy"
if grep -q 'WATCHSYNC BEGIN' "$CADDY_FILE"; then
  echo "   سایت از قبل در Caddyfile وجود دارد"
else
  cat Caddyfile.snippet >> "$CADDY_FILE"
  echo "   سایت اضافه شد"
fi
docker compose -f /opt/filemanager/docker-compose.yml --project-directory /opt/filemanager \
  exec -T caddy caddy validate --config /etc/caddy/Caddyfile
docker compose -f /opt/filemanager/docker-compose.yml --project-directory /opt/filemanager \
  exec -T caddy caddy reload --config /etc/caddy/Caddyfile

echo "==> وضعیت نهایی"
docker compose ps
sleep 5
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' https://watch.darkfamily.ir/ || true
echo "تمام. آدرس: https://watch.darkfamily.ir"
