"""One-command local frontend -> GPU inference smoke test.

What this script does:
1) Validates local marketplace is reachable.
2) Ensures a vLLM endpoint is reachable locally (or starts an SSH tunnel).
3) Starts a temporary local lender runner pointed at that vLLM endpoint.
4) Publishes one request and waits for bids.

Usage:
    .venv/bin/python -m scripts.gpu_frontend_smoke
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import httpx
from dotenv import load_dotenv

from shared.config import get_settings


def _http_ok(url: str, timeout_s: float = 2.0) -> bool:
    try:
        with urlopen(url, timeout=timeout_s) as res:  # noqa: S310 - internal/local probe URL
            return 200 <= res.status < 300
    except URLError:
        return False
    except TimeoutError:
        return False
    except Exception:
        return False


def _wait_http(url: str, timeout_s: float, poll_s: float = 0.5) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _http_ok(url):
            return True
        time.sleep(poll_s)
    return False


def _start_tunnel(
    host: str,
    key_path: str,
    local_port: int,
    remote_port: int,
    root_user: str = "root",
) -> subprocess.Popen[str]:
    cmd = [
        "ssh",
        "-i",
        key_path,
        "-N",
        "-L",
        f"{local_port}:127.0.0.1:{remote_port}",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=20",
        "-o",
        "ServerAliveCountMax=3",
        f"{root_user}@{host}",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _stop_and_capture(proc: subprocess.Popen[str], kill_after_s: float = 2.0) -> str:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=kill_after_s)
        except subprocess.TimeoutExpired:
            proc.kill()
    out = ""
    if proc.stdout:
        out = proc.stdout.read()
    return out


def _parse_hosts(primary_host: str) -> list[str]:
    raw_hosts = os.getenv("GPU_SSH_HOSTS", "")
    from_env = [h.strip() for h in raw_hosts.split(",") if h.strip()]
    defaults = ["134.199.207.234", "134.199.198.185", "129.212.179.121"]
    ordered = [h for h in [primary_host, *from_env, *defaults] if h]
    dedup: list[str] = []
    for host in ordered:
        if host not in dedup:
            dedup.append(host)
    return dedup


async def _publish_and_wait_for_bids(
    marketplace_url: str,
    timeout_s: float = 45.0,
    poll_s: float = 2.0,
) -> tuple[str, int]:
    payload = {
        "dealer_id": "dlr-gpu-smoke",
        "applicant_fico": 735,
        "loan_amount": "26500",
        "vehicle_type": "new",
        "term_months": 60,
        "state": "TX",
        "dealer_reserve_bps": 150,
    }
    async with httpx.AsyncClient(base_url=marketplace_url, timeout=10.0) as client:
        res = await client.post("/apps", json=payload)
        res.raise_for_status()
        request_id = res.json()["id"]

        elapsed = 0.0
        while elapsed < timeout_s:
            bids_res = await client.get(f"/apps/{request_id}/bids")
            bids_res.raise_for_status()
            bid_count = len(bids_res.json())
            if bid_count > 0:
                return request_id, bid_count
            await asyncio.sleep(poll_s)
            elapsed += poll_s
    return request_id, 0


async def _count_open_requests(marketplace_url: str) -> int:
    async with httpx.AsyncClient(base_url=marketplace_url, timeout=10.0) as client:
        res = await client.get("/apps", params={"status": "open"})
        res.raise_for_status()
        return len(res.json())


def _tail_buffer(proc: subprocess.Popen[str], max_chars: int = 2000) -> str:
    if proc.poll() is None:
        return ""
    if not proc.stdout:
        return ""
    text = proc.stdout.read()
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


async def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Local frontend -> GPU inference smoke test")
    parser.add_argument("--local-vllm-port", type=int, default=18001)
    parser.add_argument("--remote-vllm-port", type=int, default=8001)
    parser.add_argument("--ssh-host", default=os.getenv("AMD_DROPLET_PUBLIC_IPV4", ""))
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument(
        "--ssh-key",
        default=os.getenv("GPU_SSH_KEY", str(Path.home() / ".ssh" / "id_ed25519_amd_mi300x")),
    )
    parser.add_argument(
        "--runner-python",
        default=str(Path(".venv/bin/python")),
        help="Python executable used to run agents.runner",
    )
    parser.add_argument("--poll-timeout", type=float, default=120.0)
    args = parser.parse_args()

    settings = get_settings()
    marketplace_url = settings.marketplace_url
    local_vllm_url = f"http://127.0.0.1:{args.local_vllm_port}/v1"
    local_models_url = f"http://127.0.0.1:{args.local_vllm_port}/v1/models"

    print(f"[1/5] checking marketplace: {marketplace_url}")
    if not _http_ok(f"{marketplace_url}/healthz", timeout_s=2.0):
        print("FAIL: marketplace is not reachable. Start it with:")
        print("  .venv/bin/python -m uvicorn marketplace.server:app --host 127.0.0.1 --port 8001")
        return 1

    tunnel_proc: subprocess.Popen[str] | None = None
    print(f"[2/5] checking local vLLM endpoint: {local_models_url}")
    if not _http_ok(local_models_url, timeout_s=1.5):
        hosts = _parse_hosts(args.ssh_host)
        if not hosts:
            print("FAIL: local vLLM unavailable and no SSH host configured.")
            print("Set AMD_DROPLET_PUBLIC_IPV4 or GPU_SSH_HOSTS in .env, or pass --ssh-host.")
            return 2
        print(f"local vLLM not up; trying SSH tunnel hosts: {', '.join(hosts)}")
        tunnel_errors: list[str] = []
        for host in hosts:
            print(
                f"  - trying {host}: 127.0.0.1:{args.local_vllm_port} -> "
                f"{host}:127.0.0.1:{args.remote_vllm_port}"
            )
            proc = _start_tunnel(
                host=host,
                key_path=args.ssh_key,
                local_port=args.local_vllm_port,
                remote_port=args.remote_vllm_port,
                root_user=args.ssh_user,
            )
            if _wait_http(local_models_url, timeout_s=12.0):
                tunnel_proc = proc
                print(f"  - tunnel ready via {host}")
                break
            details = _stop_and_capture(proc).strip()
            if details:
                tunnel_errors.append(f"{host}: {details}")
            else:
                tunnel_errors.append(f"{host}: no ssh output (timeout or blocked)")
        if tunnel_proc is None:
            print("FAIL: unable to establish working GPU tunnel to any host.")
            print("Tunnel diagnostics:")
            for line in tunnel_errors:
                print(f"  * {line}")
            return 3

    open_count = await _count_open_requests(marketplace_url)
    if open_count > 0:
        print(
            f"info: {open_count} existing open requests detected; first smoke run may take longer."
        )

    print(f"[3/5] starting temporary lender runner against {local_vllm_url}")
    env = os.environ.copy()
    env["VLLM_URL"] = local_vllm_url
    env.setdefault("LORA_MODE", "prompt")
    env.setdefault("PAYMENT_MODE", "stub")
    runner_proc = subprocess.Popen(
        [args.runner_python, "-m", "agents.runner"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        print("[4/5] publishing smoke request and waiting for bids...")
        request_id, bid_count = await _publish_and_wait_for_bids(
            marketplace_url=marketplace_url,
            timeout_s=args.poll_timeout,
        )
        if bid_count <= 0:
            print(f"FAIL: request {request_id} received no bids within timeout.")
            logs = _tail_buffer(runner_proc)
            if logs.strip():
                print("Runner output:")
                print(logs.rstrip())
            return 4
        print(f"PASS: request {request_id} received {bid_count} bids.")
        print("Frontend + marketplace are now wired to GPU inference path.")
        return 0
    finally:
        print("[5/5] cleaning up temporary processes")
        if runner_proc.poll() is None:
            runner_proc.terminate()
            try:
                runner_proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                runner_proc.kill()
        if tunnel_proc and tunnel_proc.poll() is None:
            tunnel_proc.terminate()
            try:
                tunnel_proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                tunnel_proc.kill()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
