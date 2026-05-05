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
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

from shared.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Credit App+ Dealer", layout="wide")

settings = get_settings()
MKT = settings.marketplace_url
BASESCAN_TX = "https://sepolia.basescan.org/tx"


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


# ============= Sidebar: publish =============
with st.sidebar:
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
st.title("Credit App+ Dealer")

tab_active, tab_settled, tab_treasury = st.tabs(
    ["Active Requests", "Settled", "Marketplace Treasury"]
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
                        st.write(f"**{bid['lender_id']}**  ·  {bid.get('decision', 'approve')}")
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


with tab_active:
    render_active()

with tab_settled:
    render_settled()

with tab_treasury:
    render_treasury()
