// ledger.jsx — Treasury / Ledger view + Operations panel

const { useState: lUseState, useMemo: lUseMemo } = React;

function LedgerView({ requests, treasury, onOpenRequest }) {
  const [search, setSearch] = lUseState('');
  const [filter, setFilter] = lUseState('all');

  const settled = requests.filter(r => r.status === 'settled' && r.settlement);
  const filtered = settled.filter(r => {
    const q = search.trim().toLowerCase();
    if (filter === 'high' && r.settlement.win_premium_usdc < 400) return false;
    if (!q) return true;
    return requestDisplayId(r).toLowerCase().includes(q) ||
           r.id.toLowerCase().includes(q) ||
           r.dealer_id.toLowerCase().includes(q) ||
           r.vehicle_type.toLowerCase().includes(q);
  });

  const totalGross = settled.reduce((s, r) => s + r.settlement.win_premium_usdc, 0);

  return (
    <div style={{ padding: 24, display:'flex', flexDirection:'column', gap: 16 }}>
      {/* Top metrics */}
      <div style={{ display:'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12 }}>
        <BigStat label="Total Settlements" value={treasury.total_settlements} sub="all-time"/>
        <BigStat label="Total Bids"        value={treasury.total_bids}        sub="across RFQs"/>
        <BigStat label="Win Premium"   value={fmtUSD(totalGross, { decimals: 2 })} sub="gross USDC" highlight/>
        <BigStat label="Marketplace"   value={fmtUSD(treasury.marketplace_total, { decimals: 2 })} sub="15% take"/>
        <BigStat label="Dealer Share"  value={fmtUSD(treasury.dealer_total, { decimals: 2 })} sub="80% paid out"/>
        <BigStat label="Reserve Fund"  value={fmtUSD(treasury.reserve_total, { decimals: 2 })} sub="5% retained"/>
      </div>

      {/* Cumulative chart placeholder + breakdown */}
      <div style={{ display:'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        <div className="card">
          <div className="card-hd">
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Cumulative Win Premium · 24h</h3>
            <div style={{ display:'flex', gap: 6 }}>
              <button className="btn btn-sm">24H</button>
              <button className="btn btn-sm btn-ghost">7D</button>
              <button className="btn btn-sm btn-ghost">30D</button>
            </div>
          </div>
          <div className="card-bd"><CumChart settled={settled}/></div>
        </div>
        <div className="card">
          <div className="card-hd"><h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Fee Breakdown</h3></div>
          <div className="card-bd" style={{ display:'flex', flexDirection:'column', gap: 12 }}>
            <FeeRow label="Insertion fees collected" value={treasury.insertion_fees} note={`$0.50 × ${requests.length} RFQs`}/>
            <FeeRow label="Win premium · marketplace" value={treasury.marketplace_total} note="15% of gross"/>
            <FeeRow label="Reserve buffer growth" value={treasury.reserve_total} note="5% retained"/>
            <div style={{ paddingTop: 10, borderTop: '1px solid var(--ink-100)', display:'flex', justifyContent:'space-between', alignItems:'baseline' }}>
              <span className="eyebrow">Marketplace revenue</span>
              <span className="serif tabular" style={{ fontSize: 22, fontWeight: 500, color: 'var(--gold-700)' }}>
                {fmtUSD(treasury.marketplace_total + treasury.insertion_fees, { decimals: 2 })}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Settlement table */}
      <div className="card">
        <div className="card-hd">
          <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Settlement History</h3>
            <span className="pill pill-neutral">{filtered.length}</span>
          </div>
          <div style={{ display:'flex', gap: 6 }}>
            <div style={{ position:'relative' }}>
              <input className="input" placeholder="Search RFQ, dealer, vehicle…"
                value={search} onChange={e => setSearch(e.target.value)}
                style={{ width: 240, height: 28, paddingLeft: 28, fontSize: 12, background: 'var(--ink-25)' }}/>
              <span style={{ position:'absolute', left: 8, top: 7, color:'var(--ink-400)' }}><Icon d={Icons.search} size={12}/></span>
            </div>
            <button className={`btn btn-sm ${filter === 'high' ? 'btn-primary' : ''}`} onClick={() => setFilter(f => f === 'high' ? 'all' : 'high')}>
              <Icon d={Icons.filter} size={11}/>High premium
            </button>
            <button className="btn btn-sm"><Icon d={Icons.download} size={11}/>CSV</button>
          </div>
        </div>
        <div style={{ overflowX:'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Request</th>
                <th>Vehicle</th>
                <th>Dealer</th>
                <th style={{ textAlign:'right' }}>Premium</th>
                <th style={{ textAlign:'right' }}>Dealer</th>
                <th style={{ textAlign:'right' }}>Marketplace</th>
                <th style={{ textAlign:'right' }}>Reserve</th>
                <th>Tx Dealer</th>
                <th>Mode</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.id} onClick={() => onOpenRequest(r.id)} style={{ cursor: 'pointer' }}>
                  <td>
                    <div className="mono" style={{ fontWeight: 500 }}>{requestDisplayId(r)}</div>
                    <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{timeAgo(r.created)}</div>
                  </td>
                  <td>{r.vehicle_type}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{r.dealer_id}</td>
                  <td className="num" style={{ textAlign:'right', color:'var(--gold-700)', fontWeight: 500 }}>{fmtUSD(r.settlement.win_premium_usdc, { decimals: 2 })}</td>
                  <td className="num" style={{ textAlign:'right' }}>{fmtUSD(r.settlement.dealer_usdc, { decimals: 2 })}</td>
                  <td className="num" style={{ textAlign:'right' }}>{fmtUSD(r.settlement.marketplace_usdc, { decimals: 2 })}</td>
                  <td className="num" style={{ textAlign:'right' }}>{fmtUSD(r.settlement.reserve_usdc, { decimals: 2 })}</td>
                  <td className="mono" style={{ fontSize: 11, color: 'var(--info-700)' }}>{shortHash(r.settlement.tx_dealer)}</td>
                  <td><span className="pill pill-gold">STUB</span></td>
                  <td style={{ width: 36, color: 'var(--ink-400)' }}><Icon d={Icons.arrow_r} size={14}/></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function BigStat({ label, value, sub, highlight }) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div className="serif tabular" style={{ fontSize: 22, fontWeight: 500, marginTop: 4, letterSpacing: '-0.02em', color: highlight ? 'var(--gold-700)' : 'var(--ink-950)' }}>
        {value}
      </div>
      <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{sub}</div>
    </div>
  );
}

function FeeRow({ label, value, note }) {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
      <div>
        <div style={{ fontSize: 12.5, fontWeight: 500 }}>{label}</div>
        <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{note}</div>
      </div>
      <span className="mono tabular" style={{ fontSize: 14, fontWeight: 500 }}>{fmtUSD(value, { decimals: 2 })}</span>
    </div>
  );
}

function CumChart({ settled }) {
  // Generate plausible 24-point cumulative line
  const ordered = settled.slice().sort((a,b) => new Date(a.created) - new Date(b.created));
  let cum = 0;
  const points = [];
  // Spread settlements over 24 buckets
  const buckets = 24;
  for (let i = 0; i < buckets; i++) {
    const inBucket = ordered.filter((_, idx) => idx % buckets === i);
    cum += inBucket.reduce((s, r) => s + r.settlement.win_premium_usdc, 0);
    // also add baseline noise
    cum += rand(15, 80);
    points.push(cum);
  }
  const w = 760, h = 220, pad = 30;
  const max = Math.max(...points);
  const xy = points.map((v, i) => {
    const x = pad + (i / (buckets - 1)) * (w - pad * 2);
    const y = h - pad - (v / max) * (h - pad * 2);
    return [x, y];
  });
  const linePath = xy.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ');
  const areaPath = `${linePath} L ${xy[xy.length-1][0]} ${h-pad} L ${xy[0][0]} ${h-pad} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="cumfill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--gold-500)" stopOpacity="0.30"/>
          <stop offset="100%" stopColor="var(--gold-500)" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {/* grid */}
      {[0.25, 0.5, 0.75].map(t => (
        <line key={t} x1={pad} x2={w-pad} y1={h-pad - t * (h-pad*2)} y2={h-pad - t * (h-pad*2)}
          stroke="var(--ink-150)" strokeWidth="1" strokeDasharray="2 4"/>
      ))}
      <line x1={pad} x2={w-pad} y1={h-pad} y2={h-pad} stroke="var(--ink-200)" strokeWidth="1"/>
      <line x1={pad} x2={pad} y1={pad} y2={h-pad} stroke="var(--ink-200)" strokeWidth="1"/>
      {/* y labels */}
      {[0, 0.5, 1].map(t => (
        <text key={t} x={6} y={h-pad - t * (h-pad*2) + 4}
          fontSize="10" fontFamily="var(--ff-mono)" fill="var(--ink-500)">
          ${Math.round(max * t).toLocaleString()}
        </text>
      ))}
      <path d={areaPath} fill="url(#cumfill)"/>
      <path d={linePath} fill="none" stroke="var(--gold-600)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {xy.map((p, i) => i % 4 === 0 && (
        <circle key={i} cx={p[0]} cy={p[1]} r="3" fill="var(--paper)" stroke="var(--gold-600)" strokeWidth="1.5"/>
      ))}
      {/* x labels */}
      {[0, 6, 12, 18, 23].map(i => (
        <text key={i} x={pad + (i / (buckets - 1)) * (w - pad * 2)} y={h - 8}
          fontSize="10" fontFamily="var(--ff-mono)" fill="var(--ink-500)" textAnchor="middle">
          {String(i).padStart(2, '0')}:00
        </text>
      ))}
    </svg>
  );
}

// ─── Operations Panel ───────────────────────────────────────────────
function OpsView({ ops, onUpdate }) {
  const items = [
    {
      group: 'Fees',
      key: 'insertion_fee',
      label: 'Insertion Fee',
      sub: '$0.50 charged on RFQ publish',
      type: 'toggle', value: ops.insertion_fee,
    },
    {
      group: 'Payments',
      key: 'payment_mode',
      label: 'Payment Mode',
      sub: 'x402 stub returns deterministic tx hashes',
      type: 'segment', value: ops.payment_mode, options: ['stub', 'live'],
    },
    {
      group: 'Settlement',
      key: 'settlement_mode',
      label: 'Settlement Mode',
      sub: 'Stub: synthetic on-chain confirmations',
      type: 'segment', value: ops.settlement_mode, options: ['stub', 'live'],
    },
    {
      group: 'Model',
      key: 'model_endpoint',
      label: 'Model Endpoint',
      sub: 'Pricing & confidence scoring',
      type: 'segment', value: ops.model_endpoint, options: ['fico-rank-v2', 'fico-rank-v3', 'rank-experimental'],
    },
  ];

  const grouped = {};
  items.forEach(it => {
    grouped[it.group] = grouped[it.group] || [];
    grouped[it.group].push(it);
  });

  return (
    <div style={{ padding: 24, display:'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
      <div style={{ display:'flex', flexDirection:'column', gap: 12 }}>
        {/* Banner */}
        <div className="card" style={{ padding: 16, background: 'var(--gold-50)', borderColor: 'rgba(202,138,4,0.25)', display:'flex', gap: 12 }}>
          <span style={{ color: 'var(--gold-700)' }}><Icon d={Icons.alert} size={18}/></span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--gold-700)' }}>Simulation mode is active</div>
            <div style={{ fontSize: 12, color: 'var(--ink-700)', marginTop: 2 }}>
              All payment and settlement transactions are stubs. Toggling to <strong>live</strong> requires production keys and is disabled in this build.
            </div>
          </div>
        </div>

        {Object.entries(grouped).map(([group, list]) => (
          <div key={group} className="card">
            <div className="card-hd">
              <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>{group}</h3>
            </div>
            <div>
              {list.map((it, i) => (
                <div key={it.key} style={{ padding: 16, display:'flex', alignItems:'center', gap: 16, borderBottom: i < list.length - 1 ? '1px solid var(--ink-100)' : 'none' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{it.label}</div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>{it.sub}</div>
                  </div>
                  {it.type === 'toggle' ? (
                    <button onClick={() => onUpdate(it.key, !it.value)} style={{
                      width: 36, height: 20, borderRadius: 999, border: 0, cursor: 'pointer',
                      background: it.value ? 'var(--success-500)' : 'var(--ink-300)',
                      position: 'relative', transition: 'background 200ms',
                    }}>
                      <span style={{ position:'absolute', top: 2, left: it.value ? 18 : 2, width: 16, height: 16, borderRadius: 999, background: '#fff', transition: 'left 200ms', boxShadow: '0 1px 2px rgba(0,0,0,0.2)' }}/>
                    </button>
                  ) : (
                    <div style={{ display:'flex', gap: 2, padding: 2, background: 'var(--ink-100)', borderRadius: 4 }}>
                      {it.options.map(o => (
                        <button key={o} onClick={() => onUpdate(it.key, o)} style={{
                          height: 24, padding: '0 10px', border: 0, borderRadius: 3,
                          background: it.value === o ? 'var(--paper)' : 'transparent',
                          color: it.value === o ? 'var(--ink-950)' : 'var(--ink-600)',
                          fontFamily: 'var(--ff-mono)', fontSize: 11, fontWeight: 500, cursor: 'pointer',
                          boxShadow: it.value === o ? 'var(--sh-2)' : 'none',
                        }}>{o}</button>
                      ))}
                    </div>
                  )}
                  {it.value === 'stub' || (it.type === 'toggle' && !it.value) ? (
                    <span className="pill pill-gold">SIM</span>
                  ) : (
                    <span className="pill pill-success"><span className="live-dot"></span>LIVE</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display:'flex', flexDirection:'column', gap: 12 }}>
        <div className="card">
          <div className="card-hd"><h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Runtime Inspect</h3></div>
          <div className="card-bd" style={{ fontFamily: 'var(--ff-mono)', fontSize: 12, lineHeight: 1.9, color: 'var(--ink-700)' }}>
            <div><span style={{ color:'var(--ink-500)' }}>build:</span>          <span style={{ color: 'var(--ink-950)' }}>v0.4.2-rc.3</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>region:</span>         <span style={{ color: 'var(--ink-950)' }}>us-west-2</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>commit:</span>         <span style={{ color: 'var(--info-700)' }}>9a3f1b2</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>uptime:</span>         <span style={{ color: 'var(--ink-950)' }}>4d 12h 09m</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>lender_agents:</span>  <span style={{ color: 'var(--info-700)' }}>{LENDERS.length}</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>p99_bid_latency:</span><span style={{ color: 'var(--ink-950)' }}>312ms</span></div>
          </div>
        </div>

        <div className="card">
          <div className="card-hd"><h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Audit Log</h3></div>
          <div style={{ padding: '4px 0' }}>
            {[
              { t: 'settlement_mode set to stub', who: 'ops@appbid.io', time: '2m ago' },
              { t: 'fico-rank-v2 deployed',       who: 'system',          time: '4h ago' },
              { t: 'insertion_fee enabled',       who: 'ops@appbid.io',   time: '1d ago' },
              { t: 'rate-limit raised to 200rps', who: 'system',          time: '3d ago' },
            ].map((e, i) => (
              <div key={i} style={{ padding: '10px 16px', display:'flex', alignItems:'center', gap: 10, borderBottom: i < 3 ? '1px solid var(--ink-100)' : 'none' }}>
                <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--ink-300)' }}></span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{e.t}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{e.who} · {e.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { LedgerView, OpsView });
