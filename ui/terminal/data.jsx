// data.jsx — mock data + helpers for AppBid Terminal

const LENDERS = [
  { id: 'LND-AURUM',   name: 'Aurum Capital',        type: 'Bank',         tier: 'A+', avatar: '#0f1f3d' },
  { id: 'LND-MERIDIAN', name: 'Meridian Auto Finance', type: 'Captive',     tier: 'A',  avatar: '#1e3a8a' },
  { id: 'LND-PRIME',   name: 'PrimeWest Credit',      type: 'Credit Union', tier: 'A',  avatar: '#14305c' },
  { id: 'LND-NORTH',   name: 'NorthBridge Lending',   type: 'Bank',         tier: 'A-', avatar: '#2d4ba0' },
  { id: 'LND-VAULT',   name: 'Vault Auto Trust',      type: 'Fintech',     tier: 'B+', avatar: '#3b5fb8' },
  { id: 'LND-IRIS',    name: 'Iris Lending Group',    type: 'Fintech',     tier: 'B+', avatar: '#4d5260' },
  { id: 'LND-OAKMNT',  name: 'Oakmont Federal',       type: 'Credit Union', tier: 'A-', avatar: '#22252c' },
  { id: 'LND-CRWN',    name: 'Crown Origination Co.', type: 'Bank',         tier: 'A',  avatar: '#0a1628' },
];

const STATES = ['CA','TX','NY','FL','IL','WA','PA','OH','GA','NC','MI','VA','NJ','AZ','MA'];

function rand(min, max) { return Math.random() * (max - min) + min; }
function randInt(min, max) { return Math.floor(rand(min, max + 1)); }
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function txHash() {
  const chars = '0123456789abcdef';
  let s = '0x';
  for (let i = 0; i < 64; i++) s += chars[Math.floor(Math.random() * 16)];
  return s;
}
function reqId() {
  const n = String(randInt(1000, 9999));
  return `RFQ-${n}`;
}
function shortHash(h) { return h.slice(0, 10) + '…' + h.slice(-6); }
function fmtUSD(n, opts = {}) {
  const { decimals = 0, sign = false } = opts;
  const num = Number(n);
  const abs = Math.abs(num);
  const s = abs.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const prefix = num < 0 ? '-' : (sign && num > 0 ? '+' : '');
  return `${prefix}$${s}`;
}
function fmtPct(n, decimals = 2) {
  return Number(n).toFixed(decimals) + '%';
}
function fmtBps(n) {
  return Math.round(n) + ' bps';
}

// Demo seed: pre-built historical requests + bids
const SEED_REQUESTS = [
  {
    id: 'RFQ-7421',
    dealer_id: 'DLR-104',
    applicant_fico: 742,
    loan_amount: 38500,
    vehicle_type: 'New SUV',
    term_months: 60,
    state: 'CA',
    dealer_reserve_bps: 175,
    status: 'settled',
    created: '2026-05-07T13:42:11Z',
    bids_count: 7,
    accepted_bid_id: 'BID-9081',
    settlement: {
      win_premium_usdc: 412.50,
      dealer_usdc: 330.00,
      marketplace_usdc: 61.88,
      reserve_usdc: 20.62,
      tx_dealer:      txHash(),
      tx_marketplace: txHash(),
      tx_reserve:     txHash(),
      mode: 'demo',
    },
  },
  {
    id: 'RFQ-7418',
    dealer_id: 'DLR-031',
    applicant_fico: 689,
    loan_amount: 24200,
    vehicle_type: 'Used Sedan',
    term_months: 48,
    state: 'TX',
    dealer_reserve_bps: 200,
    status: 'open',
    created: '2026-05-07T13:36:02Z',
    bids_count: 4,
    accepted_bid_id: null,
  },
  {
    id: 'RFQ-7414',
    dealer_id: 'DLR-218',
    applicant_fico: 805,
    loan_amount: 62000,
    vehicle_type: 'New Truck',
    term_months: 72,
    state: 'NY',
    dealer_reserve_bps: 150,
    status: 'settled',
    created: '2026-05-07T12:58:44Z',
    bids_count: 8,
    accepted_bid_id: 'BID-9076',
    settlement: {
      win_premium_usdc: 595.20,
      dealer_usdc: 476.16,
      marketplace_usdc: 89.28,
      reserve_usdc: 29.76,
      tx_dealer:      txHash(),
      tx_marketplace: txHash(),
      tx_reserve:     txHash(),
      mode: 'demo',
    },
  },
  {
    id: 'RFQ-7410',
    dealer_id: 'DLR-104',
    applicant_fico: 712,
    loan_amount: 19800,
    vehicle_type: 'Used SUV',
    term_months: 60,
    state: 'FL',
    dealer_reserve_bps: 225,
    status: 'settled',
    created: '2026-05-07T12:14:30Z',
    bids_count: 5,
    accepted_bid_id: 'BID-9069',
    settlement: {
      win_premium_usdc: 287.10,
      dealer_usdc: 229.68,
      marketplace_usdc: 43.07,
      reserve_usdc: 14.36,
      tx_dealer:      txHash(),
      tx_marketplace: txHash(),
      tx_reserve:     txHash(),
      mode: 'demo',
    },
  },
  {
    id: 'RFQ-7402',
    dealer_id: 'DLR-077',
    applicant_fico: 658,
    loan_amount: 15400,
    vehicle_type: 'Used Sedan',
    term_months: 48,
    state: 'IL',
    dealer_reserve_bps: 250,
    status: 'expired',
    created: '2026-05-07T10:42:08Z',
    bids_count: 2,
    accepted_bid_id: null,
  },
  {
    id: 'RFQ-7398',
    dealer_id: 'DLR-156',
    applicant_fico: 776,
    loan_amount: 47300,
    vehicle_type: 'New SUV',
    term_months: 60,
    state: 'WA',
    dealer_reserve_bps: 180,
    status: 'settled',
    created: '2026-05-07T09:31:50Z',
    bids_count: 6,
    accepted_bid_id: 'BID-9054',
    settlement: {
      win_premium_usdc: 521.30,
      dealer_usdc: 417.04,
      marketplace_usdc: 78.20,
      reserve_usdc: 26.06,
      tx_dealer:      txHash(),
      tx_marketplace: txHash(),
      tx_reserve:     txHash(),
      mode: 'demo',
    },
  },
];

