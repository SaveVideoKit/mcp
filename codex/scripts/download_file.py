#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SaveVideoKit local download helper (zero dependencies, Python standard library only).

Accepts two kinds of URLs:

1. Direct option URL - inspect_video -> structuredContent.direct_options[].download_url.
   The service answers with a 302 redirect straight to the original media file on the
   source CDN, so the bytes never pass through the service: no download job, no merge,
   no server-side storage. This is the preferred path when it is offered.
2. Job URL - get_download_status -> download_url, produced by create_download when no
   direct option exists. The generated file is retained for about 30 minutes.

Direct URLs are opaque signed tokens without a file extension, so pass --ext (taken from
direct_options[].ext) or let the script infer it from the response Content-Type. Some
origins only serve media when a Referer is present, hence --referer.

Usage:
    python3 download_file.py "<url>" "<output_dir>" \
        [--name "title"] [--ext mp4] [--referer "page url"] [--timeout 180]
"""
import argparse
import os
import re
import sys
import urllib.error
import urllib.request

UA = "savevideokit-cli/1.2 (+https://www.savevideokit.com)"

# Media extensions we are willing to trust from a URL path or a Content-Type header.
MEDIA_EXTS = {
    "mp4", "m4a", "m4v", "webm", "mkv", "mov", "flv", "ts", "mp3",
    "wav", "opus", "aac", "ogg", "oga", "3gp", "avi", "gif",
}

# Content-Type -> extension, used when the URL carries no usable suffix.
CTYPE_EXTS = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/x-matroska": "mkv",
    "video/quicktime": "mov",
    "video/x-flv": "flv",
    "video/mp2t": "ts",
    "video/3gpp": "3gp",
    "image/gif": "gif",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
}


def safe_name(name, fallback):
    """Build a readable, filesystem-safe filename from a video title."""
    if not name:
        return fallback
    keep = []
    for ch in str(name):
        if ch.isalnum() or ch in (" ", "-", "_", ".", "(", ")", "[", "]", "&", "+"):
            keep.append(ch)
        else:
            keep.append(" ")
    s = " ".join("".join(keep).split())
    s = s.strip(" ._")[:120].strip(" ._")
    return s or fallback


def ext_of(url, default=""):
    """Derive a media extension from the URL path, or return default."""
    base = url.split("?")[0].rstrip("/").split("/")[-1]
    if "." in base:
        cand = base.rsplit(".", 1)[-1].lower()
        if cand in MEDIA_EXTS:
            return "." + cand
    return default


def ext_of_ctype(ctype, default=".mp4"):
    """Derive a media extension from a Content-Type header."""
    ctype = (ctype or "").split(";")[0].strip().lower()
    if ctype in CTYPE_EXTS:
        return "." + CTYPE_EXTS[ctype]
    for key, ext in CTYPE_EXTS.items():
        if ctype.startswith(key):
            return "." + ext
    return default


def unique_path(path):
    """Avoid clobbering an existing file: title.mp4 -> title (1).mp4."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    i = 1
    while os.path.exists("%s (%d)%s" % (stem, i, ext)):
        i += 1
    return "%s (%d)%s" % (stem, i, ext)


def main():
    p = argparse.ArgumentParser(
        description="Save a SaveVideoKit direct option URL or job download_url to local disk")
    p.add_argument("url", help="direct_options[].download_url or get_download_status download_url")
    p.add_argument("out_dir", help="target directory")
    p.add_argument("--name", "--title", dest="name", default="",
                   help="video title used as the base filename (without extension)")
    p.add_argument("--ext", default="", help="force the file extension, e.g. mp4 or m4a")
    p.add_argument("--referer", default="", help="Referer header (the source page URL)")
    p.add_argument("--timeout", type=int, default=180, help="download timeout seconds")
    args = p.parse_args()

    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)

    base = safe_name(args.name, "video")
    if not args.name:
        sys.stderr.write("[warn] no --name/--title provided; saving as 'video.<ext>'\n")

    forced = ""
    if args.ext:
        forced = "." + str(args.ext).lstrip(".").lower()

    headers = {"User-Agent": UA, "Accept": "*/*"}
    if args.referer:
        headers["Referer"] = args.referer

    req = urllib.request.Request(args.url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=args.timeout)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read(300).decode("utf-8", "replace").strip()
        except Exception:
            pass
        sys.stderr.write("[error] HTTP %s %s%s\n" % (
            e.code, e.reason, (" - " + detail) if detail else ""))
        sys.stderr.write("        A direct link may have expired: run inspect_video again for a fresh option.\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write("[error] network error: %s\n" % (e.reason,))
        sys.exit(1)

    with resp:
        # Resolve the extension: explicit --ext, then URL suffix, then Content-Type.
        ext = forced or ext_of(resp.geturl()) or ext_of(args.url) or ext_of_ctype(resp.headers.get("Content-Type"))
        dest = unique_path(os.path.join(out, base + ext))
        try:
            total = int(resp.headers.get("Content-Length", "0") or 0)
        except ValueError:
            total = 0
        written = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
                if total:
                    sys.stderr.write("\r%.1f%% (%d KB)" % (written / total * 100, written // 1024))

    sys.stderr.write("\n")
    if written == 0:
        sys.stderr.write("[error] the response body was empty; nothing saved\n")
        try:
            os.remove(dest)
        except OSError:
            pass
        sys.exit(1)
    print("SAVED %s (%.2f MB)" % (dest, written / 1024 / 1024))


if __name__ == "__main__":
    main()
