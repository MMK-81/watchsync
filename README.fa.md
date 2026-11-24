# WatchSync روی سرور — watch.darkfamily.ir

تماشای هماهنگ ویدیو با دوستان: ساخت اتاق، لینک اشتراک، صف ویدیو، چت، واکنشها،
 هماهنگی پخش (play/pause/seek/سرعت)، پشتیبانی از YouTube، MP4/WebM/M3U8
 و تقریباً ۱۸۰۰ سایت دیگر از طریق yt-dlp.

| مورد | مقدار |
|---|---|
| دامنه | `watch.darkfamily.ir` (رکورد A از قبل به `5.57.37.113` اشاره میکند) |
| مسیر روی سرور | `/opt/watchsync` |
| پروکسی | همان Caddy کانتینر `filemanager-caddy-1` (شبکه `filemanager_default`) |
| منبع | `github.com/Houdini99/WatchSync` (نسخه v3، Rust + React) |

## ساختار

```
/opt/watchsync
├── docker-compose.yml      # ۴ کانتینر: server, resolver, bgutil, client
├── .env                    # دامنه، تنظیمات و مشخصات حریم خصوصی
├── Caddyfile.snippet       # بلاکی که به Caddyfile فایلمنیجر اضافه میشود
├── setup.sh                # نصب/ساخت ایمیجها/بالا آوردن/پروکسی
├── resolver-patch.py       # پچ YouTube (android/MP4) + پشتیبانی Aparat از API
├── backend-patch.py        # پچ پخش YouTube از طریق HLSproxy سرور
├── backup.sh               # بکاپ دیتابیس SQLite
├── update.sh               # بروزرسانی
├── src/                    # سورس WatchSync (clone)
└── bgutil/                 # سورس PO-token provider نسخه 1.2.2 (clone)
```

فقط کانتینر `watchsync-client` به شبکه `filemanager_default` متصل است؛
server/resolver/bgutil روی شبکه خصوصی `watchsync-internal`اند و هیچ پورتی روی هاست باز نمیکنند.

## نصب (یکبار)

پوشه `watchsync` را به `/opt/watchsync` کپی کنید، سپس:

```bash
cd /opt/watchsync
chmod +x *.sh
./setup.sh
```

اسکریپت این کارها را میکند:

1. سورس WatchSync و bgutil را clone میکند.
2. مشخصات `CONTROLLER_NAME` / `CONTROLLER_EMAIL` را در صفحه `/privacy` میگذارد.
3. ایمیجهای base را به آینه `public.ecr.aws/docker/library/...` تغییر میدهد
   (چون Docker Hub روی سرور گاهی با خطای unauthorized روبهرو میشود).
4. سه ایمیج WatchSync + ایمیج bgutil را میسازد (اولین بار چند دقیقه).
5. استک را بالا میآورد.
6. بلاک `watch.darkfamily.ir` را به `/opt/filemanager/Caddyfile` اضافه، validate و reload میکند.

بعد از اتمام: `https://watch.darkfamily.ir` — گواهی SSL را Caddy بهصورت خودکار میگیرد.

> ظرف RAM اختصاصی استریمها بهطور پیشفرض ۵۱۲ مگ است (`STREAMS_TMPFS_SIZE` در `.env`).
> برای فیلمهای طولانیتر آن را به `1g` تغییر دهید، سپس:
> `docker compose down && docker volume rm watchsync_watchsync-streams && docker compose up -d`

## دستورهای روزمره

```bash
cd /opt/watchsync
docker compose ps
docker compose logs -f watchsync-server
docker compose logs -f watchsync-client
docker compose restart watchsync-client
docker compose down
docker compose up -d
./backup.sh
./update.sh
```

اگر Caddyfile تغییر کرد و reload نشد:

```bash
cd /opt/filemanager
docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
```

## نحوه استفاده

- در صفحه اصلی **Create a Room** بزنید؛ لینک `/r/xxxx` را با دوستانتان بهاشتراک بگذارید.
- اولین نفر میزبان (host) است: میتواند کنترلها را قفل کند، کاربری را اخراج/بن کند یا میزبانی را واگذار کند.
- برای اتاق دائمی مثل `/r/movie-night` ثبتنام کنید (فقط نام کاربری + رمز، بدون ایمیل).
- ویدیو YouTube بچسبانید یا فایل مستقیم `.mp4/.webm/.m3u8` — بقیه کارها روی سرور انجام میشود.
- لینکهای Vimeo/Twitch/Reddit و… توسط resolver پشتیبانی میشوند (best-effort).

