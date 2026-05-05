"""Hero-shot demo: 50 bid requests published in ~10s, 5 lender agents bid concurrently.

Run with the marketplace + lender runner already up:
    .venv/bin/uvicorn marketplace.server:app --port 8001
    .venv/bin/python -m agents.runner
    .venv/bin/python -m scripts.concurrency_demo

The script:
  1. Publishes 50 synthetic bid requests (with small jitter) to the marketplace.
  2. Polls /apps + /apps/{id}/bids while a rich.Live display shows real-time
     metrics: requests published, bids per lender, decisions/s rolling, p50
     publish->first-bid latency, total insertion fees paid.
  3. Stops when all requests have bids OR when --duration seconds elapse.
  4. Prints a final summary panel.

This is what gets screen-recorded for the submission demo.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from data.synthetic_apps import generate_requests
from shared.config import get_settings
from shared.gpu_metrics import snapshot as gpu_snapshot


@dataclass
class DemoMetrics:
    started_at: float
    n_target: int
    requests_published: int = 0
    bids_per_lender: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    bid_timestamps: list[float] = field(default_factory=list)
    publish_at: dict[str, float] = field(default_factory=dict)
    first_bid_latency_s: list[float] = field(default_factory=list)
    insertion_fees_paid_usdc: Decimal = Decimal("0")
    seen_bid_ids: set[str] = field(default_factory=set)
    requests_with_bid: set[str] = field(default_factory=set)

    @property
    def total_bids(self) -> int:
        return sum(self.bids_per_lender.values())

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at

    def decisions_per_sec_rolling(self, window_s: float = 5.0) -> float:
        cutoff = time.monotonic() - window_s
        recent = [t for t in self.bid_timestamps if t >= cutoff]
        if not recent:
            return 0.0
        return len(recent) / window_s

    def p50_first_bid_latency_s(self) -> float | None:
        return statistics.median(self.first_bid_latency_s) if self.first_bid_latency_s else None


def _summary_panel(m: DemoMetrics, gpu: dict[str, Any]) -> Panel:
    p50 = m.p50_first_bid_latency_s()
    p50_str = f"{p50:.2f}s" if p50 is not None else "—"
    rate = m.decisions_per_sec_rolling()

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="bold cyan")
    table.add_column()
    table.add_row("Elapsed", f"{m.elapsed_s:.1f}s")
    table.add_row("Requests published", f"{m.requests_published} / {m.n_target}")
    table.add_row("Bids submitted", str(m.total_bids))
    table.add_row("Requests with ≥1 bid", f"{len(m.requests_with_bid)} / {m.requests_published}")
    table.add_row("Decisions/s (5s avg)", f"{rate:.1f}")
    table.add_row("Median pub→first-bid", p50_str)
    table.add_row("Total insertion fees", f"${m.insertion_fees_paid_usdc:.2f} USDC")
    if gpu:
        table.add_row("[magenta]GPU util[/]", f"{gpu.get('util_pct', 0)}%")
        mem_used = gpu.get("mem_used_gb", 0.0)
        mem_total = gpu.get("mem_total_gb", 0.0)
        table.add_row("[magenta]GPU VRAM[/]", f"{mem_used:.1f} / {mem_total:.0f} GB")
        table.add_row("[magenta]GPU power[/]", f"{gpu.get('power_w', 0):.0f} W")
        table.add_row("[magenta]GPU temp[/]", f"{gpu.get('temp_c', 0)} °C")
    return Panel(table, title="[bold]Concurrency Demo[/]", border_style="green")


def _per_lender_panel(m: DemoMetrics) -> Panel:
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Lender", style="cyan")
    table.add_column("Bids", justify="right")
    table.add_column("Bar", ratio=2)

    max_bids = max(m.bids_per_lender.values(), default=0) or 1
    for lender_id in sorted(m.bids_per_lender.keys()):
        n = m.bids_per_lender[lender_id]
        bar = "█" * int(40 * n / max_bids)
        table.add_row(lender_id, str(n), Text(bar, style="green"))
    return Panel(table, title="[bold]Bids per lender[/]", border_style="cyan")


def _layout(m: DemoMetrics, log_lines: list[str], gpu: dict[str, Any]) -> Layout:
    root = Layout()
    root.split_column(
        Layout(name="top", size=15),
        Layout(name="middle", size=10),
        Layout(name="log", ratio=1),
    )
    root["top"].update(_summary_panel(m, gpu))
    root["middle"].update(_per_lender_panel(m))
    log_text = "\n".join(log_lines[-12:])
    root["log"].update(Panel(log_text, title="[bold]Events[/]", border_style="white"))
    return root


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


async def _publish_requests(
    http: httpx.AsyncClient,
    n: int,
    seed: int | None,
    duration_s: float,
    metrics: DemoMetrics,
    log: list[str],
) -> None:
    """Publish ``n`` bid requests over ~``duration_s`` seconds with jitter."""
    requests = generate_requests(n=n, seed=seed)
    rng = random.Random(seed)
    base_delay = duration_s / max(1, n)

    for req in requests:
        body = {
            "dealer_id": req.dealer_id,
            "applicant_fico": req.applicant_fico,
            "loan_amount": str(req.loan_amount),
            "vehicle_type": req.vehicle_type.value,
            "term_months": req.term_months,
            "state": req.state,
            "dealer_reserve_bps": req.dealer_reserve_bps,
        }
        try:
            r = await http.post("/apps", json=body)
            r.raise_for_status()
            published_id = r.json()["id"]
        except httpx.HTTPError as e:
            log.append(f"[{_now_iso()}] [red]publish failed:[/] {e}")
            continue

        metrics.requests_published += 1
        metrics.publish_at[published_id] = time.monotonic()
        log.append(
            f"[{_now_iso()}] published {published_id[:8]} "
            f"FICO={req.applicant_fico} {req.vehicle_type.value} ${req.loan_amount:.0f}"
        )
        jitter = rng.uniform(0, base_delay)
        await asyncio.sleep(base_delay + jitter)


async def _watch_bids(
    http: httpx.AsyncClient,
    metrics: DemoMetrics,
    log: list[str],
    insertion_fee: Decimal,
    stop: asyncio.Event,
) -> None:
    """Poll /apps?status=open and per-request /bids, track new bids in metrics."""
    while not stop.is_set():
        try:
            r = await http.get("/apps")
            r.raise_for_status()
            requests_payload = r.json()
        except httpx.HTTPError as e:
            log.append(f"[{_now_iso()}] [red]list requests failed:[/] {e}")
            await asyncio.sleep(0.5)
            continue

        for req in requests_payload:
            try:
                br = await http.get(f"/apps/{req['id']}/bids")
                br.raise_for_status()
                bids = br.json()
            except httpx.HTTPError:
                continue

            for bid in bids:
                bid_id = bid["id"]
                if bid_id in metrics.seen_bid_ids:
                    continue
                metrics.seen_bid_ids.add(bid_id)
                metrics.bids_per_lender[bid["lender_id"]] += 1
                now = time.monotonic()
                metrics.bid_timestamps.append(now)
                metrics.insertion_fees_paid_usdc += insertion_fee

                pub_t = metrics.publish_at.get(req["id"])
                if pub_t is not None and req["id"] not in metrics.requests_with_bid:
                    metrics.first_bid_latency_s.append(now - pub_t)
                    metrics.requests_with_bid.add(req["id"])

                apr_pct = bid["apr_bps"] / 100
                log.append(
                    f"[{_now_iso()}] bid [cyan]{bid['lender_id']}[/] "
                    f"on {req['id'][:8]} APR {apr_pct:.2f}%"
                )
        await asyncio.sleep(0.4)


async def run_demo(
    n: int = 50,
    publish_window_s: float = 10.0,
    max_duration_s: float = 60.0,
    seed: int | None = None,
    console: Console | None = None,
) -> DemoMetrics:
    """Programmatic entry point. Returns final metrics."""
    settings = get_settings()
    console = console or Console()

    metrics = DemoMetrics(started_at=time.monotonic(), n_target=n)
    log: list[str] = []
    stop_watch = asyncio.Event()
    gpu_state: dict[str, Any] = {}

    async with httpx.AsyncClient(base_url=settings.marketplace_url, timeout=15.0) as http:
        with Live(
            _layout(metrics, log, gpu_state), console=console, refresh_per_second=4
        ) as live:

            async def _ticker() -> None:
                last_gpu_poll = 0.0
                while not stop_watch.is_set():
                    now = time.monotonic()
                    if now - last_gpu_poll > 1.0:
                        snap = gpu_snapshot()
                        if snap:
                            gpu_state.update(snap)
                        last_gpu_poll = now
                    live.update(_layout(metrics, log, gpu_state))
                    await asyncio.sleep(0.25)

            ticker_task = asyncio.create_task(_ticker())
            watcher_task = asyncio.create_task(
                _watch_bids(http, metrics, log, settings.insertion_fee_usdc, stop_watch)
            )
            await _publish_requests(http, n, seed, publish_window_s, metrics, log)

            done_at = time.monotonic() + max_duration_s
            while time.monotonic() < done_at:
                if (
                    metrics.requests_published >= n
                    and metrics.total_bids > 0
                    and metrics.bid_timestamps
                    and time.monotonic() - metrics.bid_timestamps[-1] > 5.0
                ):
                    break
                await asyncio.sleep(0.5)

            stop_watch.set()
            await asyncio.gather(ticker_task, watcher_task, return_exceptions=True)
            live.update(_layout(metrics, log, gpu_state))

    _print_summary(console, metrics)
    return metrics


def _print_summary(console: Console, m: DemoMetrics) -> None:
    p50 = m.p50_first_bid_latency_s()
    table = Table(title="[bold]Final summary[/]", show_header=False, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Total wall-clock", f"{m.elapsed_s:.2f}s")
    table.add_row("Requests published", f"{m.requests_published}")
    table.add_row("Bids submitted", f"{m.total_bids}")
    table.add_row("Inference calls", f"{m.total_bids} approves (declines not bid)")
    table.add_row("Throughput (bids/s)", f"{m.total_bids / max(m.elapsed_s, 1e-6):.2f}")
    table.add_row(
        "Median pub→first-bid", f"{p50:.2f}s" if p50 is not None else "—"
    )
    table.add_row("Insertion fees paid", f"${m.insertion_fees_paid_usdc:.2f} USDC")
    table.add_row("Requests with ≥1 bid", f"{len(m.requests_with_bid)} / {m.requests_published}")
    for lender, count in sorted(m.bids_per_lender.items()):
        table.add_row(f"  bids by {lender}", str(count))
    console.print(table)


def main() -> None:
    p = argparse.ArgumentParser(description="Run the Credit App+ concurrency demo")
    p.add_argument("--n", type=int, default=50, help="apps to publish")
    p.add_argument(
        "--publish-window",
        type=float,
        default=10.0,
        help="seconds over which to publish all apps (default 10s)",
    )
    p.add_argument(
        "--max-duration",
        type=float,
        default=60.0,
        help="hard ceiling on total demo runtime",
    )
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args()
    asyncio.run(
        run_demo(
            n=args.n,
            publish_window_s=args.publish_window,
            max_duration_s=args.max_duration,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
