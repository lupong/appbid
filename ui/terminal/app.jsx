const { useState, useEffect, useMemo, useCallback } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "stream_speed": "normal",
  "demo_banner": "subtle",
  "density": "comfortable",
  "accent": "gold"
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [route, setRoute] = useState('dashboard');
  const [requests, setRequests] = useState([]);
  const [activeReq, setActiveReq] = useState(null);
  const [bids, setBids] = useState({});
  const [ops, setOps] = useState({
    insertion_fee: true,
    payment_mode: 'stub',
    settlement_mode: 'stub',
    model_endpoint: 'fico-rank-v2',
  });
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState('');
  const [treasury, setTreasury] = useState({
    total_bids: 0,
    total_settlements: 0,
    win_premium_total: 0,
    marketplace_total: 0,
    dealer_total: 0,
    reserve_total: 0,
    insertion_fees: 0,
  });
  const [gpu, setGpu] = useState({
    available: false,
    sampled_at: '',
    util_pct: 0,
    mem_used_gb: 0,
    mem_total_gb: 0,
    power_w: 0,
    temp_c: 0,
  });
  const [demo, setDemo] = useState({
    running: false,
    created: 0,
    failures: 0,
    started_at: '',
  });

  const demoTimerRef = React.useRef(null);
  const demoSubmittingRef = React.useRef(false);

  const refreshState = useCallback(async () => {
    try {
      const live = await Backend.hydrateState();
      setRequests(live.requests);
      setBids(live.bidsByRequest);
      setTreasury(live.treasury);
      setLoadErr('');
      if (live.requests.length === 0 && route === 'request') {
        setRoute('dashboard');
      }
      const settledAny = live.requests.some(
        (r) => r.status === 'settled' && r.settlement && r.settlement.mode !== 'live',
      );
      setOps((o) => ({
        ...o,
        settlement_mode: settledAny ? 'stub' : o.settlement_mode,
      }));
    } catch (e) {
      setLoadErr(e.message || 'Unable to load marketplace state');
    } finally {
      setLoading(false);
    }
  }, [route]);

  useEffect(() => {
    refreshState();
    const id = setInterval(refreshState, 4000);
    return () => clearInterval(id);
  }, [refreshState]);

  useEffect(() => {
    let mounted = true;
    async function refreshGpu() {
      try {
        const snap = await Backend.getGpuMetrics();
        if (mounted) setGpu(snap);
      } catch (_e) {
        if (mounted) {
          setGpu((g) => ({
            ...g,
            available: false,
            sampled_at: new Date().toISOString(),
          }));
        }
      }
    }
    refreshGpu();
    const id = setInterval(refreshGpu, 2000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const layoutDensity = t.density === 'compact' ? 0.93 : 1;

  function openRequest(id) {
    setActiveReq(id);
    setRoute('request');
  }

  async function submitNewRequest(reqLikeForm) {
    await Backend.createRequest(reqLikeForm);
    await refreshState();
    setRoute('requests');
  }

  async function acceptBid(bidId) {
    if (!activeReq) return;
    await Backend.acceptBid(activeReq, bidId);
    await refreshState();
    setRoute('settlement');
  }

  function makeDemoPayload() {
    const states = ['CA', 'TX', 'FL', 'NY', 'WA', 'AZ'];
    const terms = [48, 60, 72, 84];
    const vehicles = ['New SUV', 'Used Sedan', 'New Truck', 'EV', 'Used SUV'];
    const dealerSuffix = String(Math.floor(Math.random() * 900) + 100);
    return {
      dealer_id: `DLR-${dealerSuffix}`,
      applicant_fico: Math.floor(Math.random() * 170) + 640,
      loan_amount: Math.floor(Math.random() * 47000) + 18000,
      vehicle_type: vehicles[Math.floor(Math.random() * vehicles.length)],
      term_months: terms[Math.floor(Math.random() * terms.length)],
      state: states[Math.floor(Math.random() * states.length)],
      dealer_incentive_usd: Math.floor(Math.random() * 800) + 250,
    };
  }

  async function submitOneDemoRequest() {
    if (demoSubmittingRef.current) return;
    demoSubmittingRef.current = true;
    try {
      const created = await Backend.createRequest(makeDemoPayload());
      setDemo((d) => ({ ...d, created: d.created + 1 }));
      setActiveReq(created.id);
    } catch (_e) {
      setDemo((d) => ({ ...d, failures: d.failures + 1 }));
    } finally {
      demoSubmittingRef.current = false;
    }
  }

  async function startDemoFlow() {
    if (demo.running) return;
    setRoute('requests');
    setDemo({
      running: true,
      created: 0,
      failures: 0,
      started_at: new Date().toISOString(),
    });
    await submitOneDemoRequest();
    await refreshState();
    demoTimerRef.current = setInterval(() => {
      submitOneDemoRequest();
    }, 1200);
  }

  async function stopDemoFlow() {
    if (demoTimerRef.current) {
      clearInterval(demoTimerRef.current);
      demoTimerRef.current = null;
    }
    demoSubmittingRef.current = false;
    setDemo((d) => ({ ...d, running: false }));
    await refreshState();
  }

  useEffect(() => {
    return () => {
      if (demoTimerRef.current) {
        clearInterval(demoTimerRef.current);
        demoTimerRef.current = null;
      }
    };
  }, []);

  async function toggleDemoFlow() {
    if (demo.running) {
      await stopDemoFlow();
    } else {
      await startDemoFlow();
    }
  }

  function handleAction(action) {
    if (action === 'new') setRoute('new');
    else if (action === 'demo-flow-toggle') toggleDemoFlow();
  }

  const currentRequest = requests.find((r) => r.id === activeReq);
  const currentBids = bids[activeReq] || [];

  let main;
  if (loading) {
    main = (
      <div style={{ padding: 24 }}>
        <div className="card" style={{ padding: 18 }}>
          Loading marketplace state...
        </div>
      </div>
    );
  } else if (loadErr) {
    main = (
      <div style={{ padding: 24 }}>
        <div className="card" style={{ padding: 18, borderColor: 'var(--danger-100)', background: 'var(--danger-50)' }}>
          Backend error: {loadErr}
        </div>
      </div>
    );
  } else if (route === 'dashboard') {
    main = <Dashboard requests={requests} treasury={treasury} ops={ops} onRoute={setRoute} onOpenRequest={openRequest}/>;
  } else if (route === 'new') {
    main = <NewRequestForm onSubmit={submitNewRequest} onCancel={() => setRoute('dashboard')}/>;
  } else if (route === 'requests') {
    main = <RequestsList
      requests={requests}
      onOpenRequest={openRequest}
      onRoute={setRoute}
      demo={demo}
      onToggleDemo={toggleDemoFlow}
      gpu={gpu}
    />;
  } else if (route === 'request') {
    main = <RequestDetail request={currentRequest} bids={currentBids}
                          isLive={false}
                          onBack={() => setRoute('requests')}
                          onAcceptBid={acceptBid}
                          onRoute={setRoute}
                          demoMode={ops.settlement_mode}/>;
  } else if (route === 'settlement') {
    main = <SettlementView request={currentRequest} bids={currentBids}
                           onBack={() => setRoute('request')}
                           onRoute={setRoute}
                           demoMode={ops.settlement_mode}/>;
  } else if (route === 'ledger') {
    main = <LedgerView requests={requests} treasury={treasury} onOpenRequest={openRequest}/>;
  } else if (route === 'ops') {
    main = <OpsView ops={ops} onUpdate={(k, v) => setOps((o) => ({ ...o, [k]: v }))}/>;
  } else {
    main = null;
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', fontSize: layoutDensity === 1 ? 13 : 12 }}>
      <Sidebar route={route} onRoute={setRoute} treasury={treasury} demoMode={ops.settlement_mode}/>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Topbar route={route} onAction={handleAction}
                demoMode={ops.settlement_mode}
                ops={ops}
                marketplaceHealth={loadErr ? 'degraded' : 'operational'}
                demo={demo}
                gpu={gpu}/>
        <main style={{ flex: 1, background: 'var(--ink-50)' }} key={route} className="fade-in">
          {main}
        </main>
      </div>

      <TweaksPanel>
        <TweakSection label="Layout"/>
        <TweakRadio label="Density" value={t.density}
          options={['compact', 'comfortable']}
          onChange={(v) => setTweak('density', v)}/>
        <TweakSection label="Actions"/>
        <TweakButton label={demo.running ? 'Stop demo flow' : 'Run demo flow'} onClick={toggleDemoFlow}/>
        <TweakButton label="Refresh now" onClick={refreshState}/>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
