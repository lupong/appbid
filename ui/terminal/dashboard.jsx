// dashboard.jsx — hero screen

const { useState: dashUseState, useEffect: dashUseEffect, useMemo: dashUseMemo } = React;

function Dashboard({ requests, treasury, ops, onRoute, onOpenRequest }) {
  const activeCount   = requests.filter(r => r.status === 'open').length;
  const settledCount  = requests.filter(r => r.status === 'settled').length;
  const totalBids     = requests.reduce((s, r) => s + (r.bids_count || 0), 0);
  const acceptanceRate = settledCount / Math.max(1, settledCount + requests.filter(r => r.status === 'expired').length);

  // Health checks
  const health = [
    { id: 'mp', label: 'Marketplace API',  status: 'operational', latency: 42,   uptime: 99.98 },
    { id: 'rn', label: 'Bid Runner',       status: 'operational', latency: 18,   uptime: 99.99 },
    { id: 'mo', label: 'Pricing Model',    status: 'operational', latency: 124,  uptime: 99.92, sub: ops.model_endpoint },
    { id: 'st', label: 'Settlement Stub',  status: 'simulated',   latency: 8,    uptime: 100.0 },
  ];

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Health row */}
      <section>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom: 10 }}>
          <div className="eyebrow">System Health</div>
          <span className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>
            Polled · {new Date().toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {health.map(h => (
            <div key={h.id} className="card" style={{ padding: 14, display:'flex', flexDirection:'column', gap: 8 }}>
              <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                <div style={{ fontSize: 12, color: 'var(--ink-700)', fontWeight: 500 }}>{h.label}</div>
                <span className={`pill ${h.status === 'simulated' ? 'pill-gold' : 'pill-success'}`}>
                  <span className={h.status === 'simulated' ? 'pill-dot' : 'live-dot'}></span>
                  {h.status === 'simulated' ? 'STUB' : 'LIVE'}
                </span>
              </div>
              <div style={{ display:'flex', alignItems:'baseline', gap: 12 }}>
                <span className="mono tabular" style={{ fontSize: 22, fontWeight: 500 }}>
                  {h.latency}<span style={{ fontSize: 11, color: 'var(--ink-500)', fontWeight: 400, marginLeft: 2 }}>ms</span>
                </span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>↑ {h.uptime.toFixed(2)}%</span>
              </div>
              {h.sub && <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{h.sub}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* KPI row */}
      <section style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr', gap: 12 }}>
        <KpiCardLarge
          eyebrow="Win Premium · 24h"
          value={`$${treasury.win_premium_total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          delta="+12.4% vs prev"
          deltaPositive={true}
          spark={[18, 22, 19, 25, 31, 28, 35, 32, 38, 42, 39, 44, 48]}
        />
        <KpiCard
          eyebrow="Active Requests"
          value={activeCount}
          sub={`${requests.length} total today`}
          accent="navy"
          icon="list"
        />
        <KpiCard
          eyebrow="Bids Received"
          value={totalBids}
          sub={`${(totalBids/Math.max(1,requests.length)).toFixed(1)} avg per RFQ`}
          accent="info"
          icon="gavel"
        />
        <KpiCard
          eyebrow="Acceptance Rate"
          value={`${(acceptanceRate * 100).toFixed(1)}%`}
          sub={`${settledCount} of ${settledCount + requests.filter(r=>r.status==='expired').length} closed`}
          accent="gold"
          icon="check"
        />
      </section>

      {/* Two-column main */}
      <section style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 16 }}>
        {/* Live activity */}
        <div className="card">
          <div className="card-hd">
            <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
              <span className="live-dot"></span>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Active Marketplace</h3>
              <span className="pill pill-neutral">{activeCount} OPEN · {settledCount} SETTLED</span>
            </div>
            <div style={{ display:'flex', gap: 6 }}>
              <button className="btn btn-sm" onClick={() => onRoute('requests')}>
                View all <Icon d={Icons.arrow_r} size={11}/>
              </button>
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Vehicle</th>
                  <th style={{ textAlign:'right' }}>Loan</th>
                  <th style={{ textAlign:'right' }}>FICO</th>
                  <th>State</th>
                  <th style={{ textAlign:'center' }}>Bids</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {requests.slice(0, 6).map(r => (
                  <tr key={r.id} style={{ cursor: 'pointer' }} onClick={() => onOpenRequest(r.id)}>
                    <td>
                      <div className="mono" style={{ fontWeight: 500 }}>{requestDisplayId(r)}</div>
                      <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{timeAgo(r.created)}</div>
                    </td>
                    <td>
                      <div>{r.vehicle_type}</div>
                      <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{r.term_months}mo · incentive {fmtUSD(r.incentive_usd, { decimals: 2, sign: true })}</div>
                    </td>
                    <td className="num" style={{ textAlign: 'right' }}>${r.loan_amount.toLocaleString()}</td>
                    <td className="num" style={{ textAlign: 'right', color: r.applicant_fico >= 740 ? 'var(--success-700)' : r.applicant_fico >= 670 ? 'var(--ink-700)' : 'var(--warning-700)' }}>
                      {r.applicant_fico}
                    </td>
                    <td className="mono" style={{ fontSize: 12 }}>{r.state}</td>
                    <td style={{ textAlign:'center' }}>
                      <BidCountBar count={r.bids_count}/>
                    </td>
                    <td><StatusPill status={r.status}/></td>
                    <td style={{ width: 36 }}>
                      <span style={{ color: 'var(--ink-400)' }}><Icon d={Icons.arrow_r} size={14}/></span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right column */}
        <div style={{ display:'flex', flexDirection:'column', gap: 16 }}>
          <DemoPathCard onRoute={onRoute}/>
          <TreasurySnapshot treasury={treasury}/>
        </div>
      </section>

      {/* Settled feed + lender leaderboard */}
      <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card">
          <div className="card-hd">
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Lender Leaderboard · 24h</h3>
            <span className="eyebrow">By win rate</span>
          </div>
          <div className="card-bd" style={{ paddingTop: 0 }}>
            <Leaderboard requests={requests}/>
          </div>
        </div>

        <div className="card">
          <div className="card-hd">
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Recent Settlements</h3>
            <button className="btn btn-sm btn-ghost" onClick={() => onRoute('ledger')}>
              Ledger <Icon d={Icons.arrow_r} size={11}/>
            </button>
          </div>
          <div>
            {requests.filter((r) => r.status === 'settled' && r.settlement).slice(0, 4).map((r, idx) => (
              <div key={r.id} style={{ padding: '12px 16px', borderBottom: idx < 3 ? '1px solid var(--ink-100)' : 'none', display:'flex', alignItems:'center', gap: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: 4, background: 'var(--success-50)', color: 'var(--success-700)', display:'flex', alignItems:'center', justifyContent:'center' }}>
                  <Icon d={Icons.check} size={16}/>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
                    <span className="mono" style={{ fontWeight: 500 }}>{requestDisplayId(r)}</span>
                    <span className="pill pill-neutral" style={{ fontSize: 9.5 }}>{r.vehicle_type}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--ink-500)', marginTop: 2 }}>
                    {r.settlement && shortHash(r.settlement.tx_dealer)} · {timeAgo(r.created)}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="mono tabular" style={{ fontWeight: 500 }}>+{fmtUSD(r.settlement.win_premium_usdc, { decimals: 2 })}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>premium</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function KpiCardLarge({ eyebrow, value, delta, deltaPositive, spark }) {
  // tiny sparkline
  const max = Math.max(...spark);
  const min = Math.min(...spark);
  const w = 200, h = 44;
  const pts = spark.map((v, i) => {
    const x = (i / (spark.length - 1)) * w;
    const y = h - ((v - min) / Math.max(1, max - min)) * h;
    return `${x},${y}`;
  }).join(' ');
  return (
    <div className="card" style={{ padding: 18, display:'flex', flexDirection:'column', gap: 10, background: 'linear-gradient(180deg, var(--paper), var(--ink-25))' }}>
      <div className="eyebrow">{eyebrow}</div>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', gap: 12 }}>
        <div>
          <div className="serif tabular" style={{ fontSize: 30, fontWeight: 500, letterSpacing: '-0.02em', color: 'var(--ink-950)' }}>
            {value}
          </div>
          <div style={{ display:'flex', alignItems:'center', gap: 6, marginTop: 4 }}>
            <span className="pill pill-success" style={{ height: 18, fontSize: 9.5 }}>
              <Icon d={Icons.trend} size={10}/>{delta}
            </span>
          </div>
        </div>
        <svg width={w} height={h} style={{ flexShrink: 0 }}>
          <defs>
            <linearGradient id="sparkfill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--gold-400)" stopOpacity="0.30"/>
              <stop offset="100%" stopColor="var(--gold-400)" stopOpacity="0"/>
            </linearGradient>
          </defs>
          <polygon points={`0,${h} ${pts} ${w},${h}`} fill="url(#sparkfill)"/>
          <polyline points={pts} fill="none" stroke="var(--gold-600)" strokeWidth="1.5"/>
        </svg>
      </div>
    </div>
  );
}

function KpiCard({ eyebrow, value, sub, accent = 'navy', icon }) {
  const accentColors = {
    navy:  { bg: 'var(--navy-50)',  fg: 'var(--navy-800)' },
    gold:  { bg: 'var(--gold-50)',  fg: 'var(--gold-700)' },
    info:  { bg: 'var(--info-50)',  fg: 'var(--info-700)' },
  };
  const c = accentColors[accent];
  return (
    <div className="card" style={{ padding: 18, display:'flex', flexDirection:'column', gap: 8 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div className="eyebrow">{eyebrow}</div>
        <div style={{ width: 24, height: 24, borderRadius: 4, background: c.bg, color: c.fg, display:'flex', alignItems:'center', justifyContent:'center' }}>
          <Icon d={Icons[icon]} size={13}/>
        </div>
      </div>
      <div className="serif tabular" style={{ fontSize: 30, fontWeight: 500, letterSpacing: '-0.02em' }}>{value}</div>
      <div className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>{sub}</div>
    </div>
  );
}

function BidCountBar({ count }) {
  const max = 8;
  return (
    <div style={{ display:'inline-flex', alignItems:'center', gap: 6 }}>
      <span className="mono tabular" style={{ minWidth: 14, textAlign: 'right', fontSize: 12, fontWeight: 500 }}>{count}</span>
      <div style={{ display:'flex', gap: 1.5 }}>
        {Array.from({ length: max }).map((_, i) => (
          <div key={i} style={{
            width: 3, height: 12,
            background: i < count ? 'var(--navy-700)' : 'var(--ink-150)',
            borderRadius: 1
          }}/>
        ))}
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    open:     { cls: 'pill-success', label: 'OPEN', dot: 'live-dot' },
    settled:  { cls: 'pill-navy',    label: 'SETTLED', dot: 'pill-dot' },
    expired:  { cls: 'pill-neutral', label: 'EXPIRED', dot: 'pill-dot' },
    accepted: { cls: 'pill-gold',    label: 'ACCEPTED', dot: 'pill-dot' },
    lost:     { cls: 'pill-neutral', label: 'LOST', dot: 'pill-dot' },
  };
  const c = map[status] || map.open;
  return (
    <span className={`pill ${c.cls}`}>
      <span className={c.dot}></span>{c.label}
    </span>
  );
}

function DemoPathCard({ onRoute }) {
  const steps = [
    { id: 'new',        label: 'Publish request',   sub: 'PII-free RFQ'      },
    { id: 'requests',   label: 'Watch bids stream', sub: 'Lender competition' },
    { id: 'settlement', label: 'Accept top bid',    sub: 'Trigger settlement' },
    { id: 'ledger',     label: 'Inspect treasury',  sub: 'Splits & tx hashes' },
  ];
  return (
    <div className="card" style={{ background: 'linear-gradient(180deg, var(--navy-900), var(--navy-950))', color: '#fff', borderColor: 'var(--navy-900)' }}>
      <div style={{ padding: 18, display:'flex', flexDirection:'column', gap: 14 }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <span className="eyebrow" style={{ color: 'var(--gold-300)' }}>Recommended Demo</span>
          <span className="pill pill-gold" style={{ background: 'rgba(202,138,4,0.18)', color: 'var(--gold-300)', borderColor: 'rgba(202,138,4,0.4)' }}>
            <Icon d={Icons.zap} size={10}/>4 STEPS
          </span>
        </div>
        <h3 className="serif" style={{ margin: 0, fontSize: 19, fontWeight: 500, letterSpacing: '-0.01em', textWrap: 'pretty' }}>
          Publish · Compete · Settle · Reconcile
        </h3>
        <div style={{ display:'flex', flexDirection:'column', gap: 6 }}>
          {steps.map((s, i) => (
            <button key={s.id} onClick={() => onRoute(s.id)}
              style={{ display:'flex', alignItems:'center', gap: 12, padding: '10px 12px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 4, color: '#fff', cursor: 'pointer', textAlign: 'left' }}>
              <span className="mono" style={{ width: 18, height: 18, borderRadius: 999, background: 'var(--gold-500)', color: 'var(--ink-950)', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 10, fontWeight: 600 }}>{i + 1}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12.5, fontWeight: 500 }}>{s.label}</div>
                <div className="mono" style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.55)' }}>{s.sub}</div>
              </div>
              <Icon d={Icons.arrow_r} size={13}/>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function TreasurySnapshot({ treasury }) {
  const items = [
    { label: 'Marketplace cut',  value: treasury.marketplace_total, color: 'var(--navy-700)'  },
    { label: 'Dealer share',     value: treasury.dealer_total,      color: 'var(--gold-600)'  },
    { label: 'Reserve',          value: treasury.reserve_total,     color: 'var(--ink-500)'   },
  ];
  const total = items.reduce((s, i) => s + i.value, 0);
  return (
    <div className="card">
      <div className="card-hd">
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Treasury Snapshot</h3>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>USDC</span>
      </div>
      <div className="card-bd" style={{ display:'flex', flexDirection:'column', gap: 14 }}>
        {/* Stacked bar */}
        <div style={{ display:'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: 'var(--ink-100)' }}>
          {items.map((i, idx) => (
            <div key={idx} style={{ width: `${(i.value/total)*100}%`, background: i.color }}/>
          ))}
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap: 8 }}>
          {items.map((i, idx) => (
            <div key={idx} style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
              <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: i.color }}></span>
                <span style={{ fontSize: 12.5, color: 'var(--ink-700)' }}>{i.label}</span>
              </div>
              <span className="mono tabular" style={{ fontWeight: 500 }}>{fmtUSD(i.value, { decimals: 2 })}</span>
            </div>
          ))}
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', paddingTop: 8, borderTop: '1px solid var(--ink-100)' }}>
            <span style={{ fontSize: 11, color: 'var(--ink-500)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Insertion fees</span>
            <span className="mono tabular">{fmtUSD(treasury.insertion_fees, { decimals: 2 })}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Leaderboard({ requests }) {
  // tally wins per lender
  const wins = {};
  for (const r of requests) {
    if (r.status === 'settled' && r.accepted_bid_id && r.winner_lender_id) {
      wins[r.winner_lender_id] = (wins[r.winner_lender_id] || 0) + r.settlement.win_premium_usdc;
    }
  }
  // fake some leaderboard data
  const board = LENDERS.slice(0, 6).map((l, i) => ({
    lender: l,
    wins: [4, 3, 3, 2, 1, 1][i],
    bids: [9, 8, 7, 6, 5, 4][i],
    avgApr: [4.92, 5.18, 5.34, 5.61, 5.89, 6.12][i],
    revenue: [1247, 982, 871, 612, 388, 291][i],
  }));
  return (
    <div style={{ display:'flex', flexDirection:'column' }}>
      {board.map((row, i) => {
        const winRate = (row.wins / row.bids) * 100;
        return (
          <div key={row.lender.id} style={{ display:'flex', alignItems:'center', gap: 12, padding: '10px 0', borderBottom: i < board.length - 1 ? '1px solid var(--ink-100)' : 'none' }}>
            <span className="mono" style={{ width: 16, color: 'var(--ink-500)', fontSize: 11 }}>{String(i + 1).padStart(2, '0')}</span>
            <div style={{ width: 26, height: 26, borderRadius: 4, background: row.lender.avatar, color: '#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 11, fontFamily: 'var(--ff-serif)', fontWeight: 600 }}>
              {row.lender.name[0]}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display:'flex', alignItems:'center', gap: 6 }}>
                <span style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap' }}>{row.lender.name}</span>
                <span className="pill pill-neutral" style={{ height: 16, fontSize: 9, padding: '0 5px' }}>{row.lender.tier}</span>
              </div>
              <div style={{ display:'flex', alignItems:'center', gap: 8, marginTop: 2 }}>
                <div style={{ flex: 1, height: 4, background: 'var(--ink-100)', borderRadius: 2, overflow:'hidden' }}>
                  <div style={{ width: `${winRate}%`, height: '100%', background: 'linear-gradient(90deg, var(--gold-500), var(--gold-600))' }}/>
                </div>
                <span className="mono tabular" style={{ fontSize: 10.5, color: 'var(--ink-500)', minWidth: 36, textAlign: 'right' }}>{winRate.toFixed(0)}%</span>
              </div>
            </div>
            <div style={{ textAlign:'right' }}>
              <div className="mono tabular" style={{ fontSize: 12, fontWeight: 500 }}>${row.revenue}</div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--ink-500)' }}>{row.wins}/{row.bids} wins</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

Object.assign(window, { Dashboard, KpiCard, BidCountBar, StatusPill });
