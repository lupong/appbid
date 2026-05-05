"""Read-only ledger inspector — bid requests, bids, settlements with on-chain links.

Run with:
    streamlit run ui/ledger_view.py
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
import streamlit as st

from shared.config import get_settings

st.set_page_config(page_title="Credit App+ Ledger", layout="wide")

settings = get_settings()
MKT = settings.marketplace_url
BASESCAN_TX = "https://sepolia.basescan.org/tx"


def _api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    r = httpx.get(f"{MKT}{path}", params=params, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _tx(tx_hash: str) -> str:
    if not tx_hash:
        return "—"
    return f"[{tx_hash[:10]}…]({BASESCAN_TX}/{tx_hash})"


st.title("Credit App+ Ledger")
st.caption(f"Marketplace: `{MKT}`")

status_filter = st.selectbox(
    "Filter by status", ["all", "open", "closed", "funded_pending"], index=0
)

try:
    params = None if status_filter == "all" else {"status": status_filter}
    requests = _api_get("/apps", params)
except httpx.HTTPError as e:
    st.error(f"Marketplace unreachable: {e}")
    st.stop()

if not requests:
    st.info("No bid requests yet.")
    st.stop()

for req in requests:
    with st.expander(f"Request {req['id'][:8]}  ·  {req['status']}", expanded=False):
        st.write(
            f"Dealer **{req['dealer_id']}** · FICO **{req['applicant_fico']}** · "
            f"Loan **${Decimal(req['loan_amount']):,}** · "
            f"{req['vehicle_type']} · {req['term_months']} mo · "
            f"{req['state']} · reserve {req['dealer_reserve_bps']} bps"
        )
        st.caption(f"created {req['created_at']}  ·  id `{req['id']}`")

        bids = _api_get(f"/apps/{req['id']}/bids")
        if bids:
            st.markdown("**Bids (ranked):**")
            for b in bids:
                apr = b["apr_bps"] / 100
                stips = b.get("stipulations") or []
                stips_part = (
                    f" · {len(stips)} stip{'s' if len(stips) != 1 else ''}"
                    if stips else ""
                )
                st.markdown(
                    f"- **{b['lender_id']}** · APR {apr:.2f}% · "
                    f"term {b['term_months']}mo · "
                    f"max ${Decimal(b['max_amount_usdc']):,} · "
                    f"reserve {b.get('dealer_reserve_bps', 0)}bps"
                    f"{stips_part} · "
                    f"status `{b['status']}` · "
                    f"fee {_tx(b.get('insertion_fee_tx_hash') or '')}"
                )
                st.caption(b["rationale"])
        else:
            st.caption("no bids")

        if req["status"] == "closed":
            try:
                s = _api_get(f"/apps/{req['id']}/settlement")
            except httpx.HTTPError:
                s = None
            if s:
                st.markdown(
                    f"**Settlement** · "
                    f"dealer (70%) {_tx(s['dealer_payout_tx'])} · "
                    f"marketplace (25%) {_tx(s['marketplace_cut_tx'])} · "
                    f"reserve (5%) {_tx(s['reserve_tx'])}"
                )
                st.caption(f"settled {s['created_at']}")
