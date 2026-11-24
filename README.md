# WatchSync Deployment Kit

Server-side deployment files for **WatchSync** at `watch.darkfamily.ir` — a synchronized group video-watching service. Users create rooms (`/r/xxxx`), build a shared queue, chat and react, while the host controls play/pause/seek/speed and moderation. Sources are supported via yt-dlp (YouTube, direct `.mp4/.webm/.m3u8`, Aparat and ~1,800 other sites).

This is **not** the upstream application source. It adapts `Houdini99/WatchSync` (v3, Rust backend + React frontend) to one server: an existing Caddy container from the sibling **filemanager** project is the public proxy, Docker Hub is unreliable so images use AWS ECR public mirrors, and resource limits are tuned for a 4 GB host.

[راهنمای فارسی / Persian README](README.fa.md)

## Services

| Service | Image | Role | Limits |
|---|---|---|---|
| `watchsync-server` | `watchsync-server:latest` (from `src/backend`) | Rust API/WebSocket, SQLite, ffmpeg → HLS proxy | 1536 MB / 2 CPU |
| `watchsync-resolver` | `watchsync-resolver:latest` (from `src/resolver`) | yt-dlp URL → direct stream resolver | 768 MB / 1.5 CPU |
| `watchsync-bgutil` | `watchsync-bgutil:1.2.2` (from `bgutil/server`) | YouTube PO-token provider on 4416 | 512 MB / 0.5 CPU |
| `watchsync-client` | `watchsync-client:latest` (from `src/frontend`) | React frontend served by nginx on 80 | 256 MB / 0.5 CPU |

Startup order: **bgutil → resolver → server → client** (healthcheck-gated `depends_on`). All services use `restart: unless-stopped`, `no-new-privileges: true`, `cap_drop: ALL` and rotating json-file logs. The client re-adds only `CHOWN`, `SETUID`, `SETGID` and `NET_BIND_SERVICE`.

No service publishes a host port. Caddy proxies externally to `watchsync-client:80`.

## Requirements

- Linux server with Docker Engine and Compose v2, ~4 GB RAM
- Existing `filemanager_default` network and Caddy container from the filemanager project
- DNS A record for the domain pointing to the server; ports 80/443 reachable for Let's Encrypt
- `git` and `python3` on the server (used by `setup.sh` and the patch scripts)

## Install

```bash
cd /opt/watchsync
chmod +x *.sh
./setup.sh
```

`setup.sh` will:

1. source `.env` (`set -a`),
2. shallow-clone `Houdini99/WatchSync` into `src/` and `bgutil-ytdlp-pot-provider` (tag `1.2.2`) into `bgutil/` if missing,
3. apply `resolver-patch.py` and `backend-patch.py`,
4. rewrite base images in the cloned Dockerfiles to `public.ecr.aws/docker/library/...` mirrors,
5. build all four images and run `docker compose up -d`,
6. append `Caddyfile.snippet` to `/opt/filemanager/Caddyfile` (once, guarded by a `WATCHSYNC BEGIN` marker),
7. validate and reload Caddy, then print `docker compose ps` and an HTTP status check.

The final `curl ... || true` is informational — always check `docker compose ps` and the logs yourself.

## What the patches do

`resolver-patch.py` (idempotent, marker `WATCHSYNC_APARAT_PATCH`):

- forces yt-dlp to use the `android` player client so YouTube resolves to a direct progressive MP4 instead of blocked/HLS formats,
- adds an Aparat resolver using its public JSON API (HLS link → `multiSRC` → `file_link`), bypassing the broken yt-dlp extractor,
- migrates older `web_safari` patches to `android`.

`backend-patch.py` (idempotent, marker `WATCHSYNC_YT_PROXY_PATCH`):

- classifies YouTube URLs as ordinary `file` media instead of the browser IFrame API, so viewers only need access to this domain; the server proxies through yt-dlp → ffmpeg → `/api/streams`.

`setup.sh` also replaces the controller name/email in the privacy page and updates `LAST_UPDATED`.

## Configuration

Copy `.env.example` to `.env` and edit. **Never commit `.env`.**

