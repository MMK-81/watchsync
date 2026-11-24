#!/usr/bin/env bash
# بکاپ دیتابیس حسابها و نام اتاقهای دائمی WatchSync
set -euo pipefail
cd "$(dirname "$0")"

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="./backups"
mkdir -p "$DEST"

echo "==> توقف موقت سرور برای بکاپ سازگار"
docker stop watchsync-server >/dev/null

MP="$(docker volume inspect -f '{{.Mountpoint}}' watchsync_watchsync-data)"
tar -czf "$DEST/watchsync-data-$STAMP.tar.gz" -C "$(dirname "$MP")" "$(basename "$MP")"

docker start watchsync-server >/dev/null

echo "بکاپ ساخته شد: $DEST/watchsync-data-$STAMP.tar.gz"
