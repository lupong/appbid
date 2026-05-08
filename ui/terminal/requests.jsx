// requests.jsx — New Request form + Requests list + Request Detail (live bids)

const { useState: rUseState, useEffect: rUseEffect, useRef: rUseRef, useMemo: rUseMemo } = React;

// ─── Requests List ────────────────────────────────────────────────────
function RequestsList({ requests, onOpenRequest, onRoute, demo, onToggleDemo, gpu }) {
  const [filter, setFilter] = rUseState('all');
  const filtered = requests.filter(r => filter === 'all' ? true : r.status === filter);
  const counts = {
    all:     requests.length,
    open:    requests.filter(r => r.status === 'open').length,
    settled: requests.filter(r => r.status === 'settled').length,
    expired: requests.filter(r => r.status === 'expired').length,
  };
  return (
    <div style={{ padding: 24 }}>
      <div className="card" style={{ marginBottom: 12, borderColor: demo?.running ? 'rgba(202,138,4,0.35)' : 'var(--ink-150)', background: demo?.running ? 'var(--gold-50)' : 'var(--paper)' }}>
        <div style={{ padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className={`pill ${demo?.running ? 'pill-gold' : 'pill-neutral'}`}>
              <span className={demo?.running ? 'live-dot' : 'pill-dot'}></span>
              {demo?.running ? 'DEMO RUNNING' : 'DEMO STOPPED'}
            </span>
            <span className="mono" style={{ fontSize: 11, color: 'var(--ink-600)' }}>
              Requests generated: {demo?.created || 0}
            </span>
            <span className="mono" style={{ fontSize: 11, color: 'var(--ink-600)' }}>
              GPU: {gpu?.available ? `${Math.round(gpu.util_pct || 0)}% util · ${Math.round(gpu.power_w || 0)}W` : 'N/A'}
            </span>
          </div>
          <button className={demo?.running ? 'btn btn-primary btn-sm' : 'btn btn-gold btn-sm'} onClick={onToggleDemo}>
            <Icon d={demo?.running ? Icons.close : Icons.zap} size={12}/>
            {demo?.running ? 'Stop demo' : 'Run demo now'}
          </button>
        </div>
      </div>
      <div className="card">
        <div className="card-hd">
          <div style={{ display:'flex', gap: 4 }}>
            {['all','open','settled','expired'].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                style={{
                  height: 28, padding: '0 12px', borderRadius: 4, border: 0,
                  background: filter === f ? 'var(--ink-900)' : 'transparent',
                  color: filter === f ? '#fff' : 'var(--ink-700)',
                  fontSize: 12, fontWeight: 500, cursor:'pointer',
                  textTransform: 'capitalize', display:'inline-flex', alignItems:'center', gap: 6,
                }}>
                {f} <span className="mono" style={{ fontSize: 10, opacity: 0.6 }}>{counts[f]}</span>
              </button>
            ))}
          </div>
          <div style={{ display:'flex', gap: 6 }}>
            <button className="btn btn-sm"><Icon d={Icons.filter} size={12}/>Filter</button>
            <button className="btn btn-sm"><Icon d={Icons.download} size={12}/>Export</button>
            <button className="btn btn-sm btn-primary" onClick={() => onRoute('new')}>
              <Icon d={Icons.plus} size={12}/>New Request
            </button>
          </div>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Request</th>
                <th>Dealer</th>
                <th>Vehicle</th>
                <th style={{ textAlign:'right' }}>Loan</th>
                <th style={{ textAlign:'right' }}>FICO</th>
                <th>Term</th>
                <th>State</th>
                <th style={{ textAlign:'right' }}>Incentive ($)</th>
                <th style={{ textAlign:'center' }}>Bids</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.id} style={{ cursor: 'pointer' }} onClick={() => onOpenRequest(r.id)}>
                  <td>
                    <div className="mono" style={{ fontWeight: 500 }}>{requestDisplayId(r)}</div>
                    <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{timeAgo(r.created)}</div>
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>{r.dealer_id}</td>
                  <td>{r.vehicle_type}</td>
                  <td className="num" style={{ textAlign: 'right' }}>${r.loan_amount.toLocaleString()}</td>
                  <td className="num" style={{ textAlign: 'right' }}>{r.applicant_fico}</td>
                  <td className="mono">{r.term_months}mo</td>
                  <td className="mono">{r.state}</td>
                  <td className="num" style={{ textAlign: 'right' }}>{fmtUSD(r.incentive_usd, { decimals: 2, sign: true })}</td>
                  <td style={{ textAlign:'center' }}><BidCountBar count={r.bids_count}/></td>
                  <td><StatusPill status={r.status}/></td>
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

// ─── New Bid Request Form ────────────────────────────────────────────
const VEHICLE_TYPES = ['New Sedan', 'New SUV', 'New Truck', 'Used Sedan', 'Used SUV', 'Used Truck', 'EV'];

function NewRequestForm({ onSubmit, onCancel }) {
  const [form, setForm] = rUseState({
    dealer_id: 'DLR-104',
    applicant_fico: 720,
    loan_amount: 32000,
    vehicle_type: 'New SUV',
    term_months: 60,
    state: 'CA',
    dealer_incentive_usd: 560,
  });
  const [touched, setTouched] = rUseState({});
  const [submitting, setSubmitting] = rUseState(false);

  function update(k, v) { setForm(f => ({ ...f, [k]: v })); }
  function blur(k) { setTouched(t => ({ ...t, [k]: true })); }

  // Validation
  const errors = rUseMemo(() => {
    const e = {};
    if (!/^DLR-\d{3}$/.test(form.dealer_id)) e.dealer_id = 'Format: DLR-### (3 digits)';
    if (form.applicant_fico < 300 || form.applicant_fico > 850) e.applicant_fico = 'FICO must be 300–850';
    if (form.loan_amount < 1000) e.loan_amount = 'Min loan $1,000';
    if (form.loan_amount > 250000) e.loan_amount = 'Max loan $250,000';
    if (![24, 36, 48, 60, 72, 84].includes(Number(form.term_months))) e.term_months = 'Term must be 24/36/48/60/72/84';
    const incentiveBps = usdToBps(form.loan_amount, form.dealer_incentive_usd);
    if (incentiveBps < -500 || incentiveBps > 500) {
      const maxAbsUsd = form.loan_amount * 0.05;
      e.dealer_incentive_usd = `Keep incentive within +/-${fmtUSD(maxAbsUsd, { decimals: 2 })} (5%)`;
    }
    return e;
  }, [form]);

  const canSubmit = Object.keys(errors).length === 0 && !submitting;

  function submit() {
    if (!canSubmit) {
      setTouched({ dealer_id: true, applicant_fico: true, loan_amount: true, term_months: true, dealer_incentive_usd: true });
      return;
    }
    setSubmitting(true);
    setTimeout(() => {
      onSubmit({
        ...form,
        id: reqId(),
        status: 'open',
        created: new Date().toISOString(),
        bids_count: 0,
      });
      setSubmitting(false);
    }, 700);
  }

  // Estimated bids preview
  const ficoBoost = (form.applicant_fico - 700) / 100;
  const estApr = Math.max(3.49, 6.20 - ficoBoost * 0.65);
  const incentiveBps = usdToBps(form.loan_amount, form.dealer_incentive_usd);
  const estBids = Math.min(8, Math.max(1, Math.round(4 + ficoBoost * 2 - (incentiveBps / 100))));
  const maxAbsIncentiveUsd = Math.max(500, form.loan_amount * 0.05);

  return (
    <div style={{ padding: 24, display:'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>

      <div className="card">
        <div className="card-hd">
          <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>RFQ Parameters</h3>
            <span className="pill pill-neutral" title="No PII transmitted">PII-FREE</span>
          </div>
          <span className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>{Object.keys(form).length} fields</span>
        </div>
        <div className="card-bd" style={{ display:'grid', gridTemplateColumns: '1fr 1fr', gap: 14, padding: 20 }}>

          <Field label="Dealer ID" hint="Anonymized dealer handle"
                 error={touched.dealer_id && errors.dealer_id}>
            <input className={`input mono ${touched.dealer_id && errors.dealer_id ? 'has-error' : ''}`}
              value={form.dealer_id} onChange={e => update('dealer_id', e.target.value)} onBlur={() => blur('dealer_id')}
              placeholder="DLR-###" />
          </Field>

          <Field label="State" hint="Where loan originates">
            <select className="select" value={form.state} onChange={e => update('state', e.target.value)}>
              {STATES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>

          <Field label="Applicant FICO" hint="300–850, no PII"
                 error={touched.applicant_fico && errors.applicant_fico}>
            <div style={{ display:'flex', gap: 10, alignItems:'center' }}>
              <input className={`input mono tabular ${touched.applicant_fico && errors.applicant_fico ? 'has-error' : ''}`}
                type="number" style={{ width: 90 }}
                value={form.applicant_fico} onChange={e => update('applicant_fico', +e.target.value)} onBlur={() => blur('applicant_fico')}/>
              <input type="range" min={500} max={850} value={form.applicant_fico}
                onChange={e => update('applicant_fico', +e.target.value)} style={{ flex: 1 }}/>
            </div>
            <FicoBand value={form.applicant_fico}/>
          </Field>

          <Field label="Loan Amount" hint="Principal in USD"
                 error={touched.loan_amount && errors.loan_amount}>
            <div style={{ position: 'relative' }}>
              <span className="mono" style={{ position: 'absolute', left: 10, top: 9, color: 'var(--ink-500)' }}>$</span>
              <input className={`input mono tabular ${touched.loan_amount && errors.loan_amount ? 'has-error' : ''}`}
                type="number" style={{ paddingLeft: 22 }}
                value={form.loan_amount} onChange={e => update('loan_amount', +e.target.value)} onBlur={() => blur('loan_amount')}/>
            </div>
          </Field>

          <Field label="Vehicle Type">
            <select className="select" value={form.vehicle_type} onChange={e => update('vehicle_type', e.target.value)}>
              {VEHICLE_TYPES.map(v => <option key={v}>{v}</option>)}
            </select>
          </Field>

          <Field label="Term (months)" error={touched.term_months && errors.term_months}>
            <div style={{ display:'flex', gap: 4 }}>
              {[36, 48, 60, 72, 84].map(t => (
                <button key={t} type="button" onClick={() => update('term_months', t)}
                  style={{
                    flex: 1, height: 34, border: '1px solid var(--ink-200)',
                    background: form.term_months === t ? 'var(--navy-900)' : 'var(--paper)',
                    color: form.term_months === t ? '#fff' : 'var(--ink-800)',
                    borderRadius: 4, fontSize: 13, cursor:'pointer', fontFamily: 'var(--ff-mono)', fontWeight: 500,
                  }}>{t}</button>
              ))}
            </div>
          </Field>

          <Field label="Dealer Incentive ($)" hint="Signed amount: -discount, +fee" gridSpan={2}
                 error={touched.dealer_incentive_usd && errors.dealer_incentive_usd}>
            <div style={{ display:'flex', gap: 10, alignItems:'center' }}>
              <input className={`input mono tabular ${touched.dealer_incentive_usd && errors.dealer_incentive_usd ? 'has-error' : ''}`}
                type="number" style={{ width: 100 }}
                value={form.dealer_incentive_usd} onChange={e => update('dealer_incentive_usd', +e.target.value)} onBlur={() => blur('dealer_incentive_usd')}/>
              <span className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>USD</span>
              <input type="range" min={-maxAbsIncentiveUsd} max={maxAbsIncentiveUsd} step={25} value={form.dealer_incentive_usd}
                onChange={e => update('dealer_incentive_usd', +e.target.value)} style={{ flex: 1 }}/>
              <span className="mono tabular" style={{ fontSize: 11, color: 'var(--ink-500)', minWidth: 56, textAlign: 'right' }}>
                {(incentiveBps / 100).toFixed(2)}%
              </span>
            </div>
          </Field>
        </div>

        <div style={{ borderTop: '1px solid var(--ink-150)', padding: 14, display:'flex', justifyContent:'space-between', alignItems:'center', background: 'var(--ink-25)' }}>
          <div className="mono" style={{ fontSize: 11, color: 'var(--ink-500)' }}>
            <Icon d={Icons.info} size={11}/> Insertion fee <strong style={{ color: 'var(--ink-700)' }}>$0.50</strong> · billed on publish
          </div>
          <div style={{ display:'flex', gap: 8 }}>
            <button className="btn" onClick={onCancel} disabled={submitting}>Cancel</button>
            <button className="btn btn-primary" onClick={submit} disabled={!canSubmit}>
              {submitting ? <><span className="live-dot" style={{ background:'#fff' }}></span> Publishing…</> : <>Publish RFQ <Icon d={Icons.arrow_r} size={12}/></>}
            </button>
          </div>
        </div>
      </div>

      {/* Live preview side */}
      <div style={{ display:'flex', flexDirection:'column', gap: 12 }}>
        <div className="card" style={{ padding: 18 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>RFQ Preview</div>
          <div style={{ fontFamily: 'var(--ff-mono)', fontSize: 12, lineHeight: 1.7, color: 'var(--ink-700)' }}>
            <div><span style={{ color:'var(--ink-500)' }}>dealer_id:</span>          <span style={{ color: 'var(--ink-950)' }}>"{form.dealer_id}"</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>applicant_fico:</span>     <span style={{ color: 'var(--info-700)' }}>{form.applicant_fico}</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>loan_amount:</span>        <span style={{ color: 'var(--info-700)' }}>{form.loan_amount}</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>vehicle_type:</span>       <span style={{ color: 'var(--ink-950)' }}>"{form.vehicle_type}"</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>term_months:</span>        <span style={{ color: 'var(--info-700)' }}>{form.term_months}</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>state:</span>              <span style={{ color: 'var(--ink-950)' }}>"{form.state}"</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>dealer_incentive_usd:</span> <span style={{ color: 'var(--info-700)' }}>{form.dealer_incentive_usd}</span></div>
            <div><span style={{ color:'var(--ink-500)' }}>dealer_incentive_percent:</span> <span style={{ color: 'var(--info-700)' }}>{(incentiveBps / 100).toFixed(2)}%</span></div>
          </div>
        </div>

        <div className="card" style={{ padding: 18, display:'flex', flexDirection:'column', gap: 12 }}>
          <div className="eyebrow">Model · Predicted Outcome</div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 10 }}>
            <PredictTile label="Expected APR"     value={`${estApr.toFixed(2)}%`} sub="From top lender"/>
            <PredictTile label="Expected bids"    value={estBids} sub="Within 60s"/>
          </div>
          <div style={{ fontSize: 11, color: 'var(--ink-500)', display:'flex', alignItems:'center', gap: 6 }}>
            <Icon d={Icons.info} size={11}/>
            Predictions from <span className="mono" style={{ color: 'var(--ink-700)' }}>fico-rank-v2</span> · stub mode
          </div>
        </div>

        <div className="card" style={{ padding: 14, background: 'var(--gold-50)', borderColor: 'rgba(202,138,4,0.25)', display:'flex', gap: 10 }}>
          <span style={{ color: 'var(--gold-700)' }}><Icon d={Icons.info} size={16}/></span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--gold-700)' }}>Demo mode active</div>
            <div style={{ fontSize: 11.5, color: 'var(--ink-700)', marginTop: 2 }}>
              Submitted requests fan out to 8 simulated lender agents. Settlement uses stub tx hashes.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, error, children, gridSpan = 1 }) {
  return (
    <div className="field" style={{ gridColumn: `span ${gridSpan}` }}>
      <div className="field-lbl">
        <span>{label}</span>
        {hint && !error && <span className="field-hint">{hint}</span>}
      </div>
      {children}
      {error && <div className="field-err"><Icon d={Icons.alert} size={11}/>{error}</div>}
    </div>
  );
}

function FicoBand({ value }) {
  const bands = [
    { name: 'Poor',     min: 300, max: 579, color: 'var(--danger-500)' },
    { name: 'Fair',     min: 580, max: 669, color: 'var(--warning-500)' },
    { name: 'Good',     min: 670, max: 739, color: '#84cc16' },
    { name: 'V.Good',   min: 740, max: 799, color: 'var(--success-500)' },
    { name: 'Excel.',   min: 800, max: 850, color: 'var(--success-700)' },
  ];
  const active = bands.find(b => value >= b.min && value <= b.max);
  return (
    <div style={{ display:'flex', gap: 2, marginTop: 4 }}>
      {bands.map(b => (
        <div key={b.name} style={{ flex: b.max - b.min, display:'flex', flexDirection:'column', gap: 2 }}>
          <div style={{ height: 4, background: active?.name === b.name ? b.color : 'var(--ink-150)', borderRadius: 2 }}/>
          <span className="mono" style={{ fontSize: 9, color: active?.name === b.name ? b.color : 'var(--ink-400)', fontWeight: active?.name === b.name ? 600 : 400 }}>{b.name}</span>
        </div>
      ))}
    </div>
  );
}

function PredictTile({ label, value, sub }) {
  return (
    <div style={{ padding: 12, background: 'var(--ink-25)', border: '1px solid var(--ink-150)', borderRadius: 4 }}>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div className="serif tabular" style={{ fontSize: 22, fontWeight: 500, marginTop: 2 }}>{value}</div>
      <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>{sub}</div>
    </div>
  );
}

Object.assign(window, { RequestsList, NewRequestForm });
