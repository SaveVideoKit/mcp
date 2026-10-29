#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SaveVideoKit local download helper (zero dependencies, Python standard library only).

Persists the download_url returned by get_download_status to local disk.
The remote file is retained for only ~2 hours, so call this script as soon as possible.

Usage:
    python3 download_file.py "<download_url>" "<output_dir>" [--name "title"] [--timeout 180]
"""
import argparse
import os
import sys
import urllib.request

UA = "savevideokit-cli/1.0 (+https://www.savevideokit.com)"


def safe_name(name, fallback):
    """Build a filesystem-safe filename from an arbitrary title."""
    if not name:
        return fallback
    keep = []
    for ch in name:
        if ch.isalnum() or ch in (" ", "-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    s = "".join(keep).strip().replace(" ", "_")
    return s[:120] or fallback


def ext_of(url, default=".mp4"):
    """Derive a file extension from the URL, falling back to .mp4."""
    base = url.split("?")[0].rstrip("/").split("/")[-1]
    if "." in base:
        e = "." + base.rsplit(".", 1)[-1].split("/")[0][:8]
        if 2 <= len(e) <= 9:
            return e
    return default


def main():
    p = argparse.ArgumentParser(description="Save a SaveVideoKit download_url to local disk")
    p.add_argument("url", help="download_url returned by get_download_status")
    p.add_argument("out_dir", help="target directory")
    p.add_argument("--name", default="", help="preferred base filename (without extension)")
    p.add_argument("--timeout", type=int, default=180, help="download timeout seconds")
    args = p.parse_args()

    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)
    ext = ext_of(args.url)
    base = safe_name(args.name, "savevideokit_video")
    dest = os.path.join(out, base + ext)

    req = urllib.request.Request(args.url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=args.timeout) as r:
        total = 0
        try:
            total = int(r.headers.get("Content-Length", "0") or 0)
        except ValueError:
            total = 0
        written = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
                if total:
                    sys.stderr.write(f"\r{written / total * 100:.1f}% ({written // 1024} KB)")
    sys.stderr.write("\n")
    print(f"SAVED {dest} ({written / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
