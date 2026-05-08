"""Streamlit dealer dashboard for Credit App+.

Run with:
    streamlit run ui/dealer_app.py

Three tabs:
  * Active Requests — open bid requests with live-ranked bids and Accept buttons
  * Settled         — closed requests with three rev-split tx links to BaseScan
  * Treasury        — cumulative insertion fees, win-premium cut, payouts

The sidebar also exposes a "Run Concurrency Demo" button that publishes 50
bid requests in ~10s; new bids stream into the Active Requests tab as the
lender agents process them. Rich live-metrics output goes to the terminal
where Streamlit was launched.
"""
from __future__ import annotations

import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

from shared.config import get_settings
from ui.design_theme import apply_appbid_theme, render_page_header, render_sidebar_brand

PROJECT_ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Credit App+ Dealer", layout="wide")

settings = get_settings()
MKT = settings.marketplace_url
BASESCAN_TX = "https://sepolia.basescan.org/tx"
DEMO_MODE = settings.settlement_mode

apply_appbid_theme()


def _api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    r = httpx.get(f"{MKT}{path}", params=params, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _api_post(path: str, body: dict[str, Any]) -> Any:
    r = httpx.post(f"{MKT}{path}", json=body, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _tx_link(tx_hash: str) -> str:
    return f"[{tx_hash[:10]}…]({BASESCAN_TX}/{tx_hash})"


def _render_overview_card(label: str, value: str, sub: str, health: bool = False) -> str:
    health_badge = "<div class='appbid-health-live'>LIVE</div>" if health else ""
    return (
        "<div class='appbid-overview-card'>"
        f"<div class='label'>{label}</div>"
        f"<div class='value'>{value}</div>"
        f"<div class='sub'>{sub}</div>"
        f"{health_badge}"
        "</div>"
    )


def render_terminal_overview() -> None:
    """Render prototype-like health + KPI strips above tabbed content."""
    try:
        open_requests = _api_get("/apps", {"status": "open"})
        closed_requests = _api_get("/apps", {"status": "closed"})
        treasury = _api_get("/treasury")
    except httpx.HTTPError:
        st.warning("Live overview is unavailable until marketplace APIs respond.")
        return

    total_requests = len(open_requests) + len(closed_requests)
    avg_bids = (treasury["total_bids"] / total_requests) if total_requests else 0.0
    insertion_fee = Decimal(str(settings.insertion_fee_usdc))

    market_latency_ms: str
    market_subtext: str
    t0 = time.perf_counter()
    try:
        _api_get("/healthz")
        market_latency_ms = f"{(time.perf_counter() - t0) * 1000:.0f}ms"
        market_subtext = "live health probe"
    except httpx.HTTPError:
        market_latency_ms = "down"
        market_subtext = "health probe failed"

    vllm_latency_ms: str
    vllm_subtext: str
    try:
        t1 = time.perf_counter()
        vllm_models_url = f"{settings.vllm_url.rstrip('/')}/models"
        r = httpx.get(vllm_models_url, timeout=4.0)
        r.raise_for_status()
        vllm_latency_ms = f"{(time.perf_counter() - t1) * 1000:.0f}ms"
        vllm_subtext = settings.vllm_model.split("/")[-1]
    except httpx.HTTPError:
        vllm_latency_ms = "down"
        vllm_subtext = settings.vllm_model.split("/")[-1]

    st.markdown("<div class='appbid-section-label'>System Health</div>", unsafe_allow_html=True)
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        st.markdown(
            _render_overview_card("Marketplace API", market_latency_ms, market_subtext, health=True),
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            _render_overview_card(
                "Bid Runner",
                f"{len(open_requests)} open",
                f"{treasury['total_bids']} total bids seen",
                health=True,
            ),
            unsafe_allow_html=True,
        )
    with h3:
        st.markdown(
            _render_overview_card("Pricing Model", vllm_latency_ms, vllm_subtext, health=True),
            unsafe_allow_html=True,
        )
    with h4:
        mode_text = "STUB" if DEMO_MODE.lower() == "stub" else "LIVE"
        st.markdown(
            _render_overview_card("Settlement Mode", mode_text, f"insertion fee ${insertion_fee:.2f}"),
            unsafe_allow_html=True,
        )

    st.markdown("<div class='appbid-section-label'>Marketplace KPIs</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            _render_overview_card(
                "Win Premium · Total",
                f"${Decimal(treasury['win_premium_total_usdc']):,.2f}",
                "topline gross",
            ),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            _render_overview_card(
                "Active Requests",
                str(len(open_requests)),
                f"{total_requests} total requests",
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            _render_overview_card(
                "Bids Received",
                str(treasury["total_bids"]),
                f"{avg_bids:.1f} avg per request",
            ),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            _render_overview_card(
                "Marketplace Cut",
                f"${Decimal(treasury['marketplace_cut_usdc']):,.2f}",
                "win-premium share",
            ),
            unsafe_allow_html=True,
        )


# ============= Sidebar: publish =============
with st.sidebar:
    render_sidebar_brand()
    st.header("Publish Bid Request")
    with st.form("publish_request", clear_on_submit=True):
        dealer_id = st.text_input("Dealer ID", value="dlr-demo")
        applicant_fico = st.slider("Applicant FICO", 480, 820, 720)
        loan_amount = st.number_input(
            "Loan Amount (USD)",
            min_value=5_000.0,
            max_value=100_000.0,
            value=25_000.0,
            step=500.0,
        )
        vehicle_type = st.selectbox("Vehicle Type", ["new", "used", "ev"])
        term_months = st.selectbox("Term (months)", [36, 48, 60, 72, 84], index=2)
        state_code = st.text_input("State (2-letter)", value="TX", max_chars=2)
        dealer_reserve_bps = st.slider("Dealer Reserve (bps)", 0, 500, 200)
        submitted = st.form_submit_button("Publish")
        if submitted:
            try:
                created = _api_post(
                    "/apps",
                    {
                        "dealer_id": dealer_id,
                        "applicant_fico": int(applicant_fico),
                        "loan_amount": str(Decimal(str(loan_amount))),
                        "vehicle_type": vehicle_type,
                        "term_months": int(term_months),
                        "state": state_code,
                        "dealer_reserve_bps": int(dealer_reserve_bps),
                    },
                )
                st.success(f"Published request {created['id'][:8]}")
            except httpx.HTTPError as e:
                st.error(f"Publish failed: {e}")

    st.markdown("---")
    st.subheader("Concurrency Demo")
    st.caption(
        "Publishes a burst of bid requests; lender agents underwrite + bid concurrently. "
        "Watch the Active Requests tab fill up."
    )
    demo_n = st.slider("Requests to publish", 10, 100, 50, key="demo_n")
    demo_window = st.slider(
        "Publish window (s)", 2, 30, 10, key="demo_window",
        help="requests are spread across this window with jitter",
    )
    proc: subprocess.Popen[bytes] | None = st.session_state.get("demo_proc")
    running = proc is not None and proc.poll() is None
    if st.button(
        "Run Concurrency Demo" if not running else "Demo running…",
        disabled=running,
        type="primary",
    ):
        new_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.concurrency_demo",
                "--n",
                str(int(demo_n)),
                "--publish-window",
                str(int(demo_window)),
            ],
            cwd=PROJECT_ROOT,
        )
        st.session_state["demo_proc"] = new_proc
        st.success(
            f"Demo started (PID {new_proc.pid}). Bids will stream into Active Requests. "
            "Live metrics print in the Streamlit terminal."
        )
    elif running and proc is not None:
        st.info(f"Demo running (PID {proc.pid})")

    st.markdown("---")
    st.caption(f"Marketplace: `{MKT}`")


