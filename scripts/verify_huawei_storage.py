#!/usr/bin/env python3
"""Run a destructive-but-self-cleaning end-to-end probe against NoSpace storage."""

from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

import requests


def env_value(path: Path, name: str) -> str:
    prefix = f"{name}="
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def upload_invite(raw_invites: str) -> str:
    for entry in raw_invites.split(","):
        parts = [part.strip() for part in entry.split(":")]
        if len(parts) == 3 and parts[0] and parts[1] == "upload" and parts[2]:
            return parts[0]
    raise RuntimeError("No local upload probe invite is configured")


def require_ok(response: requests.Response, action: str) -> requests.Response:
    if response.ok:
        return response
    raise RuntimeError(f"{action} failed with HTTP {response.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--origin", default="https://omoyx.github.io")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    invite = upload_invite(env_value(args.env_file, "INVITES"))
    smart_filename_url = env_value(args.env_file, "SMART_FILENAME_UPSTREAM_URL")
    internal_api_key = env_value(args.env_file, "INTERNAL_API_KEY")
    headers = {"X-Invite-Code": invite}
    payload = f"NoSpace Huawei storage probe {uuid.uuid4()}\n".encode()
    expected_hash = hashlib.sha256(payload).hexdigest()
    asset_id: str | None = None

    try:
        session = require_ok(
            requests.post(
                f"{base_url}/api/session",
                json={"invite": invite},
                timeout=30,
            ),
            "session validation",
        ).json()
        if session.get("role") != "upload":
            raise RuntimeError("Probe invite does not have the upload role")

        if not smart_filename_url or not internal_api_key:
            raise RuntimeError("Smart filename control-plane configuration is missing")
        smart_filename = require_ok(
            requests.post(
                smart_filename_url,
                headers={"X-Internal-Api-Key": internal_api_key},
                json={
                    "originalName": "20260729_155000.txt",
                    "mimeType": "text/plain",
                    "imageAnalysis": None,
                },
                timeout=60,
            ),
            "smart filename control-plane request",
        ).json()
        if "displayName" not in smart_filename or "renameModel" not in smart_filename:
            raise RuntimeError("Smart filename control-plane response is malformed")

        before = require_ok(
            requests.get(f"{base_url}/api/assets", headers=headers, timeout=30),
            "initial asset listing",
        ).json()

        preflight = require_ok(
            requests.options(
                f"{base_url}/api/assets",
                headers={
                    "Origin": args.origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "x-invite-code",
                },
                timeout=30,
            ),
            "CORS preflight",
        )
        allowed_origin = preflight.headers.get("access-control-allow-origin")
        if allowed_origin not in {"*", args.origin}:
            raise RuntimeError("CORS preflight did not allow the frontend origin")

        uploaded = require_ok(
            requests.post(
                f"{base_url}/api/assets",
                headers=headers,
                files={"file": ("huawei-e2e-probe.txt", payload, "text/plain")},
                data={"note": "automated deployment probe"},
                timeout=90,
            ),
            "asset upload",
        ).json()
        asset_id = uploaded["id"]

        after_upload = require_ok(
            requests.get(f"{base_url}/api/assets", headers=headers, timeout=30),
            "post-upload asset listing",
        ).json()
        if asset_id not in {item.get("id") for item in after_upload}:
            raise RuntimeError("Uploaded asset is absent from the index")

        invite_query = quote(invite, safe="")
        for field, action in (("url", "inline read"), ("downloadUrl", "download")):
            response = require_ok(
                requests.get(
                    f"{base_url}{uploaded[field]}?invite={invite_query}",
                    timeout=30,
                ),
                action,
            )
            actual_hash = hashlib.sha256(response.content).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(f"{action} returned different bytes")

        require_ok(
            requests.delete(
                f"{base_url}/api/assets/{quote(asset_id, safe='')}",
                headers=headers,
                timeout=30,
            ),
            "asset deletion",
        )
        asset_id = None

        after_delete = require_ok(
            requests.get(f"{base_url}/api/assets", headers=headers, timeout=30),
            "post-delete asset listing",
        ).json()
        if len(after_delete) != len(before):
            raise RuntimeError("Asset count was not restored after probe deletion")

        print(f"session_role={session['role']}")
        print(
            "smart_filename_control_plane="
            f"{smart_filename.get('renameModel') or 'reachable-without-rename'}"
        )
        print(f"assets_before={len(before)}")
        print("cors_preflight=ok")
        print("upload_list_read_download_delete=ok")
        print(f"payload_sha256={expected_hash}")
        return 0
    finally:
        if asset_id:
            try:
                requests.delete(
                    f"{base_url}/api/assets/{quote(asset_id, safe='')}",
                    headers=headers,
                    timeout=30,
                )
            except requests.RequestException:
                print("warning: probe cleanup failed", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
