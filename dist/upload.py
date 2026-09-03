#!/usr/bin/env python3
"""Upload build artifacts to toysite release API (Django session auth)."""

import argparse
import getpass
import hashlib
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://toys.hgoldfish.com"
DEFAULT_USER = "goldfish"


def _login(base_url, opener, cookies, username, password):
    """POST /api/auth/login,建立 Django session 并保存 csrftoken cookie。"""
    body = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.open(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print("login failed (%s): %s" % (exc.code, detail), file=sys.stderr)
        sys.exit(1)
    if not data.get("ok"):
        print("login failed: %s" % data, file=sys.stderr)
        sys.exit(1)
    if not _csrf_token(cookies):
        print("login succeeded but no csrftoken cookie was set; uploads would fail", file=sys.stderr)
        sys.exit(1)


def _csrf_token(cookies):
    for cookie in cookies:
        if cookie.name == "csrftoken":
            return cookie.value
    return ""


def upload(base_url, opener, cookies, app_id, version, platform, file_path, notes, rollout_percent):
    boundary = "----toysite-upload-%016x" % (hash(os.urandom(8)) & 0xFFFFFFFFFFFFFFFF)
    filename = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        body = f.read()
    file_hash = hashlib.sha512(body).hexdigest()

    parts = []
    fields = [
        ("app_id", app_id),
        ("version", version),
        ("platform", platform),
        ("notes", notes),
    ]
    if rollout_percent is not None:
        fields.append(("rollout_percent", str(rollout_percent)))

    for name, value in fields:
        parts.append(
            ("--%s\r\n" % boundary).encode()
            + ('Content-Disposition: form-data; name="%s"\r\n\r\n' % name).encode()
            + value.encode()
            + b"\r\n"
        )

    parts.append(
        ("--%s\r\n" % boundary).encode()
        + (
            'Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename
        ).encode()
        + b"Content-Type: application/octet-stream\r\n\r\n"
        + body
        + b"\r\n"
    )
    parts.append(("--%s--\r\n" % boundary).encode())
    payload = b"".join(parts)

    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/admin/releases",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "multipart/form-data; boundary=" + boundary,
            "X-CSRFToken": _csrf_token(cookies),
            # https 下 Django CSRF 校验要求 Origin/Referer 同源
            "Referer": base_url.rstrip("/") + "/login/",
        },
    )

    try:
        with opener.open(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = resp.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print("upload failed (%s): %s" % (exc.code, detail), file=sys.stderr)
        sys.exit(1)

    # toysite 的 POST /api/admin/releases 成功时固定返回 201 + release payload
    if status != 201:
        print("unexpected status %d: %s" % (status, data), file=sys.stderr)
        sys.exit(1)
    sha = data.get("sha512")
    if not sha:
        print("upload rejected: response missing sha512", file=sys.stderr)
        sys.exit(1)
    if sha != file_hash:
        print("upload rejected: server sha512 mismatch", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Upload build artifact to toysite")
    parser.add_argument("file", help="artifact path (.7z)")
    parser.add_argument("--app", required=False, default="quickpanel", help="app id, e.g. lafdup")
    parser.add_argument("--version", required=True, help="version, e.g. 1.0.1")
    parser.add_argument("--platform", default="win32", help="win32 or linux-x64")
    parser.add_argument("--notes", default="", help="release notes")
    parser.add_argument("--rollout", type=int, default=None, help="rollout percent 0-100")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("TOYSITE_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--user", default=DEFAULT_USER)
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print("file not found: %s" % args.file, file=sys.stderr)
        sys.exit(1)
    if args.rollout is not None and not 0 <= args.rollout <= 100:
        print("rollout must be 0-100", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password for %s: " % args.user)

    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    _login(args.base_url, opener, cookies, args.user, password)

    upload(
        args.base_url,
        opener,
        cookies,
        args.app,
        args.version,
        args.platform,
        args.file,
        args.notes,
        args.rollout,
    )


if __name__ == "__main__":
    main()
