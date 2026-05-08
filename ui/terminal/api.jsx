// api.jsx — live backend bridge for prototype shell

const API_BASE = window.APPBID_API_BASE || '';

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

async function readJson(path, init) {
  const res = await fetch(apiUrl(path), init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_e) {
      // ignore parse fallback
    }
    throw new Error(detail);
  }
  return res.json();
}

function toNum(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function bpsToUsd(amountUsd, bps) {
  return toNum(amountUsd) * (toNum(bps) / 10000);
}

function usdToBps(amountUsd, incentiveUsd) {
  const amt = toNum(amountUsd);
  if (amt <= 0) return 0;
  return Math.round((toNum(incentiveUsd) / amt) * 10000);
}

function mapVehicleForApi(v) {
  const s = String(v || '').toLowerCase();
  if (s.includes('ev')) return 'ev';
  if (s.includes('used')) return 'used';
  return 'new';
}

function toUiVehicle(v) {
  if (v === 'ev') return 'EV';
  if (v === 'used') return 'Used Vehicle';
  return 'New Vehicle';
}

function toUiStatus(v) {
  if (v === 'closed') return 'settled';
  return v;
}

function lenderById(lenderId) {
  const lenderNameById = {
    'prime-bank': 'STCU Retail Auto',
    'mid-market': 'Unitus Community CU',
    'subprime': 'Exeter Finance',
    'used-only-cu': 'Family Savings CU',
    'ev-captive': 'Crouse Federal Credit Union',
  };
  const known = (window.LENDERS || []).find((l) => l.id === lenderId);
  if (known) return known;
  return {
    id: lenderId,
    name: lenderNameById[lenderId] || String(lenderId || '').split('_').join(' '),
    type: 'Lender',
    tier: 'A',
    avatar: '#1e3a8a',
  };
}

function mapRequest(req) {
  const incentiveBps = toNum(req.dealer_reserve_bps);
  const loanAmount = toNum(req.loan_amount);
  return {
    id: req.id,
    display_id: '',
    dealer_id: req.dealer_id,
    applicant_fico: req.applicant_fico,
    loan_amount: loanAmount,
    vehicle_type: toUiVehicle(req.vehicle_type),
    term_months: req.term_months,
    state: req.state,
    dealer_reserve_bps: incentiveBps,
    incentive_bps: incentiveBps,
    incentive_usd: bpsToUsd(loanAmount, incentiveBps),
    status: toUiStatus(req.status),
    created: req.created_at,
    bids_count: 0,
    accepted_bid_id: null,
  };
}

function mapBid(b) {
  const maxAmount = toNum(b.max_amount_usdc);
  const incentiveBps = toNum(b.dealer_reserve_bps);
  const maxLtvBps = toNum(b.max_ltv_bps, 10000);
  const lenderMeta = lenderById(b.lender_id);
  const lenderName = b.lender_name || lenderMeta.name;
  return {
    id: b.id,
    lender: { ...lenderMeta, name: lenderName },
    apr: toNum(b.apr_bps) / 100,
    term_months: b.term_months,
    max_amount: maxAmount,
    max_ltv_bps: maxLtvBps,
    max_ltv_pct: maxLtvBps / 100,
    reserve_bps: incentiveBps,
    incentive_bps: incentiveBps,
    incentive_usd: bpsToUsd(maxAmount, incentiveBps),
    stipulations: b.stipulations || [],
    confidence: toNum(b.confidence, 0.9),
    status: b.status,
    submitted: Date.parse(b.created_at || new Date().toISOString()),
  };
}

function mapTreasury(t) {
  return {
    total_bids: t.total_bids || 0,
    total_settlements: t.total_settlements || 0,
    insertion_fees: toNum(t.insertion_fees_collected_usdc),
    win_premium_total: toNum(t.win_premium_total_usdc),
    marketplace_total: toNum(t.marketplace_cut_usdc),
    dealer_total: toNum(t.dealer_payouts_usdc),
    reserve_total: toNum(t.reserve_payouts_usdc),
  };
}

async function listRequests(status) {
  const q = status ? `?status=${encodeURIComponent(status)}` : '';
  const rows = await readJson(`/apps${q}`);
  return rows.map(mapRequest);
}

async function listBids(requestId) {
  const rows = await readJson(`/apps/${requestId}/bids`);
  return rows.map(mapBid);
}

async function getSettlementDetail(requestId) {
  return readJson(`/apps/${requestId}/settlement/detail`);
}

async function getTreasury() {
  const t = await readJson('/treasury');
  return mapTreasury(t);
}

async function getGpuMetrics() {
  try {
    return await readJson('/gpu/metrics');
  } catch (_e) {
    return {
      available: false,
      sampled_at: new Date().toISOString(),
      util_pct: 0,
      mem_used_gb: 0,
      mem_total_gb: 0,
      power_w: 0,
      temp_c: 0,
    };
  }
}

async function createRequest(payload) {
  const loanAmount = toNum(payload.loan_amount);
  const incentiveBps =
    payload.dealer_incentive_usd != null
      ? usdToBps(loanAmount, payload.dealer_incentive_usd)
      : toNum(payload.dealer_reserve_bps);
  return readJson('/apps', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dealer_id: payload.dealer_id,
      applicant_fico: toNum(payload.applicant_fico),
      loan_amount: String(payload.loan_amount),
      vehicle_type: mapVehicleForApi(payload.vehicle_type),
      term_months: toNum(payload.term_months),
      state: String(payload.state || 'TX').toUpperCase(),
      dealer_reserve_bps: incentiveBps,
    }),
  });
}

async function acceptBid(requestId, bidId) {
  return readJson(`/apps/${requestId}/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bid_id: bidId }),
  });
}

async function hydrateState() {
  const [openReqs, closedReqs, treasury] = await Promise.all([
    listRequests('open'),
    listRequests('closed'),
    getTreasury(),
  ]);
  const requests = [...openReqs, ...closedReqs].sort(
    (a, b) => new Date(b.created) - new Date(a.created),
  );
  const oldestFirst = [...requests].sort(
    (a, b) => new Date(a.created) - new Date(b.created),
  );
  oldestFirst.forEach((req, idx) => {
    req.display_id = `RFB-${String(idx + 1).padStart(3, '0')}`;
  });
  const bidsByRequest = {};

  await Promise.all(
    requests.map(async (req) => {
      const bids = await listBids(req.id);
      bidsByRequest[req.id] = bids;
      req.bids_count = bids.length;
      const accepted = bids.find((b) => b.status === 'accepted');
      if (accepted) {
        req.accepted_bid_id = accepted.id;
      }
      if (req.status === 'settled') {
        try {
          const s = await getSettlementDetail(req.id);
          req.settlement = {
            win_premium_usdc: toNum(s.splits.win_premium_usdc),
            dealer_usdc: toNum(s.splits.dealer_usdc),
            marketplace_usdc: toNum(s.splits.marketplace_usdc),
            reserve_usdc: toNum(s.splits.reserve_usdc),
            tx_dealer: s.dealer_payout_tx,
            tx_marketplace: s.marketplace_cut_tx,
            tx_reserve: s.reserve_tx,
            mode: s.mode || 'stub',
          };
        } catch (_e) {
          // no settlement for this request yet
        }
      }
    }),
  );

  return { requests, bidsByRequest, treasury };
}

Object.assign(window, {
  bpsToUsd,
  usdToBps,
  requestDisplayId: (req) => req?.display_id || req?.id || '',
  Backend: {
    hydrateState,
    createRequest,
    acceptBid,
    getGpuMetrics,
    mapVehicleForApi,
  },
});