# ============= Main =============
render_page_header(
    "Credit App+ Dealer Terminal",
    "Publish PII-free bid requests, stream lender competition, then accept and settle.",
    DEMO_MODE.upper(),
)
render_terminal_overview()

tab_active, tab_settled, tab_treasury, tab_gpu = st.tabs(
    ["Active Requests", "Settled", "Marketplace Treasury", "GPU Performance"]
)


@st.fragment(run_every=3)
def render_active() -> None:
    try:
        requests = _api_get("/apps", {"status": "open"})
    except httpx.HTTPError as e:
        st.error(f"Marketplace unreachable: {e}")
        return
    if not requests:
        st.info("No open requests. Publish one in the sidebar to get started.")
        return
    for req in requests:
        with st.container(border=True):
            cols = st.columns([3, 1])
            with cols[0]:
                loan_str = f"${Decimal(req['loan_amount']):,}"
                st.subheader(f"Request {req['id'][:8]}")
                st.write(
                    f"FICO **{req['applicant_fico']}** | Loan **{loan_str}** "
                    f"| {req['vehicle_type']} | {req['term_months']} mo "
                    f"| {req['state']} | reserve {req['dealer_reserve_bps']} bps"
                )
                st.caption(f"Dealer {req['dealer_id']} · {req['created_at']}")
            try:
                bids = _api_get(f"/apps/{req['id']}/bids")
            except httpx.HTTPError:
                bids = []
            with cols[1]:
                st.metric("Bids", len(bids))

            for bid in bids:
                with st.container(border=True):
                    bcols = st.columns([3, 2, 1])
                    apr_pct = bid["apr_bps"] / 100
                    max_amt = Decimal(bid["max_amount_usdc"])
                    cash_down = Decimal(bid.get("cash_down_required_usdc", "0"))
                    reserve_bps = bid.get("dealer_reserve_bps", 0)
                    ltv_pct = bid.get("max_ltv_bps", 10000) / 100
                    confidence = bid.get("confidence", 0.9)
                    stips = bid.get("stipulations") or []

                    with bcols[0]:
                        lender_label = bid.get("lender_name") or bid["lender_id"]
                        st.write(f"**{lender_label}**  ·  {bid.get('decision', 'approve')}")
                        st.write(
                            f"APR **{apr_pct:.2f}%** · term **{bid['term_months']}mo** "
                            f"· max **${max_amt:,.0f}** · LTV {ltv_pct:.0f}%"
                        )
                        cash_part = (
                            f" · cash down **${cash_down:,.0f}**" if cash_down > 0 else ""
                        )
                        st.write(
                            f"Dealer reserve **{reserve_bps}bps**"
                            f" · confidence {confidence:.2f}"
                            f"{cash_part}"
                        )
                        if stips:
                            with st.expander(f"Stipulations ({len(stips)})", expanded=False):
                                for s in stips:
                                    st.write(f"• {s}")
                        with st.expander("Rationale", expanded=False):
                            st.write(bid["rationale"])
                    with bcols[1]:
                        tx = bid.get("insertion_fee_tx_hash") or ""
                        if tx:
                            st.markdown(f"Fee tx: {_tx_link(tx)}", unsafe_allow_html=False)
                        else:
                            st.caption("Fee: pending")
                        st.caption(f"status: {bid['status']}")
                    with bcols[2]:
                        if bid["status"] == "open":
                            if st.button("Accept", key=f"acc-{bid['id']}"):
                                try:
                                    res = _api_post(
                                        f"/apps/{req['id']}/accept",
                                        {"bid_id": bid["id"]},
                                    )
                                    splits = res["settlement"]["splits"]
                                    st.success(
                                        f"Accepted! win premium "
                                        f"${Decimal(splits['win_premium_usdc']):.2f}"
                                    )
                                except httpx.HTTPError as e:
                                    st.error(f"Accept failed: {e}")