| Variable | Purpose |
|---|---|
| `PUBLIC_ORIGIN` | Must exactly match the browser-origin URL |
| `LOG_LEVEL` | Backend log level |
| `RESOLVER_URL` | Internal resolver base URL |
| `POT_PROVIDER_URL` | Internal PO-token provider URL |
| `STREAMS_TMPFS_SIZE` | RAM allocated to the HLS stream tmpfs (default 512m) |
| `REGISTRATION_ENABLED` | Allow open registration |
| `MAX_ROOMS_PER_USER` | Room limit |
| `COOKIE_SECURE` | HTTPS-only cookies (true behind Caddy) |
| `ALLOW_PRIVATE_URLS` | SSRF guard — keep `false` unless you need LAN/NAS sources |
| `CONTROLLER_NAME`, `CONTROLLER_EMAIL` | Shown on `/privacy` |

Additional tuning variables (`TRUSTED_PROXIES`, `MAX_USERS_PER_ROOM`, `MAX_ROOMS`, `SESSION_TTL_DAYS`, resolver timeouts, etc.) are passed through from the environment; when unset, upstream defaults apply. Check `docker-compose.yml` for the full list.

`CORS_ORIGIN` must match `PUBLIC_ORIGIN` or chat/WebSocket will break.

## Volumes and networks

- `watchsync-data` → `/data` in the server (SQLite + persistent rooms); this is what backups archive.
- `watchsync-streams` → tmpfs at `/dev/shm/streams` in server and client; RAM-backed and **not** persisted.
- `watchsync-internal`: private bridge for all four services (server alias `watchsync-server-int`).
- `filemanager_default`: external network, joined by the client only, for Caddy DNS discovery.

The Caddy site block sets compression, HSTS, `nosniff`, `Referrer-Policy`, tuned proxy buffers/timeouts, and JSON access logs at `/data/watchsync-access.log` (20 MB, keep 5).

## Operations

```bash
cd /opt/watchsync
docker compose ps
docker compose logs -f watchsync-server
docker compose logs -f watchsync-client
docker compose restart watchsync-client
docker compose down
docker compose up -d
```

Change the stream tmpfs size:

```bash
nano .env                               # STREAMS_TMPFS_SIZE=1g
docker compose down
docker volume rm watchsync_watchsync-streams
docker compose up -d
```

Manual Caddy reload:

```bash
cd /opt/filemanager
docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
```

## Backup, restore, update

```bash
./backup.sh
# backups/watchsync-data-YYYYmmdd-HHMMSS.tar.gz
# Stops the server briefly for a consistent volume copy, then restarts it.
```

Nightly backup:

```bash
(crontab -l 2>/dev/null; echo "0 4 * * * cd /opt/watchsync && ./backup.sh >> /var/log/watchsync-backup.log 2>&1") | crontab -
```

Restore (verify the archive's top-level directory first — the extracted contents must end up in `_data`):

```bash
docker compose down
rm -rf /var/lib/docker/volumes/watchsync_watchsync-data/_data/*
tar -xzf backups/watchsync-data-....tar.gz -C /var/lib/docker/volumes/watchsync_watchsync-data/
docker compose up -d
```

Update:

```bash
./update.sh        # git pull --autostash, backup.sh, setup.sh
```

`setup.sh` re-applies patches idempotently, but review the result after an upstream update: conflicts on patched lines can cause stash problems.

## Security notes

- `.env` is exported into the build/run environment via `set -a`; restrict permissions and keep it out of version control.
- Keep `ALLOW_PRIVATE_URLS=false`; `true` enables LAN/Jellyfin/NAS URLs and opens internal-network SSRF.
- `REGISTRATION_ENABLED=true` means open sign-ups; set it to `false` to close registration.
- `COOKIE_SECURE=true` assumes Caddy terminates HTTPS correctly.
- Confirm `TRUSTED_PROXIES` so rate limiting uses the real client IP rather than Caddy's.
- Backups are **unencrypted** and do not include `.env`, scripts or the Caddyfile.
- The restore command above uses `rm -rf` on a Docker volume path — double-check it before running.
- Resolver logs full video URLs; `RESOLVER_LOG=0` disables that.
- Streams live in RAM: many or long videos can exhaust memory. Tune `STREAMS_TMPFS_SIZE` and stream limits.
- Patches depend on yt-dlp behavior, Aparat's undocumented API and a third-party PO-token provider; they can break when those services change. Only legally fetchable URLs are proxied (subscription/DRM sites are out of scope).

## License

Private project. Based on upstream open-source components; see their respective licenses.
