#!/usr/bin/env python3
"""WatchSync resolver compatibility patches (idempotent).

Applied by setup.sh after cloning the upstream source:

1. YouTube /resolve: force yt-dlp's ``android`` player client. The default
   ``web`` client is rejected from datacenter IPs with
   ``The page needs to be reloaded``; ``web_safari`` extracts HLS URLs whose
   signed segments come back 403 from googlevideo. ``android`` yields a direct
   progressive MP4 (format 18) that ffmpeg can proxy reliably. Subtitle
   extraction keeps its own web + PO-token options and is untouched.

2. Aparat: the bundled yt-dlp extractor is broken against Aparat's new
   Next.js pages (they no longer contain ``og:title`` or ``options = {...}``).
   We use Aparat's own public JSON API directly for ``aparat.com/v/<id>``.
"""

import sys
from pathlib import Path

MARKER = "WATCHSYNC_APARAT_PATCH"

APARAT_HELPER = '''\
# WATCHSYNC_APARAT_PATCH ---------------------------------------------------
# Aparat migrated to a Next.js SPA: /v/<id> no longer exposes og:title or
# `options = {...}`, so yt-dlp's built-in Aparat extractor fails with
# "Unable to extract og:title". The public API still returns everything we
# need, so handle those URLs here instead.
def resolve_aparat(url):
    import re

    match = re.search(r"aparat\\.com/v/([A-Za-z0-9]+)", url)
    if not match:
        return None
    uid = match.group(1)
    api = "https://www.aparat.com/api/v0/videos/%s" % uid
    request = urllib.request.Request(api, headers={
        "User-Agent": "Mozilla/5.0",
        "Jsontype": "simple",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = json.load(response)["data"]

    sources = []
    for group in (data.get("playerOption") or {}).get("multiSRC") or []:
        for item in group or []:
            if isinstance(item, dict) and item.get("src"):
                sources.append(item)

    hls_link = (data.get("hls") or {}).get("link") or data.get("hls_link")
    if hls_link:
        direct, kind = hls_link, "hls"
    elif sources:
        direct, kind = sources[0]["src"], "muxed"
    elif data.get("file_link"):
        direct, kind = data["file_link"], "muxed"
    else:
        raise ValueError("Aparat API returned no playable stream")

    return {
        "video_url": direct,
        "audio_url": None,
        "video_headers": {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.aparat.com/",
            "Jsontype": "simple",
        },
        "audio_headers": {},
        "title": (data.get("title") or uid).strip()[:200],
        "is_live": str(data.get("process") or "").lower() in ("live", "processing"),
        "kind": kind,
    }


'''


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: resolver-patch.py <path/to/resolver/app.py>")
    path = Path(sys.argv[1])
    source = path.read_text(encoding="utf-8")

    if MARKER in source:
        # Migration from the earlier web_safari variant: its HLS segments get
        # 403 from googlevideo, so switch the already-patched file to android.
        if '["web_safari"]' in source:
            source = source.replace('["web_safari"]', '["android"]')
            source = source.replace(
                "# datacenter IPs (\"The page needs to be reloaded\"). web_safari works.",
                "# datacenter IPs. android gives a direct MP4 that ffmpeg can proxy.",
            )
            path.write_text(source, encoding="utf-8")
            print("   migrated resolver patch: web_safari -> android")
        else:
            print("   resolver patch already applied")
        return

    # --- 1. YouTube client fix for /resolve -------------------------------
    ydl_start = source.index("YDL_OPTS = {")
    ydl_end = source.index("\n}\n", ydl_start)
    ydl_block = source[ydl_start:ydl_end]
    if "extractor_args" not in ydl_block:
        insertion = (
            'YDL_OPTS = {\n'
            '    # WATCHSYNC_PATCH: YouTube rejects the default "web" client from\n'
            '    # datacenter IPs. android gives a direct MP4 that ffmpeg can proxy.\n'
            '    "extractor_args": {"youtube": {"player_client": ["android"]}},\n'
        )
        source = source.replace("YDL_OPTS = {\n", insertion, 1)

    # --- 2. Aparat API helper -------------------------------------------
    if "def resolve_aparat(url):" not in source:
        anchor = "def resolve(url):\n"
        if anchor not in source:
            raise SystemExit("could not find resolve() anchor")
        source = source.replace(anchor, APARAT_HELPER + anchor, 1)

    old_call = "def resolve(url):\n    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:\n"
    new_call = (
        "def resolve(url):\n"
        "    # WATCHSYNC_APARAT_PATCH: bypass yt-dlp's stale Aparat extractor.\n"
        "    if 'aparat.com/v/' in url:\n"
        "        aparat = resolve_aparat(url)\n"
        "        if aparat:\n"
        "            return aparat\n"
        "    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:\n"
    )
    if old_call not in source:
        raise SystemExit("could not find resolve() body")
    source = source.replace(old_call, new_call, 1)

    path.write_text(source, encoding="utf-8")
    print("   patched %s" % path)


if __name__ == "__main__":
    main()