// Realistic bid generator for a given request
function makeBid(request, lender, idx) {
  const ficoBoost  = (request.applicant_fico - 700) / 100; // +/- adjustment
  const baseApr    = 6.20 - ficoBoost * 0.65 + rand(-0.20, 0.40);
  const apr        = Math.max(3.49, +(baseApr + idx * rand(0.05, 0.18)).toFixed(2));
  const reserveBps = Math.max(50, Math.round(request.dealer_reserve_bps - rand(-20, 60)));
  const maxAmount  = request.loan_amount + randInt(0, 2000);
  const term       = request.term_months + (Math.random() < 0.2 ? pick([-12, 12]) : 0);
  const stips      = Math.random() < 0.55 ? [] :
                     pick([
                       ['Proof of income'],
                       ['VSI required'],
                       ['Proof of income','Residence verification'],
                       ['LTV ≤ 130%'],
                     ]);
  const confidence = +(rand(0.78, 0.98) - idx * 0.02).toFixed(2);
  return {
    id: 'BID-' + randInt(9100, 9999),
    lender,
    apr,
    term_months: term,
    max_amount: maxAmount,
    reserve_bps: reserveBps,
    stipulations: stips,
    confidence,
    status: 'open',
    submitted: Date.now(),
  };
}

// Compute treasury aggregate from settled requests
function computeTreasury(requests) {
  let totalSettlements = 0;
  let totalBids = 0;
  let winPremium = 0;
  let mkt = 0, dealer = 0, reserve = 0;
  let insertionFees = 0;
  for (const r of requests) {
    totalBids += r.bids_count || 0;
    insertionFees += 0.50; // $0.50 per request demo
    if (r.status === 'settled' && r.settlement) {
      totalSettlements++;
      winPremium += r.settlement.win_premium_usdc;
      mkt        += r.settlement.marketplace_usdc;
      dealer     += r.settlement.dealer_usdc;
      reserve    += r.settlement.reserve_usdc;
    }
  }
  return {
    total_bids: totalBids,
    total_settlements: totalSettlements,
    win_premium_total: winPremium,
    marketplace_total: mkt,
    dealer_total: dealer,
    reserve_total: reserve,
    insertion_fees: insertionFees,
  };
}

// Time-ago
function timeAgo(iso) {
  const d = typeof iso === 'string' ? new Date(iso) : new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return s + 's ago';
  const m = Math.floor(s / 60);
  if (m < 60) return m + 'm ago';
  const h = Math.floor(m / 60);
  if (h < 24) return h + 'h ago';
  return Math.floor(h / 24) + 'd ago';
}

Object.assign(window, {
  LENDERS, STATES,
  SEED_REQUESTS,
  rand, randInt, pick, txHash, shortHash, reqId,
  fmtUSD, fmtPct, fmtBps,
  makeBid, computeTreasury, timeAgo,
});
