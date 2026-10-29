#!/usr/bin/env python3
"""SaveVideoKit skill self-updater.

Checks the latest GitHub release of SaveVideoKit/mcp and, when a newer version
exists, updates this skill directory in place (with a backup).

Run it on first activation in a session:

    python3 scripts/check_update.py --auto     # update if a newer release exists
    python3 scripts/check_update.py            # check only (cached 24h)
    python3 scripts/check_update.py --force    # ignore the cache
    python3 scripts/check_update.py --ttl 3600 # custom cache TTL (seconds)

Design notes:
- Stdlib only (no dependencies).
- Network is used at most once per TTL (default 24h); the result is cached in
  `.update_check.json` next to this skill.
- Only this skill directory is touched; the previous version is copied to
  `<dir>.bak-<timestamp>` before any file is replaced.
- The client subfolder to fetch is read from `.client` (e.g. workbuddy, codex,
  claude-code, cursor, opencode, dsh).
"""

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

REPO = "SaveVideoKit/mcp"
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(SKILL_DIR, "VERSION")
CLIENT_FILE = os.path.join(SKILL_DIR, ".client")
CACHE_FILE = os.path.join(SKILL_DIR, ".update_check.json")
DEFAULT_TTL = 24 * 3600
UA = "savevideokit-updater"


def read_text(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def read_version(path):
    return read_text(path, "0.0.0").lstrip("v") or "0.0.0"


def client_id():
    return read_text(CLIENT_FILE, "workbuddy") or "workbuddy"


def parse_ver(value):
    core = value.strip().lstrip("v").split("-")[0].split("+")[0]
    parts = []
    for piece in core.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(remote, local):
    return parse_ver(remote) > parse_ver(local)


def http_json(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": UA}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def remote_version():
    try:
        data = http_json("https://api.github.com/repos/%s/releases/latest" % REPO)
        tag = data.get("tag_name")
        if tag:
            return tag.lstrip("v")
    except Exception:
        pass
    try:
        tags = http_json("https://api.github.com/repos/%s/tags" % REPO)
        versions = [t["name"].lstrip("v") for t in tags if t.get("name")]
        return max(versions, key=parse_ver) if versions else None
    except Exception:
        return None


def read_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def download_tarball(version):
    url = "https://codeload.github.com/%s/tar.gz/refs/tags/v%s" % (REPO, version)
    fd, path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp, open(path, "wb") as f:
        shutil.copyfileobj(resp, f)
    return path


def safe_extract(tf, dest):
    try:
        tf.extractall(dest, filter="data")  # Python 3.12+
    except TypeError:
        tf.extractall(dest)


def update(version, client):
    tar_path = download_tarball(version)
    tmp = tempfile.mkdtemp(prefix="savevideokit-")
    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            safe_extract(tf, tmp)
        entries = os.listdir(tmp)
        if not entries:
            print("[update] empty archive", file=sys.stderr)
            return False
        root = os.path.join(tmp, entries[0])
        src = os.path.join(root, client)
        if not os.path.isdir(src):
            src = os.path.join(root, "workbuddy")
        if not os.path.isdir(src):
            print(
                "[update] client folder '%s' not found in archive" % client,
                file=sys.stderr,
            )
            return False

        backup = "%s.bak-%d" % (SKILL_DIR, int(time.time()))
        shutil.copytree(SKILL_DIR, backup)

        for name in os.listdir(src):
            s = os.path.join(src, name)
            d = os.path.join(SKILL_DIR, name)
            if os.path.isdir(s):
                if os.path.isdir(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(version + "\n")
        print("[update] updated to %s; backup at %s" % (version, backup))
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            os.remove(tar_path)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser(description="SaveVideoKit skill self-updater")
    ap.add_argument("--auto", action="store_true", help="update if a newer release exists")
    ap.add_argument("--check", action="store_true", help="check only (default)")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--ttl", type=int, default=DEFAULT_TTL, help="cache TTL in seconds")
    args = ap.parse_args()

    local = read_version(VERSION_FILE)
    cache = read_cache()
    now = time.time()

    if not args.force and cache.get("remote") and now - cache.get("last_check", 0) < args.ttl:
        remote, source = cache["remote"], "cache"
    else:
        remote, source = remote_version(), "network"
        if remote:
            write_cache({"last_check": now, "remote": remote})

    if not remote:
        print("[update] local %s; remote check failed (offline?)" % local)
        return 0

    if is_newer(remote, local):
        print("[update] update available: %s -> %s (from %s)" % (local, remote, source))
        if args.auto and not args.check:
            return 0 if update(remote, client_id()) else 1
        print("[update] run with --auto to update")
    else:
        print("[update] up to date: %s (remote %s, from %s)" % (local, remote, source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
