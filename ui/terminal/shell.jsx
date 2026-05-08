// shell.jsx — App shell: sidebar nav, topbar, demo mode pill

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ─── Icons (minimal, hand-drawn line set) ───────────────────────────────
const Icon = ({ d, size = 16, stroke = 1.6 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
    {typeof d === 'string' ? <path d={d}/> : d}
  </svg>
);
const Icons = {
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></>,
  plus:      <><path d="M12 5v14M5 12h14"/></>,
  list:      <><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></>,
  gavel:     <><path d="M14 4l6 6M16 6l-4 4M11 9l4 4-7 7-4-4 7-7zM3 21h10"/></>,
  vault:     <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></>,
  settings:  <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.36.14.7.36 1 .65"/></>,
  bell:      <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></>,
  search:    <><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></>,
  copy:      <><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>,
  check:     <><path d="M20 6L9 17l-5-5"/></>,
  arrow_r:   <><path d="M5 12h14M13 5l7 7-7 7"/></>,
  arrow_dn:  <><path d="M6 9l6 6 6-6"/></>,
  arrow_up:  <><path d="M18 15l-6-6-6 6"/></>,
  external:  <><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></>,
  close:     <><path d="M18 6L6 18M6 6l12 12"/></>,
  alert:     <><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"/></>,
  zap:       <><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></>,
  info:      <><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/></>,
  trend:     <><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/></>,
  spark:     <><path d="M12 3v18M3 12h18"/></>,
  filter:    <><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></>,
  download:  <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></>,
};

// ─── Sidebar ────────────────────────────────────────────────────────────
function Sidebar({ route, onRoute, treasury, demoMode }) {
  const navItems = [
    { id: 'dashboard',  label: 'Dashboard',   icon: 'dashboard' },
    { id: 'new',        label: 'New Request', icon: 'plus' },
    { id: 'requests',   label: 'Requests',    icon: 'list',  badge: 'LIVE' },
    { id: 'ledger',     label: 'Treasury',    icon: 'vault' },
    { id: 'ops',        label: 'Operations',  icon: 'settings' },
  ];
  return (
    <aside style={S.sidebar}>
      <div style={S.brand}>
        <div style={S.brandMark}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <rect x="2" y="6" width="20" height="14" rx="1.5" fill="#0a1628"/>
            <path d="M6 14V10M9 14V10M12 14V10M15 14V10M18 14V10" stroke="#ca8a04" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M2 6L12 2L22 6" stroke="#0a1628" strokeWidth="1.5" strokeLinejoin="round" fill="#ca8a04"/>
          </svg>
        </div>
        <div>
          <div style={{ fontFamily: 'var(--ff-serif)', fontSize: 17, fontWeight: 600, letterSpacing: '-0.01em' }}>AppBid</div>
          <div className="mono" style={{ fontSize: 9.5, color: 'var(--ink-500)', letterSpacing: '0.10em', textTransform: 'uppercase', marginTop: -1 }}>Terminal · v0.4.2</div>
        </div>
      </div>

      <nav style={{ padding: '8px 8px', flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
        <div className="eyebrow" style={{ padding: '12px 10px 8px' }}>Marketplace</div>
        {navItems.map(item => (
          <button key={item.id}
            onClick={() => onRoute(item.id)}
            style={{ ...S.navBtn, ...(route === item.id ? S.navBtnActive : null) }}>
            <span style={{ width: 18, display: 'inline-flex', color: route === item.id ? 'var(--gold-600)' : 'var(--ink-500)' }}>
              <Icon d={Icons[item.icon]} size={16}/>
            </span>
            <span style={{ flex: 1, textAlign: 'left' }}>{item.label}</span>
            {item.badge && (
              <span className="pill pill-success" style={{ height: 18, fontSize: 9, padding: '0 6px' }}>
                <span className="live-dot" style={{ width: 4, height: 4 }}></span>{item.badge}
              </span>
            )}
          </button>
        ))}

        <div className="eyebrow" style={{ padding: '20px 10px 8px' }}>Live KPI</div>
        <div style={S.kpiBlock}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline' }}>
            <span style={{ fontSize: 11, color: 'var(--ink-500)' }}>Win premium · today</span>
          </div>
          <div className="mono tabular" style={{ fontSize: 18, fontWeight: 500, color: 'var(--ink-900)', marginTop: 2 }}>
            ${treasury.win_premium_total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:4, marginTop:4 }}>
            <span style={{ color: 'var(--success-600)', fontSize: 11 }}><Icon d={Icons.trend} size={11}/></span>
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--success-600)' }}>+12.4%</span>
            <span style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>vs 24h</span>
          </div>
        </div>
      </nav>

      <div style={S.sidebarFoot}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 999, background: 'linear-gradient(135deg, #1e3a8a, #14305c)', color: '#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--ff-mono)', fontSize:11, fontWeight:600 }}>EM</div>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ fontSize: 12, fontWeight: 500 }}>E. Marquez</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--ink-500)' }}>ops@appbid.io</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

