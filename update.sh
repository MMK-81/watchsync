#!/usr/bin/env bash
# بروزرسانی WatchSync: git pull + بکاپ + rebuild (از طریق setup.sh)
set -euo pipefail
cd "$(dirname "$0")"

git -C src pull --autostash
git -C bgutil pull --autostash

./backup.sh
# setup.sh بهصورت idempotent پچها را دوباره اعمال میکند، ایمیجها را میسازد،
# استک را بالا میآورد و Caddyfile را هم چک میکند.
./setup.sh