@st.fragment(run_every=3)
def render_settled() -> None:
    try:
        requests = _api_get("/apps", {"status": "closed"})
    except httpx.HTTPError as e:
        st.error(f"Marketplace unreachable: {e}")
        return
    if not requests:
        st.info("No settled requests yet.")
        return
    for req in requests:
        try:
            settlement = _api_get(f"/apps/{req['id']}/settlement")
        except httpx.HTTPError:
            continue
        with st.container(border=True):
            st.subheader(f"Request {req['id'][:8]}")
            st.write(
                f"FICO {req['applicant_fico']} | "
                f"Loan ${Decimal(req['loan_amount']):,} | "
                f"{req['vehicle_type']} | {req['term_months']} mo"
            )
            cols = st.columns(3)
            cols[0].markdown(f"**Dealer (70%)**\n{_tx_link(settlement['dealer_payout_tx'])}")
            cols[1].markdown(
                f"**Marketplace (25%)**\n{_tx_link(settlement['marketplace_cut_tx'])}"
            )
            cols[2].markdown(f"**Reserve (5%)**\n{_tx_link(settlement['reserve_tx'])}")
            st.caption(f"settled {settlement['created_at']}")


@st.fragment(run_every=3)
def render_treasury() -> None:
    try:
        stats = _api_get("/treasury")
    except httpx.HTTPError as e:
        st.error(f"Marketplace unreachable: {e}")
        return
    cols = st.columns(4)
    cols[0].metric("Total bids", stats["total_bids"])
    cols[1].metric("Total settlements", stats["total_settlements"])
    cols[2].metric(
        "Insertion fees collected",
        f"${Decimal(stats['insertion_fees_collected_usdc']):.2f}",
    )
    cols[3].metric(
        "Marketplace cut",
        f"${Decimal(stats['marketplace_cut_usdc']):.2f}",
    )
    st.markdown("---")
    cols2 = st.columns(3)
    cols2[0].metric(
        "Win-premium total",
        f"${Decimal(stats['win_premium_total_usdc']):.2f}",
    )
    cols2[1].metric(
        "Dealer payouts (70%)",
        f"${Decimal(stats['dealer_payouts_usdc']):.2f}",
    )
    cols2[2].metric(
        "Reserve payouts (5%)",
        f"${Decimal(stats['reserve_payouts_usdc']):.2f}",
    )
    st.caption(f"Marketplace wallet: `{stats['marketplace_wallet_id'] or 'unset'}`")


