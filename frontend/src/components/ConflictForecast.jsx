import { useState, useEffect } from 'react';

const PREDICTIONS = [
  {
    id: 'TN002', sev: 'critical',
    text: 'Headway conflict with TN005 at Itarsi Jn',
    reason: 'GNN detects TN002 and TN005 converging on Track 1 at Itarsi Jn with only 3.2 min headway — minimum safe headway is 6 min. High cascade risk to TN008 and TN011 downstream.',
    conf: 91, tti: 4, action: 'Hold TN002 at Pipariya for 5 min',
    corridor: 'Bhopal–Itarsi'
  },
  {
    id: 'TN007', sev: 'warning',
    text: 'Speed drop — fog advisory section km 88–102',
    reason: 'Weather API reports visibility dropping below 2 km at section km 88–102 on Howrah–Dhanbad corridor. TN007 currently at 100 km/h, mandatory advisory requires 50 km/h. Expect 9 min delay.',
    conf: 87, tti: 9, action: 'Issue speed advisory 50 km/h',
    corridor: 'Howrah–Dhanbad'
  },
  {
    id: 'TN008', sev: 'critical',
    text: 'Platform conflict at Kanpur Central Pl.3',
    reason: 'TN008 and TN014 both scheduled for platform 3 at Kanpur Central within a 2 min window. Dispatcher assignment error detected. PPO recommends diverting TN014 to platform 5.',
    conf: 94, tti: 6, action: 'Divert TN014 → Platform 5',
    corridor: 'Delhi–Mughalsarai'
  },
  {
    id: 'TN011', sev: 'watch',
    text: 'Cascading delay risk from freight overlap',
    reason: 'Freight train 64502 running 18 min late on shared track. If not cleared by 14:42, TN011 passenger service will face minimum 11 min delay at Asansol. Currently low probability but rising.',
    conf: 73, tti: 14, action: 'Monitor — alert if conf > 85%',
    corridor: 'Howrah–Dhanbad'
  },
  {
    id: 'TN003', sev: 'warning',
    text: 'Track switch failure risk at Bhopal Jn',
    reason: 'Sensor data from axle counter at Bhopal Jn shows anomalous readings on Track 2 switch. Predictive maintenance model flags 68% probability of switch degradation within 2 hours.',
    conf: 78, tti: 11, action: 'Route TN003 via Track 1',
    corridor: 'Bhopal–Itarsi'
  },
];

const getSevColor = (sev) => {
  if (sev === 'critical') return '#ff4444';
  if (sev === 'warning') return '#ffaa00';
  return '#1a6fff';
};

const getCountdownColor = (mins) => {
  if (mins <= 5) return '#ff4444';
  if (mins <= 10) return '#ffaa00';
  return '#aaa';
};