## نتایج تست پخش (۲۲ نوامبر ۲۰۲۶)

| منبع | نتیجه |
|---|---|
| YouTube (`watch?v=…`) | ✅ پخش شد؛ resolver از client اندروید و فرمت MP4 مستقیم را استفاده میکند و ffmpeg از طریق `/api/streams` پروکسی میکند. بازدیدکننده نیازی به دسترس مستقیم به YouTube ندارد. |
| Aparat (`aparat.com/v/…`) | ✅ پخش شد (جلوگیری از extractor خراب yt-dlp با API عمومی آپارات). |
| Aparat Sport | ✅ پخش شد؛ یک کلیپ کوتاه و یک خلاصه بازی ۷ دقیقهای هر دو تست شدند. |
| MP4 / HLS مستقیم | ✅ پخش شد (پروکسی سرور؛ resilience در برابر قطعی موقتی network). |
| Filimo / Namava | ⚠️ لینکهای عمومی نمونه (`/m/ymhPo`, `/movie/269010-…`) فقط پیشنمایش/تبلیغ میدهند و API آنها `loginRequired=true` / `type=login` برمیگرداند. بدون حساب و اشتراک، استریمی برای پروکسی وجود ندارد. لینک مستقیم `.m3u8/.mp4`ای که از حساب معتبر خودتان بگیرید قابل پخش است. |

> نکته: سایتهای اشتراکی (Filimo، Namava و…) محتوای DRM/لاگینمحور دارند. WatchSync قصد دور زدن حفاظت آنها را ندارد؛ فقط URLهایی را پخش میکند که سرور بتواند بهصورت قانونی و بدون احراز هویت اضافه دریافت کند.

## بکاپ و ریاستور

```bash
./backup.sh
# backups/watchsync-data-YYYYmmdd-HHMMSS.tar.gz

# ریاستور
cd /opt/watchsync
docker compose down
rm -rf /var/lib/docker/volumes/watchsync_watchsync-data/_data/*
tar -xzf backups/watchsync-data-....tar.gz -C /var/lib/docker/volumes/watchsync_watchsync-data/
# پوشه استخراجشده data است؛ محتویاتش را به _data منتقل کنید
docker compose up -d
```

برای بکاپ خودکار شبانه:

```bash
(crontab -l 2>/dev/null; echo "0 4 * * * cd /opt/watchsync && ./backup.sh >> /var/log/watchsync-backup.log 2>&1") | crontab -
```

## عیبیدایی

| نشانه | علت / راهحل |
|---|---|
| 502 از Caddy | `docker network inspect filemanager_default` را چک کنید؛ `watchsync-client` باید در آن شبکه باشد |
| چت / WebSocket کار نمیکند | `PUBLIC_ORIGIN` دقیقاً برابر `https://watch.darkfamily.ir` باشد؛ Caddy upgrade را خودکار پشتیبانی میکند |
| ویدیوهای غیر YouTube روی Preparing stream میماند | لاگ `watchsync-server`؛ حجم `watchsync-streams` را بالا ببرید |
| کانتینرها بالا نمیآیند | ترتیب سلامت: bgutil → resolver → server → client؛ لاگ اولی که unhealthy است را ببینید |
| گواهی SSL گرفته نشد | DNS و پورت 80/443؛ لاگ `docker compose -f /opt/filemanager/docker-compose.yml logs caddy` |
| `/privacy`placeholderهای انگلیسی نشان میدهد | `.env` را چک کنید و `./setup.sh` را دوباره بزنید (client image rebuild میشود) |
| bgutil image pull خطای unauthorized داد | `./setup.sh` آنرا از سورس محلی میسازد؛ نیازی به Docker Hub نیست |

## امنیت

- `ALLOW_PRIVATE_URLS=false` پیشفرض است (جلوگیری از SSRF به شبکه داخلی سرور).
- `COOKIE_SECURE=true` و `REGISTRATION_ENABLED=true` است؛ برای بستن ثبتنام، مقدار را `false` کنید.
- مشخصات صفحه `/privacy` را حتماً با نام و ایمیل واقعی خودتان جایگزین کنید.
- لاگ resolver آدرس کامل ویدیوها را ثبت میکند؛ در صورت نگرانی `RESOLVER_LOG=0` بگذارید.
