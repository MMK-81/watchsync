#!/usr/bin/env python3
"""WatchSync backend compatibility patch (idempotent).

YouTube links are normally played by the browser through YouTube's IFrame
API. That fails for viewers whose own network cannot reach youtube.com (even
though our server can). Force YouTube URLs through the same server-side
yt-dlp -> ffmpeg -> HLS proxy used for Aparat and other sites, so viewers only
need to reach watch.darkfamily.ir.
"""

import sys
from pathlib import Path

MARKER = "WATCHSYNC_YT_PROXY_PATCH"

OLD = '''    if YT_HOSTS.contains(&host.as_str()) {
        if let Some(id) = extract_youtube_id(&url) {
            let title = cache.get(&id).unwrap_or_else(|| raw_url.to_string());
            // A canonical `/live/<id>` URL is always a live stream; other YouTube
            // URL forms (`watch?v=`, `youtu.be/…`) can't be told apart here.
            let is_live = url
                .path_segments()
                .and_then(|mut s| s.next())
                .map(|first| first.eq_ignore_ascii_case("live"))
                .unwrap_or(false);
            return Some(Media {
                kind: "youtube".to_string(),
                id: Some(id),
                source: raw_url.to_string(),
                start: extract_start_seconds(&url),
                title,
                is_live,
            });
        }
    }
'''

NEW = '''    if YT_HOSTS.contains(&host.as_str()) {
        // WATCHSYNC_YT_PROXY_PATCH: do not use YouTube's IFrame API. Viewers on
        // restricted networks cannot reach youtube.com directly, but our server
        // can (via the resolver's android/MP4 client). Classify YouTube URLs as
        // ordinary media so ws.rs spawns the ffmpeg -> /api/streams HLS proxy.
        if let Some(youtube_id) = extract_youtube_id(&url) {
            let title = cache
                .get(&youtube_id)
                .unwrap_or_else(|| raw_url.to_string());
            let is_live = url
                .path_segments()
                .and_then(|mut s| s.next())
                .map(|first| first.eq_ignore_ascii_case("live"))
                .unwrap_or(false);
            return Some(Media {
                kind: "file".to_string(),
                id: None,
                source: raw_url.to_string(),
                start: extract_start_seconds(&url),
                title,
                is_live,
            });
        }
    }
'''


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: backend-patch.py <path/to/backend/src/media.rs>")
    path = Path(sys.argv[1])
    source = path.read_text(encoding="utf-8")

    if MARKER in source:
        print("   backend patch already applied")
        return
    if OLD not in source:
        raise SystemExit("could not find YouTube detection block")

    source = source.replace(OLD, NEW, 1)
    path.write_text(source, encoding="utf-8")
    print("   patched %s" % path)


if __name__ == "__main__":
    main()
