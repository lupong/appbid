// detail.jsx — Request Detail with live bid competition + Settlement screen

const { useState: dUseState, useEffect: dUseEffect, useRef: dUseRef, useMemo: dUseMemo } = React;

// ─── Request Detail / Live Bids ──────────────────────────────────────
function RequestDetail({ request, bids, isLive, onBack, onAcceptBid, onRoute, demoMode }) {
  const [confirming, setConfirming] = dUseState(null); // bid being confirmed
  const [selectedId, setSelectedId] = dUseState(null);

  if (!request) {
    return <div style={{ padding: 24 }}>Request not found.</div>;
  }

  // Sort bids by APR ascending (best first)
  const sorted = [...bids].sort((a, b) => a.apr - b.apr);
  const accepted = bids.find(b => b.status === 'accepted');
  const isSettled = request.status === 'settled' || request.status === 'accepted';

  return (
    <div style={{ padding: 24, display:'flex', flexDirection:'column', gap: 16 }}>
      {/* Breadcrumb */}
      <div style={{ display:'flex', alignItems:'center', gap: 8, fontSize: 12, color: 'var(--ink-500)' }}>
        <button className="btn btn-sm btn-ghost" onClick={onBack} style={{ padding: '0 8px' }}>
          <Icon d={Icons.arrow_r} size={11} stroke={2} />
          <span style={{ transform: 'rotate(180deg)', display:'inline-block', transform: 'scaleX(-1)' }}>→</span> Requests
        </button>
        <span>/</span>
        <span className="mono">{requestDisplayId(request)}</span>
      </div>

      {/* Summary */}
      <div className="card">
        <div style={{ padding: 20, display:'grid', gridTemplateColumns: 'auto 1fr auto', gap: 24, alignItems: 'center' }}>
          <div>
            <div className="eyebrow">Request</div>
            <div className="serif" style={{ fontSize: 28, fontWeight: 500, letterSpacing: '-0.02em' }}>
              {requestDisplayId(request)}
            </div>
            <div style={{ display:'flex', gap: 6, marginTop: 6 }}>
              <StatusPill status={request.status}/>
              {isLive && <span className="pill pill-success"><span className="live-dot"></span>BIDS STREAMING</span>}
            </div>
          </div>

          <div style={{ display:'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 18, padding: '0 8px', borderLeft: '1px solid var(--ink-150)', paddingLeft: 24 }}>
            <Stat label="Loan"    value={`$${request.loan_amount.toLocaleString()}`}/>
            <Stat label="FICO"    value={request.applicant_fico} valueColor={request.applicant_fico >= 740 ? 'var(--success-700)' : 'var(--ink-900)'}/>
            <Stat label="Vehicle" value={request.vehicle_type} small/>
            <Stat label="Term"    value={`${request.term_months}mo`}/>
            <Stat label="State"   value={request.state}/>
            <Stat label="Incentive" value={fmtUSD(request.incentive_usd, { decimals: 2, sign: true })}/>
          </div>

          <div style={{ display:'flex', gap: 8 }}>
            <button className="btn btn-sm">
              <Icon d={Icons.copy} size={12}/> Copy ID
            </button>
            <button className="btn btn-sm">
              <Icon d={Icons.external} size={12}/> JSON
            </button>
          </div>
        </div>
      </div>

      {/* Bid arena */}
      <div style={{ display:'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16 }}>

        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-hd">
            <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Lender Competition</h3>
              <span className="pill pill-neutral">{bids.length} BIDS</span>
              {isLive && <span className="mono shimmer" style={{ fontSize: 11, color: 'var(--gold-700)', padding: '0 8px' }}>scanning lenders…</span>}
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>
              Sort: APR ↑
            </div>
          </div>

          {bids.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center' }}>
              <div style={{ width: 48, height: 48, borderRadius: 999, background: 'var(--ink-100)', margin: '0 auto 12px', display:'flex', alignItems:'center', justifyContent:'center', color: 'var(--ink-500)' }}>
                <Icon d={Icons.gavel} size={20}/>
              </div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>Awaiting bids…</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 4 }}>
                {LENDERS.length} lender agents notified · first bid expected in ~3s
              </div>
            </div>
          ) : (
            <div style={{ position: 'relative' }}>
              {sorted.map((bid, idx) => (
                <BidRow key={bid.id} bid={bid} rank={idx + 1} isTop={idx === 0}
                  isAccepted={bid.id === accepted?.id}
                  isSelected={bid.id === selectedId}
                  isLost={accepted && bid.id !== accepted.id}
                  disabled={isSettled}
                  onSelect={() => !isSettled && setSelectedId(bid.id)}
                  onAccept={() => !isSettled && setConfirming(bid)}
                  request={request}/>
              ))}
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ display:'flex', flexDirection:'column', gap: 12 }}>
          {accepted ? (
            <AcceptedPanel bid={accepted} request={request} onRoute={onRoute}/>
          ) : (
            <ActionPanel selectedBid={sorted.find(b => b.id === selectedId)} topBid={sorted[0]}
              onAccept={(b) => setConfirming(b)} bidsCount={bids.length}/>
          )}

          <div className="card">
            <div className="card-hd"><h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Bid Distribution</h3></div>
            <div className="card-bd">
              <BidHistogram bids={sorted}/>
            </div>
          </div>

          <div className="card" style={{ padding: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Activity</div>
            <ActivityFeed bids={sorted} request={request} isLive={isLive}/>
          </div>
        </div>
      </div>

      {/* Confirm modal */}
      {confirming && (
        <ConfirmModal bid={confirming} request={request}
          onCancel={() => setConfirming(null)}
          onConfirm={() => { onAcceptBid(confirming.id); setConfirming(null); }}/>
      )}
    </div>
  );
}

function Stat({ label, value, small, valueColor }) {
  return (
    <div>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div className={small ? '' : 'mono tabular'} style={{ fontSize: small ? 13 : 16, fontWeight: 500, marginTop: 2, color: valueColor || 'var(--ink-900)' }}>
        {value}
      </div>
    </div>
  );
}

function BidRow({ bid, rank, isTop, isAccepted, isLost, isSelected, disabled, onSelect, onAccept, request }) {
  const [highlight, setHighlight] = dUseState(true);
  dUseEffect(() => {
    const t = setTimeout(() => setHighlight(false), 800);
    return () => clearTimeout(t);
  }, [bid.id]);

  const monthly = (bid.max_amount * (bid.apr / 100 / 12)) / (1 - Math.pow(1 + bid.apr/100/12, -bid.term_months));

  return (
    <div onClick={!disabled ? onSelect : undefined}
      style={{
        display: 'grid',
        gridTemplateColumns: '36px 200px 90px 70px 70px 70px 80px 1fr auto',
        alignItems: 'center',
        gap: 14,
        padding: '14px 16px',
        borderBottom: '1px solid var(--ink-100)',
        background: isAccepted ? 'linear-gradient(90deg, rgba(202,138,4,0.06), transparent)'
                  : isLost     ? 'var(--ink-25)'
                  : isSelected ? 'var(--info-50)'
                  : isTop      ? 'linear-gradient(90deg, rgba(202,138,4,0.04), transparent)'
                  : highlight  ? 'var(--info-50)'
                  : 'var(--paper)',
        opacity: isLost ? 0.55 : 1,
        cursor: disabled ? 'default' : 'pointer',
        transition: 'background 600ms var(--ease-out), opacity 300ms',
        position: 'relative',
      }}>
      {/* Rank */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
        {isTop && !isLost ? (
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            background: 'linear-gradient(135deg, var(--gold-400), var(--gold-600))',
            color: 'var(--ink-950)', display:'flex', alignItems:'center', justifyContent:'center',
            fontFamily: 'var(--ff-serif)', fontSize: 13, fontWeight: 600,
            boxShadow: '0 1px 3px rgba(202,138,4,0.4)',
          }}>
            ★
          </div>
        ) : (
          <div className="mono tabular" style={{ width: 28, height: 28, borderRadius: 4, background: 'var(--ink-100)', color: 'var(--ink-600)', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 12, fontWeight: 500 }}>
            {rank}
          </div>
        )}
      </div>

      {/* Lender */}
      <div style={{ display:'flex', alignItems:'center', gap: 10, minWidth: 0 }}>
        <div style={{ width: 30, height: 30, borderRadius: 4, background: bid.lender.avatar, color: '#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily: 'var(--ff-serif)', fontSize: 13, fontWeight: 600, flexShrink: 0 }}>
          {bid.lender.name[0]}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {bid.lender.name}
          </div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)', display:'flex', alignItems:'center', gap: 4 }}>
            <span>{bid.lender.id}</span>
            <span>·</span>
            <span style={{ color: 'var(--ink-700)' }}>{bid.lender.tier}</span>
          </div>
        </div>
      </div>

      {/* APR */}
      <div>
        <div className="serif tabular" style={{ fontSize: 18, fontWeight: 500, color: isTop && !isLost ? 'var(--gold-700)' : 'var(--ink-950)' }}>
          {bid.apr.toFixed(2)}<span style={{ fontSize: 11, color: 'var(--ink-500)', fontWeight: 400 }}>%</span>
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--ink-500)' }}>APR</div>
      </div>

      {/* Term */}
      <div className="mono tabular" style={{ fontSize: 13 }}>
        {bid.term_months}<span style={{ fontSize: 10, color: 'var(--ink-500)' }}> mo</span>
      </div>

      {/* Max amount */}
      <div className="mono tabular" style={{ fontSize: 13 }}>
        ${(bid.max_amount/1000).toFixed(1)}<span style={{ fontSize: 10, color: 'var(--ink-500)' }}>k</span>
      </div>

      {/* Max LTV */}
      <div className="mono tabular" style={{ fontSize: 13 }}>
        {bid.max_ltv_pct.toFixed(0)}<span style={{ fontSize: 10, color: 'var(--ink-500)' }}>% LTV</span>
      </div>

      {/* Incentive */}
      <div className="mono tabular" style={{ fontSize: 13 }}>
        {fmtUSD(bid.incentive_usd, { decimals: 2, sign: true })}
      </div>

      {/* Stipulations + confidence */}
      <div style={{ display:'flex', alignItems:'center', gap: 6, flexWrap: 'wrap' }}>
        {bid.stipulations.length === 0 ? (
          <span className="pill pill-success" style={{ fontSize: 9.5 }}>NO STIPS</span>
        ) : (
          bid.stipulations.map(s => (
            <span key={s} className="pill pill-neutral" style={{ fontSize: 9.5 }}>{s}</span>
          ))
        )}
        <div style={{ marginLeft: 'auto', display:'flex', alignItems:'center', gap: 6 }}>
          <ConfidenceBar value={bid.confidence}/>
          <span className="mono tabular" style={{ fontSize: 11, color: 'var(--ink-700)' }}>{(bid.confidence*100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Action */}
      <div>
        {isAccepted ? (
          <span className="pill pill-gold" style={{ height: 26 }}>
            <Icon d={Icons.check} size={11}/>ACCEPTED
          </span>
        ) : isLost ? (
          <span className="pill pill-neutral" style={{ height: 26 }}>LOST</span>
        ) : (
          <button className={`btn btn-sm ${isTop ? 'btn-gold' : ''}`} onClick={(e) => { e.stopPropagation(); onAccept(); }} disabled={disabled}>
            Accept
          </button>
        )}
      </div>
    </div>
  );
}

function ConfidenceBar({ value }) {
  return (
    <div style={{ width: 50, height: 4, background: 'var(--ink-100)', borderRadius: 2, overflow: 'hidden' }}>
      <div style={{ width: `${value*100}%`, height: '100%', background: value > 0.9 ? 'var(--success-500)' : value > 0.8 ? 'var(--gold-500)' : 'var(--warning-500)' }}/>
    </div>
  );
}

function ActionPanel({ selectedBid, topBid, onAccept, bidsCount }) {
  const bid = selectedBid || topBid;
  if (!bid) {
    return (
      <div className="card" style={{ padding: 18, background: 'var(--ink-25)' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Awaiting bids</div>
        <div style={{ fontSize: 13, color: 'var(--ink-700)' }}>Bids will appear here as lender agents respond.</div>
      </div>
    );
  }
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div style={{ padding: 18, background: 'linear-gradient(180deg, var(--navy-900), var(--navy-950))', color: '#fff' }}>
        <div className="eyebrow" style={{ color: 'var(--gold-300)', marginBottom: 8 }}>
          {selectedBid ? 'Selected Bid' : 'Top-Ranked Bid'}
        </div>
        <div style={{ display:'flex', alignItems:'baseline', gap: 6 }}>
          <div className="serif tabular" style={{ fontSize: 38, fontWeight: 500, letterSpacing: '-0.02em' }}>
            {bid.apr.toFixed(2)}<span style={{ fontSize: 18, color: 'var(--gold-300)' }}>%</span>
          </div>
          <span className="mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)' }}>APR · {bid.term_months}mo</span>
        </div>
        <div style={{ marginTop: 4, fontSize: 13, color: 'rgba(255,255,255,0.85)' }}>
          {bid.lender.name} <span className="mono" style={{ color: 'rgba(255,255,255,0.5)', fontSize: 11 }}>· {bid.lender.id}</span>
        </div>
      </div>
      <div style={{ padding: 16, display:'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <PanelStat label="Max amount" value={`$${bid.max_amount.toLocaleString()}`}/>
        <PanelStat label="Max LTV"   value={`${bid.max_ltv_pct.toFixed(0)}%`}/>
        <PanelStat label="Incentive"  value={fmtUSD(bid.incentive_usd, { decimals: 2, sign: true })}/>
        <PanelStat label="Confidence" value={`${(bid.confidence*100).toFixed(0)}%`}/>
        <PanelStat label="Stipulations" value={bid.stipulations.length === 0 ? 'None' : bid.stipulations.length}/>
      </div>
      <div style={{ padding: 16, borderTop: '1px solid var(--ink-150)', display:'flex', flexDirection:'column', gap: 8 }}>
        <button className="btn btn-gold btn-lg" onClick={() => onAccept(bid)} style={{ width: '100%' }}>
          <Icon d={Icons.check} size={14}/>
          Accept this bid · settle now
        </button>
        <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)', textAlign: 'center' }}>
          Acceptance is irrevocable · settlement is atomic
        </div>
      </div>
    </div>
  );
}

function AcceptedPanel({ bid, request, onRoute }) {
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div style={{ padding: 18, background: 'linear-gradient(180deg, var(--gold-50), var(--paper))' }}>
        <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 999, background: 'var(--gold-500)', color:'var(--ink-950)', display:'flex', alignItems:'center', justifyContent:'center' }}>
            <Icon d={Icons.check} size={18} stroke={2.5}/>
          </div>
          <div>
            <div className="eyebrow" style={{ color: 'var(--gold-700)' }}>Bid Accepted</div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>{bid.lender.name}</div>
          </div>
        </div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--ink-700)', marginTop: 12 }}>
          Settled at <strong>{bid.apr.toFixed(2)}%</strong> · ${bid.max_amount.toLocaleString()} · {bid.term_months}mo
        </div>
      </div>
      <div style={{ padding: 16 }}>
        <button className="btn btn-primary btn-lg" style={{ width: '100%' }} onClick={() => onRoute('settlement')}>
          View settlement <Icon d={Icons.arrow_r} size={13}/>
        </button>
      </div>
    </div>
  );
}

function PanelStat({ label, value }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div className="mono tabular" style={{ fontSize: 14, fontWeight: 500, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function BidHistogram({ bids }) {
  if (bids.length === 0) return <div style={{ fontSize: 12, color: 'var(--ink-500)' }}>No bids yet.</div>;
  const aprs = bids.map(b => b.apr);
  const min = Math.min(...aprs);
  const max = Math.max(...aprs);
  const range = Math.max(0.5, max - min);
  return (
    <div>
      <div style={{ display:'flex', alignItems:'flex-end', gap: 4, height: 80 }}>
        {bids.map((b, i) => {
          const h = ((b.apr - min) / range) * 60 + 16;
          return (
            <div key={b.id} style={{ flex: 1, display:'flex', flexDirection:'column', alignItems:'center', gap: 4 }}>
              <div style={{ height: h, width: '100%', background: i === 0 ? 'linear-gradient(180deg, var(--gold-500), var(--gold-600))' : 'var(--navy-100)', borderRadius: '2px 2px 0 0' }}/>
            </div>
          );
        })}
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', marginTop: 6 }}>
        <span className="mono" style={{ fontSize: 10, color: 'var(--ink-500)' }}>{min.toFixed(2)}%</span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--ink-500)' }}>{max.toFixed(2)}%</span>
      </div>
    </div>
  );
}

function ActivityFeed({ bids, request, isLive }) {
  const items = [
    { t: 'RFQ published', sub: `Fanned out to ${LENDERS.length} lenders`, time: timeAgo(request.created), icon: 'list' },
    ...bids.slice().reverse().slice(0, 4).map(b => ({
      t: `Bid received · ${b.lender.name}`, sub: `${b.apr.toFixed(2)}% · ${b.term_months}mo`, time: 'now', icon: 'gavel'
    })),
  ];
  return (
    <div style={{ display:'flex', flexDirection:'column', gap: 8, maxHeight: 200, overflowY: 'auto' }}>
      {items.map((it, i) => (
        <div key={i} style={{ display:'flex', gap: 10, padding: '6px 0' }}>
          <div style={{ width: 22, height: 22, borderRadius: 4, background: 'var(--ink-100)', color: 'var(--ink-600)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink: 0 }}>
            <Icon d={Icons[it.icon]} size={11}/>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 500 }}>{it.t}</div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{it.sub} · {it.time}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ConfirmModal({ bid, request, onCancel, onConfirm }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(10, 22, 40, 0.55)', backdropFilter: 'blur(4px)', display:'flex', alignItems:'center', justifyContent:'center', zIndex: 100, animation: 'fade-in 200ms' }}>
      <div className="card" style={{ width: 460, padding: 0, boxShadow: 'var(--sh-pop)' }}>
        <div style={{ padding: 20, borderBottom: '1px solid var(--ink-150)' }}>
          <div className="eyebrow" style={{ color: 'var(--gold-700)' }}>Confirm Acceptance</div>
          <h3 className="serif" style={{ margin: '6px 0 0', fontSize: 20, fontWeight: 500 }}>Accept bid from {bid.lender.name}?</h3>
        </div>
        <div style={{ padding: 20, display:'flex', flexDirection:'column', gap: 14 }}>
          <div style={{ background: 'var(--ink-25)', border: '1px solid var(--ink-150)', padding: 14, borderRadius: 4 }}>
            <div style={{ display:'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <PanelStat label="APR"        value={`${bid.apr.toFixed(2)}%`}/>
              <PanelStat label="Term"       value={`${bid.term_months}mo`}/>
              <PanelStat label="Max"        value={`$${bid.max_amount.toLocaleString()}`}/>
              <PanelStat label="Max LTV"    value={`${bid.max_ltv_pct.toFixed(0)}%`}/>
              <PanelStat label="Incentive"  value={fmtUSD(bid.incentive_usd, { decimals: 2, sign: true })}/>
            </div>
          </div>
          <div style={{ display:'flex', gap: 10, padding: 12, background: 'var(--gold-50)', borderRadius: 4, border: '1px solid rgba(202,138,4,0.25)' }}>
            <span style={{ color: 'var(--gold-700)', flexShrink: 0 }}><Icon d={Icons.alert} size={14}/></span>
            <div style={{ fontSize: 12, color: 'var(--ink-700)' }}>
              This is irrevocable. Other bids will be marked <strong>lost</strong> and settlement transactions will be triggered immediately.
            </div>
          </div>
        </div>
        <div style={{ padding: 16, borderTop: '1px solid var(--ink-150)', display:'flex', justifyContent:'flex-end', gap: 8, background: 'var(--ink-25)' }}>
          <button className="btn" onClick={onCancel}>Cancel</button>
          <button className="btn btn-gold" onClick={onConfirm}>
            <Icon d={Icons.check} size={13}/>
            Accept and settle
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Settlement screen ───────────────────────────────────────────────
function SettlementView({ request, bids, onBack, onRoute, demoMode }) {
  const [copied, setCopied] = dUseState(null);
  const accepted = bids.find(b => b.status === 'accepted');
  if (!accepted || !request.settlement) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <div style={{ fontSize: 14 }}>No settlement available — accept a bid first.</div>
      </div>
    );
  }
  const s = request.settlement;

  function copy(text, key) {
    try { navigator.clipboard.writeText(text); } catch (e) {}
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  }

  return (
    <div style={{ padding: 24, display:'flex', flexDirection:'column', gap: 16 }}>
      {/* Hero */}
      <div className="card" style={{ overflow: 'hidden', background: 'linear-gradient(135deg, var(--navy-950) 0%, var(--navy-900) 60%, #0a1628 100%)', color: '#fff', border: 0 }}>
        <div style={{ padding: 28, display:'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'center' }}>
          <div>
            <div style={{ display:'flex', alignItems:'center', gap: 8, marginBottom: 12 }}>
              <span className="pill pill-gold" style={{ background: 'rgba(202,138,4,0.18)', color: 'var(--gold-300)', borderColor: 'rgba(202,138,4,0.4)' }}>
                <Icon d={Icons.check} size={11}/>SETTLED
              </span>
              <span className="pill" style={{ background: 'rgba(255,255,255,0.08)', borderColor: 'rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.85)' }}>
                <span className="pill-dot" style={{ background: 'var(--gold-300)' }}></span>
                {s.mode === 'demo' || demoMode === 'stub' ? 'STUB MODE' : 'LIVE'}
              </span>
              <span className="mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>{requestDisplayId(request)}</span>
            </div>
            <h1 className="serif" style={{ margin: 0, fontSize: 30, fontWeight: 500, letterSpacing: '-0.02em', textWrap: 'balance' }}>
              Settled with {accepted.lender.name} at {accepted.apr.toFixed(2)}%
            </h1>
            <div style={{ marginTop: 10, fontSize: 13, color: 'rgba(255,255,255,0.65)' }}>
              ${accepted.max_amount.toLocaleString()} principal · {accepted.term_months}-month term · originated {request.state}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="eyebrow" style={{ color: 'rgba(255,255,255,0.55)' }}>Win Premium</div>
            <div className="serif tabular" style={{ fontSize: 56, fontWeight: 500, letterSpacing: '-0.03em', color: 'var(--gold-300)' }}>
              ${s.win_premium_usdc.toFixed(2)}
            </div>
            <div className="mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>USDC · split below</div>
          </div>
        </div>
      </div>

      {/* Split math */}
      <div style={{ display:'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card">
          <div className="card-hd"><h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Split Math</h3>
            <span className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>USDC</span>
          </div>
          <div style={{ padding: 18 }}>
            <SplitVisual win={s.win_premium_usdc} dealer={s.dealer_usdc} mkt={s.marketplace_usdc} reserve={s.reserve_usdc}/>
            <div style={{ marginTop: 18, fontFamily: 'var(--ff-mono)', fontSize: 12, lineHeight: 1.9, padding: 12, background: 'var(--ink-25)', borderRadius: 4, border: '1px solid var(--ink-100)' }}>
              <div><span style={{ color:'var(--ink-500)' }}>win_premium</span>     = <span style={{ color:'var(--gold-700)', fontWeight: 500 }}>${s.win_premium_usdc.toFixed(2)}</span></div>
              <div><span style={{ color:'var(--ink-500)' }}>dealer_share</span>    = win_premium × <span style={{ color: 'var(--info-700)' }}>0.80</span> = <span style={{ fontWeight: 500 }}>${s.dealer_usdc.toFixed(2)}</span></div>
              <div><span style={{ color:'var(--ink-500)' }}>marketplace_cut</span> = win_premium × <span style={{ color: 'var(--info-700)' }}>0.15</span> = <span style={{ fontWeight: 500 }}>${s.marketplace_usdc.toFixed(2)}</span></div>
              <div><span style={{ color:'var(--ink-500)' }}>reserve</span>         = win_premium × <span style={{ color: 'var(--info-700)' }}>0.05</span> = <span style={{ fontWeight: 500 }}>${s.reserve_usdc.toFixed(2)}</span></div>
            </div>
          </div>
        </div>

        {/* Tx hashes */}
        <div className="card">
          <div className="card-hd">
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Settlement Transactions</h3>
            <span className="pill pill-gold">{s.mode === 'demo' || demoMode === 'stub' ? 'STUB HASHES' : 'ON-CHAIN'}</span>
          </div>
          <div>
            <TxRow label="Dealer payout"     amount={s.dealer_usdc}      hash={s.tx_dealer}      color="var(--gold-600)"  copied={copied === 'd'} onCopy={() => copy(s.tx_dealer, 'd')}/>
            <TxRow label="Marketplace cut"   amount={s.marketplace_usdc} hash={s.tx_marketplace} color="var(--navy-700)"  copied={copied === 'm'} onCopy={() => copy(s.tx_marketplace, 'm')}/>
            <TxRow label="Reserve fund"      amount={s.reserve_usdc}     hash={s.tx_reserve}     color="var(--ink-500)"   copied={copied === 'r'} onCopy={() => copy(s.tx_reserve, 'r')}/>
          </div>
        </div>
      </div>

      {/* Footer actions */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding: '12px 16px', background: 'var(--paper)', border: '1px solid var(--ink-150)', borderRadius: 4 }}>
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>
          <Icon d={Icons.info} size={11}/> Settlement complete · audit trail written to ledger
        </div>
        <div style={{ display:'flex', gap: 8 }}>
          <button className="btn btn-sm" onClick={onBack}>Back to request</button>
          <button className="btn btn-sm btn-primary" onClick={() => onRoute('ledger')}>
            View in Treasury <Icon d={Icons.arrow_r} size={11}/>
          </button>
        </div>
      </div>
    </div>
  );
}

function SplitVisual({ win, dealer, mkt, reserve }) {
  const segs = [
    { label: 'Dealer',     v: dealer,  c: 'var(--gold-500)' },
    { label: 'Marketplace',v: mkt,     c: 'var(--navy-700)' },
    { label: 'Reserve',    v: reserve, c: 'var(--ink-400)'  },
  ];
  return (
    <div>
      <div style={{ display:'flex', height: 28, borderRadius: 4, overflow: 'hidden', border: '1px solid var(--ink-150)' }}>
        {segs.map((s, i) => (
          <div key={i} style={{ flex: s.v, background: s.c, display:'flex', alignItems:'center', paddingLeft: 10, color: i < 2 ? '#fff' : 'var(--ink-900)', fontSize: 11, fontFamily: 'var(--ff-mono)', fontWeight: 500 }}>
            ${s.v.toFixed(2)}
          </div>
        ))}
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', marginTop: 6 }}>
        {segs.map(s => (
          <div key={s.label} style={{ display:'flex', alignItems:'center', gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: s.c }}></span>
            <span style={{ fontSize: 11, color: 'var(--ink-700)' }}>{s.label} <span className="mono tabular" style={{ color: 'var(--ink-500)' }}>{((s.v/win)*100).toFixed(0)}%</span></span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TxRow({ label, amount, hash, color, copied, onCopy }) {
  return (
    <div style={{ padding: 14, borderBottom: '1px solid var(--ink-100)', display:'flex', alignItems:'center', gap: 14 }}>
      <div style={{ width: 4, height: 36, background: color, borderRadius: 2 }}></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display:'flex', alignItems:'baseline', gap: 8 }}>
          <span style={{ fontSize: 12.5, fontWeight: 500 }}>{label}</span>
          <span className="mono tabular" style={{ fontSize: 12, color: 'var(--ink-700)', fontWeight: 500 }}>${amount.toFixed(2)}</span>
        </div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--ink-500)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {hash}
        </div>
      </div>
      <button className="btn btn-sm btn-ghost" onClick={onCopy} style={{ flexShrink: 0 }}>
        {copied ? <><Icon d={Icons.check} size={12}/>Copied</> : <><Icon d={Icons.copy} size={12}/>Copy</>}
      </button>
    </div>
  );
}

Object.assign(window, { RequestDetail, SettlementView });
