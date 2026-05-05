"""Quick vLLM benchmark probe for MI300X droplet tuning.

Measures latency and approximate output-token throughput by issuing repeated
chat-completions requests against an OpenAI-compatible vLLM endpoint.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class Sample:
    latency_s: float
    completion_tokens: int
    prompt_tokens: int


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark vLLM chat-completions endpoint")
    p.add_argument("--url", default="http://localhost:8000/v1")
    p.add_argument("--model", required=True)
    p.add_argument("--requests", type=int, default=20)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument(
        "--prompt",
        default=(
            "Underwrite this hypothetical bid request and return a short explanation "
            "of the decision in 2 sentences."
        ),
    )
    p.add_argument("--timeout-s", type=float, default=90.0)
    return p.parse_args()


async def _one_request(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
) -> Sample:
    started = time.perf_counter()
    resp = await client.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        },
    )
    resp.raise_for_status()
    elapsed = time.perf_counter() - started
    body = resp.json()
    usage = body.get("usage") or {}
    return Sample(
        latency_s=elapsed,
        completion_tokens=int(usage.get("completion_tokens", 0)),
        prompt_tokens=int(usage.get("prompt_tokens", 0)),
    )


async def _run(args: argparse.Namespace) -> int:
    sem = asyncio.Semaphore(args.concurrency)
    samples: list[Sample] = []
    errors = 0

    async with httpx.AsyncClient(timeout=args.timeout_s) as client:
        async def worker() -> None:
            nonlocal errors
            async with sem:
                try:
                    s = await _one_request(
                        client=client,
                        base_url=args.url.rstrip("/"),
                        model=args.model,
                        prompt=args.prompt,
                        max_tokens=args.max_tokens,
                    )
                    samples.append(s)
                except Exception:
                    errors += 1

        started = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(args.requests)])
        wall_s = time.perf_counter() - started

    if not samples:
        print("Benchmark failed: no successful requests.")
        return 2

    latencies = [s.latency_s for s in samples]
    completion_tokens = sum(s.completion_tokens for s in samples)
    prompt_tokens = sum(s.prompt_tokens for s in samples)
    req_per_s = len(samples) / wall_s if wall_s > 0 else 0.0
    tok_per_s = completion_tokens / wall_s if wall_s > 0 else 0.0

    print("vLLM benchmark summary")
    print(f"- endpoint: {args.url}")
    print(f"- model: {args.model}")
    print(f"- requests: {args.requests} (ok={len(samples)} err={errors})")
    print(f"- concurrency: {args.concurrency}")
    print(f"- wall time: {wall_s:.2f}s")
    print(f"- req/s: {req_per_s:.2f}")
    print(f"- completion tok/s: {tok_per_s:.2f}")
    print(f"- completion tokens total: {completion_tokens}")
    print(f"- prompt tokens total: {prompt_tokens}")
    print(
        "- latency (s): "
        f"p50={statistics.median(latencies):.2f} "
        f"p95={sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]:.2f} "
        f"max={max(latencies):.2f}"
    )
    return 0 if errors == 0 else 1


def main() -> None:
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