@st.fragment(run_every=2)
def render_gpu_performance() -> None:
    try:
        metrics = _api_get("/gpu/metrics")
    except httpx.HTTPError as e:
        st.error(f"GPU metrics unavailable: {e}")
        return

    if not metrics.get("available"):
        st.warning("GPU metrics not available on this host yet.")
        st.caption("If running on droplet, ensure amdsmi is installed and accessible.")
        return

    util = float(metrics.get("util_pct", 0.0))
    mem_used = float(metrics.get("mem_used_gb", 0.0))
    mem_total = float(metrics.get("mem_total_gb", 0.0))
    power = float(metrics.get("power_w", 0.0))
    temp = float(metrics.get("temp_c", 0.0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GPU Utilization", f"{util:.0f}%")
    c2.metric("VRAM", f"{mem_used:.1f} / {mem_total:.0f} GB")
    c3.metric("Power", f"{power:.0f} W")
    c4.metric("Temp", f"{temp:.0f} C")

    hist = st.session_state.setdefault(
        "gpu_perf_hist",
        {"t": [], "util": [], "power": [], "temp": [], "mem_used": []},
    )
    ts = metrics.get("sampled_at", "")
    hist["t"].append(ts)
    hist["util"].append(util)
    hist["power"].append(power)
    hist["temp"].append(temp)
    hist["mem_used"].append(mem_used)
    for k in ("t", "util", "power", "temp", "mem_used"):
        hist[k] = hist[k][-180:]

    chart_rows = [
        {"sample": t, "util_pct": u, "power_w": p, "temp_c": tc, "mem_used_gb": m}
        for t, u, p, tc, m in zip(
            hist["t"], hist["util"], hist["power"], hist["temp"], hist["mem_used"], strict=False
        )
    ]
    if chart_rows:
        st.line_chart(
            chart_rows,
            x="sample",
            y=["util_pct", "power_w", "temp_c", "mem_used_gb"],
            height=280,
        )
    st.caption(
        "Live GPU telemetry from `/gpu/metrics` (2s refresh). Useful during burst submission demos."
    )


with tab_active:
    render_active()

with tab_settled:
    render_settled()

with tab_treasury:
    render_treasury()

with tab_gpu:
    render_gpu_performance()