const ConflictForecast = ({ trains }) => {
  const [current, setCurrent] = useState(0);
  const [countdowns, setCountdowns] = useState(PREDICTIONS.map(p => p.tti));
  const [preempted, setPreempted] = useState(new Set());
  const [openCard, setOpenCard] = useState(null);
  const [allPreempted, setAllPreempted] = useState(false);

  // Auto-cycle every 3s
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrent(prev => (prev + 1) % PREDICTIONS.length);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  // Tick countdowns every 8s (demo speed)
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdowns(prev => prev.map(t => Math.max(1, t - 1)));
    }, 8000);
    return () => clearInterval(timer);
  }, []);

  const handlePreemptAll = () => {
    setPreempted(new Set(PREDICTIONS.map((_, i) => i)));
    setAllPreempted(true);
  };

  return (
    <div style={{ background: '#0d0d0d', borderTop: '1px solid #222' }}>

      {/* TICKER STRIP */}
      <div style={{
        padding: '8px 16px', display: 'flex',
        alignItems: 'center', gap: '12px', overflow: 'hidden'
      }}>

        {/* Label */}
        <div style={{
          fontSize: '9px', color: '#00ff88', letterSpacing: '2px',
          whiteSpace: 'nowrap', borderRight: '1px solid #222',
          paddingRight: '12px', lineHeight: 1.6
        }}>
          CONFLICT<br />FORECAST
        </div>

        {/* Cards scroll area */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', gap: '8px' }}>
          {PREDICTIONS.map((p, i) => (
            <div
              key={p.id}
              onClick={() => setOpenCard(openCard === i ? null : i)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                background: '#111',
                border: `1px solid ${openCard === i ? getSevColor(p.sev) : '#222'}`,
                borderLeft: `3px solid ${getSevColor(p.sev)}`,
                borderRadius: '8px', padding: '6px 12px',
                whiteSpace: 'nowrap', cursor: 'pointer',
                opacity: preempted.has(i) ? 0.4 : 1,
                flexShrink: 0,
                transition: 'border-color 0.2s, opacity 0.3s',
                transform: current === i ? 'scale(1.02)' : 'scale(1)',
                transition: 'transform 0.3s ease'
              }}
            >
              {/* Blinking dot */}
              <div style={{
                width: '7px', height: '7px', borderRadius: '50%',
                background: getSevColor(p.sev), flexShrink: 0,
                animation: p.sev === 'critical' ? 'none' : 'none',
                opacity: p.sev === 'critical' ? 1 : 0.8
              }} />

              {/* Severity badge */}
              <span style={{
                fontSize: '8px', fontWeight: 'bold', padding: '2px 5px',
                borderRadius: '4px', letterSpacing: '1px',
                background: getSevColor(p.sev) + '22',
                color: getSevColor(p.sev),
                border: `1px solid ${getSevColor(p.sev)}40`
              }}>
                {p.sev.toUpperCase()}
              </span>

              <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#fff' }}>{p.id}</span>
              <span style={{ fontSize: '11px', color: '#aaa' }}>— {p.text}</span>
              <span style={{ fontSize: '10px', color: '#555' }}>{p.conf}%</span>

              {/* Countdown */}
              <span style={{
                fontSize: '11px', fontWeight: 'bold',
                padding: '2px 7px', borderRadius: '4px',
                background: '#1a1a1a', minWidth: '52px', textAlign: 'center',
                color: preempted.has(i) ? '#00ff88' : getCountdownColor(countdowns[i]),
                border: `1px solid ${preempted.has(i) ? '#00ff8840' : getCountdownColor(countdowns[i]) + '40'}`
              }}>
                {preempted.has(i) ? '✓ DONE' : `in ${countdowns[i]}m`}
              </span>
            </div>
          ))}
        </div>

        {/* Dots */}
        <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
          {PREDICTIONS.map((_, i) => (
            <div
              key={i}
              onClick={() => setCurrent(i)}
              style={{
                width: '6px', height: '6px', borderRadius: '50%',
                background: i === current ? '#00ff88' : '#333',
                cursor: 'pointer', transition: 'background 0.2s'
              }}
            />
          ))}
        </div>

        {/* Pre-empt button */}
        <button
          onClick={handlePreemptAll}
          style={{
            background: allPreempted ? '#1a1a1a' : '#00ff88',
            color: allPreempted ? '#00ff88' : '#000',
            border: allPreempted ? '1px solid #00ff8840' : 'none',
            borderRadius: '6px', padding: '7px 12px',
            cursor: 'pointer', fontWeight: 'bold',
            fontSize: '11px', fontFamily: 'monospace',
            whiteSpace: 'nowrap', flexShrink: 0
          }}
        >
          {allPreempted ? '✅ ALL PRE-EMPTED' : '⚡ PRE-EMPT ALL'}
        </button>
      </div>

      {/* EXPANDED DETAIL */}
      {openCard !== null && (
        <div style={{
          margin: '0 16px 10px',
          background: '#111', border: '1px solid #222',
          borderRadius: '8px', padding: '12px 16px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                fontSize: '8px', fontWeight: 'bold', padding: '2px 6px',
                borderRadius: '4px', letterSpacing: '1px',
                background: getSevColor(PREDICTIONS[openCard].sev) + '22',
                color: getSevColor(PREDICTIONS[openCard].sev),
                border: `1px solid ${getSevColor(PREDICTIONS[openCard].sev)}40`
              }}>
                {PREDICTIONS[openCard].sev.toUpperCase()}
              </span>
              <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#fff' }}>
                {PREDICTIONS[openCard].id} — {PREDICTIONS[openCard].text}
              </span>
            </div>
            <button onClick={() => setOpenCard(null)}
              style={{ background: 'transparent', border: 'none', color: '#555', cursor: 'pointer', fontSize: '16px' }}>
              ✕
            </button>
          </div>

          <div style={{ fontSize: '12px', color: '#aaa', lineHeight: 1.7, marginBottom: '10px' }}>
            {PREDICTIONS[openCard].reason}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
            {[
              { label: 'CONFIDENCE', val: PREDICTIONS[openCard].conf + '%' },
              { label: 'TIME TO IMPACT', val: preempted.has(openCard) ? 'Pre-empted ✓' : `~${countdowns[openCard]} min` },
              { label: 'SUGGESTED ACTION', val: PREDICTIONS[openCard].action },
            ].map(d => (
              <div key={d.label} style={{ background: '#0d0d0d', borderRadius: '6px', padding: '8px 10px' }}>
                <div style={{ fontSize: '9px', color: '#555', letterSpacing: '1.5px', marginBottom: '4px' }}>{d.label}</div>
                <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#fff' }}>{d.val}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ConflictForecast;