// ─── Topbar ─────────────────────────────────────────────────────────────
function Topbar({ route, onAction, demoMode, ops, marketplaceHealth, demo, gpu }) {
  const titles = {
    dashboard:  'Dashboard',
    new:        'New Bid Request',
    requests:   'Bid Requests',
    request:    'Request Detail',
    settlement: 'Settlement',
    ledger:     'Treasury & Ledger',
    ops:        'Operations',
  };
  return (
    <header style={S.topbar}>
      <div style={{ display:'flex', alignItems:'center', gap: 16, flex: 1, minWidth: 0 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 2 }}>AppBid · {route === 'request' ? 'Marketplace' : 'Console'}</div>
          <h1 style={{ margin: 0, fontFamily: 'var(--ff-serif)', fontSize: 19, fontWeight: 500, letterSpacing: '-0.01em', color: 'var(--ink-950)' }}>
            {titles[route] || 'AppBid'}
          </h1>
        </div>
        <div style={{ height: 28, width: 1, background: 'var(--ink-200)' }}></div>
        <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
          <span className="pill pill-success">
            <span className="live-dot"></span>
            MARKETPLACE · {marketplaceHealth.toUpperCase()}
          </span>
          <span className={`pill ${gpu?.available ? 'pill-success' : 'pill-neutral'}`} title="Live GPU telemetry from /gpu/metrics">
            <span className={gpu?.available ? 'live-dot' : 'pill-dot'}></span>
            GPU · {gpu?.available ? `${Math.round(gpu.util_pct || 0)}% util · ${Math.round(gpu.power_w || 0)}W` : 'N/A'}
          </span>
          <span className="pill pill-navy">
            <span className="pill-dot"></span>
            MODEL · {ops.model_endpoint}
          </span>
          {demo?.running && (
            <span className="pill pill-gold" title="Continuous request generator is active">
              <span className="live-dot"></span>
              DEMO TRAFFIC · {demo.created} created
            </span>
          )}
        </div>
      </div>

      <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
        <div style={{ position:'relative' }}>
          <input className="input" placeholder="Search RFQ, lender, tx hash…"
            style={{ width: 280, height: 32, paddingLeft: 30, fontSize: 13, background: 'var(--ink-25)' }}/>
          <span style={{ position:'absolute', left: 9, top: 8, color:'var(--ink-400)' }}>
            <Icon d={Icons.search} size={14}/>
          </span>
          <span className="mono" style={{ position:'absolute', right: 8, top: 7, color:'var(--ink-400)', fontSize: 10, padding:'1px 5px', border:'1px solid var(--ink-200)', borderRadius: 3 }}>⌘K</span>
        </div>

        {/* Demo mode pill — subtle but persistent */}
        <span className="pill pill-gold" title="All payments and settlements are simulated stubs">
          <span className="pill-dot" style={{ background: 'var(--gold-600)' }}></span>
          DEMO MODE · {demoMode.toUpperCase()}
        </span>

        <button className="btn btn-ghost" style={{ width: 32, padding: 0 }} title="Notifications">
          <Icon d={Icons.bell} size={16}/>
        </button>

        <button className="btn btn-primary" onClick={() => onAction('new')}>
          <Icon d={Icons.plus} size={14}/>
          New Request
        </button>
        <button
          className={demo?.running ? 'btn btn-primary' : 'btn btn-gold'}
          onClick={() => onAction('demo-flow-toggle')}
          title={demo?.running ? 'Stop continuous demo traffic' : 'Start continuous demo traffic'}
        >
          <Icon d={demo?.running ? Icons.close : Icons.zap} size={14}/>
          {demo?.running ? 'Stop demo' : 'Run demo now'}
        </button>
      </div>
    </header>
  );
}

// ─── Inline styles (component-scoped) ───────────────────────────────────
const S = {
  sidebar: {
    width: 'var(--sidebar-w)',
    minWidth: 'var(--sidebar-w)',
    background: 'var(--paper)',
    borderRight: '1px solid var(--ink-150)',
    display: 'flex',
    flexDirection: 'column',
    position: 'sticky',
    top: 0,
    height: '100vh',
  },
  brand: {
    height: 'var(--topbar-h)',
    padding: '0 16px',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    borderBottom: '1px solid var(--ink-150)',
  },
  brandMark: {
    width: 30, height: 30, borderRadius: 6,
    background: 'var(--ink-25)',
    border: '1px solid var(--ink-150)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  navBtn: {
    height: 32,
    padding: '0 10px',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    border: 0,
    background: 'transparent',
    color: 'var(--ink-700)',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    borderRadius: 4,
    width: '100%',
    transition: 'background 120ms, color 120ms',
  },
  navBtnActive: {
    background: 'var(--ink-100)',
    color: 'var(--ink-950)',
    boxShadow: 'inset 2px 0 0 var(--gold-500)',
  },
  kpiBlock: {
    margin: '4px 6px 0',
    padding: '12px 10px',
    background: 'linear-gradient(180deg, var(--ink-25), var(--paper))',
    border: '1px solid var(--ink-150)',
    borderRadius: 6,
  },
  sidebarFoot: {
    padding: 12,
    borderTop: '1px solid var(--ink-150)',
  },
  topbar: {
    height: 'var(--topbar-h)',
    padding: '0 24px',
    background: 'var(--paper)',
    borderBottom: '1px solid var(--ink-150)',
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    position: 'sticky',
    top: 0,
    zIndex: 50,
  },
};

Object.assign(window, { Icon, Icons, Sidebar, Topbar, ShellStyles: S });
