#!/usr/bin/env python3
"""Provision and manage DigitalOcean droplets via API.

This script is intentionally minimal and uses only the Python standard library.
Authentication is handled with a DigitalOcean Personal Access Token (PAT)
provided via env var (DO_API_TOKEN by default).
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "https://api.digitalocean.com/v2"


class DOClient:
    def __init__(self, token: str) -> None:
        self._token = token
        self._ssl_context = ssl.create_default_context()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{BASE_URL}{path}{query}"
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url=url,
            data=body,
            method=method.upper(),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, context=self._ssl_context) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            msg = raw
            try:
                parsed = json.loads(raw)
                msg = json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                pass
            raise RuntimeError(f"DigitalOcean API error ({exc.code}): {msg}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error calling DigitalOcean API: {exc}") from exc


def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def cmd_list(client: DOClient, args: argparse.Namespace) -> None:
    response = client.request(
        "GET",
        "/droplets",
        params={"page": args.page, "per_page": args.per_page, "tag_name": args.tag or ""},
    )
    _emit(response)


def cmd_get(client: DOClient, args: argparse.Namespace) -> None:
    response = client.request("GET", f"/droplets/{args.droplet_id}")
    _emit(response)


def cmd_delete(client: DOClient, args: argparse.Namespace) -> None:
    client.request("DELETE", f"/droplets/{args.droplet_id}")
    _emit({"ok": True, "deleted_droplet_id": args.droplet_id})


def cmd_list_images(client: DOClient, args: argparse.Namespace) -> None:
    response = client.request(
        "GET",
        "/images",
        params={"type": args.type, "private": str(args.private).lower(), "per_page": args.per_page},
    )
    _emit(response)


def cmd_list_sizes(client: DOClient, args: argparse.Namespace) -> None:
    response = client.request("GET", "/sizes", params={"per_page": args.per_page})
    _emit(response)


def cmd_list_ssh_keys(client: DOClient, _args: argparse.Namespace) -> None:
    response = client.request("GET", "/account/keys")
    _emit(response)


def cmd_create(client: DOClient, args: argparse.Namespace) -> None:
    ssh_keys: list[str | int] = []
    if args.ssh_key_id:
        ssh_keys.extend(args.ssh_key_id)
    if args.ssh_key_fingerprint:
        ssh_keys.extend(args.ssh_key_fingerprint)

    payload: dict[str, Any] = {
        "name": args.name,
        "region": args.region,
        "size": args.size,
        "image": args.image,
        "ssh_keys": ssh_keys,
        "backups": args.backups,
        "ipv6": args.ipv6,
        "monitoring": args.monitoring,
        "tags": args.tag or [],
    }
    if args.user_data_file:
        with open(args.user_data_file, "r", encoding="utf-8") as fh:
            payload["user_data"] = fh.read()

    response = client.request("POST", "/droplets", payload=payload)
    _emit(response)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage DigitalOcean droplets via API")
    parser.add_argument(
        "--token-env",
        default="DO_API_TOKEN",
        help="Env var that contains the DigitalOcean PAT (default: DO_API_TOKEN)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List droplets")
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--per-page", type=int, default=50, dest="per_page")
    p_list.add_argument("--tag", default="", help="Optional tag filter")

    p_get = sub.add_parser("get", help="Get one droplet")
    p_get.add_argument("droplet_id", type=int)

    p_delete = sub.add_parser("delete", help="Delete one droplet")
    p_delete.add_argument("droplet_id", type=int)

    p_create = sub.add_parser("create", help="Create a droplet")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--region", required=True, help="Example: nyc3")
    p_create.add_argument("--size", required=True, help="Droplet size slug")
    p_create.add_argument("--image", required=True, help="Image slug or image ID")
    p_create.add_argument("--ssh-key-id", action="append", type=int, default=[])
    p_create.add_argument("--ssh-key-fingerprint", action="append", default=[])
    p_create.add_argument("--tag", action="append", default=[])
    p_create.add_argument("--user-data-file", default="")
    p_create.add_argument("--backups", action="store_true")
    p_create.add_argument("--ipv6", action="store_true")
    p_create.add_argument("--monitoring", action="store_true")

    p_images = sub.add_parser("list-images", help="List images")
    p_images.add_argument("--type", default="distribution", choices=["distribution", "application"])
    p_images.add_argument("--private", action="store_true")
    p_images.add_argument("--per-page", type=int, default=100, dest="per_page")

    p_sizes = sub.add_parser("list-sizes", help="List droplet sizes")
    p_sizes.add_argument("--per-page", type=int, default=200, dest="per_page")

    sub.add_parser("list-ssh-keys", help="List SSH keys")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    token = os.getenv(args.token_env, "").strip()
    if not token:
        print(f"error: {args.token_env} is not set", file=sys.stderr)
        return 2

    client = DOClient(token)
    dispatch = {
        "list": cmd_list,
        "get": cmd_get,
        "delete": cmd_delete,
        "create": cmd_create,
        "list-images": cmd_list_images,
        "list-sizes": cmd_list_sizes,
        "list-ssh-keys": cmd_list_ssh_keys,
    }
    dispatch[args.command](client, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
