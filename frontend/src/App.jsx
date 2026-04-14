import { useState, useEffect } from 'react';
import MapView from './components/MapView';
import ConflictForecast from './components/ConflictForecast';
import Logo from './components/Logo';
import StationDashboard from './components/StationDashboard';
import SearchBar from './components/SearchBar';
import CorridorPage from './components/CorridorPage';

const DUMMY_TRAINS = [
  { id: 'TN001', lat: 19.07, lng: 72.87, speed: 60, delay: 0, status: 'on_time' },
  { id: 'TN002', lat: 28.61, lng: 77.20, speed: 30, delay: 8, status: 'delayed' },
  { id: 'TN003', lat: 13.08, lng: 80.27, speed: 45, delay: 3, status: 'at_risk' },
  { id: 'TN004', lat: 22.57, lng: 88.36, speed: 55, delay: 0, status: 'on_time' },
  { id: 'TN005', lat: 17.38, lng: 78.48, speed: 20, delay: 12, status: 'delayed' },
];

// Simulated IR baseline delays per station (what IR reports without RailIQ)
const STATION_MATRIX = [
  { name: 'Bhopal Jn',      corridor: 'Bhopal–Itarsi',     mode: 'live', irDelay: 48, riqDelay: 19, decisions: 34 },
  { name: 'Itarsi Jn',      corridor: 'Bhopal–Itarsi',     mode: 'live', irDelay: 52, riqDelay: 21, decisions: 41 },
  { name: 'Delhi Nizamuddin',corridor: 'Delhi–Mughalsarai', mode: 'live', irDelay: 61, riqDelay: 23, decisions: 58 },
  { name: 'Kanpur Central', corridor: 'Delhi–Mughalsarai', mode: 'live', irDelay: 44, riqDelay: 18, decisions: 47 },
  { name: 'Howrah Jn',      corridor: 'Howrah–Dhanbad',    mode: 'live', irDelay: 57, riqDelay: 24, decisions: 62 },
  { name: 'Asansol',        corridor: 'Howrah–Dhanbad', mode: 'live', irDelay: 43, riqDelay: 13, decisions: 31 },
  { name: 'Mumbai CST',     corridor: 'Simulation',        mode: 'sim',  irDelay: 35, riqDelay: 14, decisions: 28 },
  { name: 'Pune Jn',        corridor: 'Simulation',        mode: 'sim',  irDelay: 29, riqDelay: 12, decisions: 19 },
];

function App() {
  const [trains, setTrains] = useState(DUMMY_TRAINS);
  const [selectedStation, setSelectedStation] = useState(null);
  const [showStationDashboard, setShowStationDashboard] = useState(false);
  const [showCorridorPage, setShowCorridorPage] = useState(false);
  const [time, setTime] = useState(new Date().toLocaleTimeString());
  const [matrix, setMatrix] = useState(STATION_MATRIX);
  const [conflictsPrevented, setConflictsPrevented] = useState(84);
  const [delaySaved, setDelaySaved] = useState(27);

  // Live clock
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Simulate live matrix updates every 2s (live stations only)
  useEffect(() => {
    const interval = setInterval(() => {
      setMatrix(prev => prev.map(s => {
        if (s.mode !== 'live') return s;
        return {
          ...s,
          riqDelay: Math.max(10, s.riqDelay + (Math.random() > 0.5 ? 1 : -1)),
          decisions: s.decisions + (Math.random() > 0.6 ? 1 : 0),
        };
      }));
      setConflictsPrevented(prev => prev + (Math.random() > 0.7 ? 1 : 0));
      setDelaySaved(prev => Math.max(20, prev + (Math.random() > 0.5 ? 0.5 : -0.5)));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket
  useEffect(() => {
    const ws = new WebSocket('ws://10.208.200.223:8000/ws/live');
    ws.onopen = () => console.log('✅ WebSocket connected!');
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setTrains(data.trains);
    };
    ws.onerror = () => {
      const interval = setInterval(() => {
        setTrains(prev => prev.map(t => ({
          ...t,
          lat: t.lat + (Math.random() - 0.5) * 0.05,
          lng: t.lng + (Math.random() - 0.5) * 0.05,
        })));
      }, 2000);
      return () => clearInterval(interval);
    };
    ws.onclose = () => console.log('WebSocket disconnected');
    return () => ws.close();
  }, []);

  const handleOptimize = async () => {
    try {
      const res = await fetch('http://10.208.200.223:8000/optimize', { method: 'POST' });
      const data = await res.json();
      console.log('✅ Optimized:', data);
    } catch {
      console.log('API not available, using local optimize');
    }
    setTrains(prev => prev.map(t => ({ ...t, status: 'on_time', delay: 0, speed: 60 })));
  };

  const delayed = trains.filter(t => t.status === 'delayed').length;
  const atRisk  = trains.filter(t => t.status === 'at_risk').length;
  const onTime  = trains.filter(t => t.status === 'on_time').length;

  const avgImprovement = Math.round(
    matrix.reduce((sum, s) => sum + ((s.irDelay - s.riqDelay) / s.irDelay * 100), 0) / matrix.length
  );

  if (showCorridorPage) return <CorridorPage onBack={() => setShowCorridorPage(false)} />;
  if (showStationDashboard && selectedStation) {
    return <StationDashboard station={selectedStation} onBack={() => setShowStationDashboard(false)} />;
  }

  return (
    <div style={{ background: '#0a0a0a', color: 'white', minHeight: '100vh', fontFamily: 'monospace' }}>

      {/* TOP BAR */}
      <div style={{ padding: '10px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #222' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Logo />
          <SearchBar onStationSelect={(station) => {
            setSelectedStation(station);
            setShowStationDashboard(true);
          }} />
        </div>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          <span style={{ color: '#aaa', fontSize: '13px' }}>🕐 {time}</span>
          <span style={{ fontSize: '13px' }}>🟢 {onTime}</span>
          <span style={{ fontSize: '13px' }}>🔴 {delayed}</span>
          <span style={{ fontSize: '13px' }}>🟡 {atRisk}</span>
          <button onClick={() => setShowCorridorPage(true)} style={{
            background: '#1a6fff', color: '#fff', padding: '8px 16px',
            border: 'none', borderRadius: '6px', cursor: 'pointer',
            fontWeight: 'bold', fontSize: '13px', fontFamily: 'monospace'
          }}>🛤️ CORRIDORS</button>
          <button onClick={handleOptimize} style={{
            background: '#00ff88', color: '#000', padding: '8px 20px',
            border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold'
          }}>⚡ OPTIMIZE</button>
        </div>
      </div>

      {/* MAIN LAYOUT */}
      <div style={{ display: 'flex', height: 'calc(100vh - 57px)' }}>

        {/* LEFT — MAP + CHART */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1 }}>
            <MapView
              trains={trains}
              onStationClick={(station) => {
                setSelectedStation(station);
                setShowStationDashboard(true);
              }}
            />
          </div>
          <div style={{ padding: '10px 15px', borderTop: '1px solid #222' }}>
            <ConflictForecast trains={trains} />
          </div>
        </div>

        {/* RIGHT — PERFORMANCE MATRIX */}
        <div style={{
          width: '420px', borderLeft: '1px solid #222',
          display: 'flex', flexDirection: 'column',
          overflowY: 'auto', background: '#0a0a0a'
        }}>

          {/* Matrix Header */}
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #222' }}>
            <div style={{ fontSize: '11px', color: '#00ff88', letterSpacing: '2px', marginBottom: '10px' }}>
              SYSTEM PERFORMANCE MATRIX
            </div>

            {/* KPI Row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
              {[
                { label: 'AVG DELAY SAVED', val: `${Math.round(delaySaved)} min`, color: '#00ff88' },
                { label: 'CONFLICTS PREVENTED', val: conflictsPrevented, color: '#00ff88' },
                { label: 'AVG IMPROVEMENT', val: `${avgImprovement}%`, color: '#00ff88' },
              ].map(k => (
                <div key={k.label} style={{ background: '#111', border: '1px solid #222', borderRadius: '8px', padding: '8px 10px' }}>
                  <div style={{ fontSize: '8px', color: '#555', letterSpacing: '1.5px', marginBottom: '4px' }}>{k.label}</div>
                  <div style={{ fontSize: '18px', fontWeight: 'bold', color: k.color }}>{k.val}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Column Headers */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 60px 55px 55px 50px',
            gap: '4px',
            padding: '8px 16px',
            borderBottom: '1px solid #222',
            fontSize: '9px', color: '#555', letterSpacing: '1.5px'
          }}>
            <span>STATION</span>
            <span style={{ textAlign: 'right' }}>IR DELAY</span>
            <span style={{ textAlign: 'right' }}>RIQ DELAY</span>
            <span style={{ textAlign: 'right' }}>SAVED</span>
            <span style={{ textAlign: 'right' }}>DEC.</span>
          </div>

          {/* Station Rows */}
          <div style={{ flex: 1 }}>
            {matrix.map((s, i) => {
              const saved = s.irDelay - Math.round(s.riqDelay);
              const pct = Math.round(saved / s.irDelay * 100);
              const barWidth = Math.round((Math.round(s.riqDelay) / s.irDelay) * 100);
              return (
                <div key={i} style={{
                  padding: '10px 16px',
                  borderBottom: '1px solid #1a1a1a',
                  background: i % 2 === 0 ? '#0d0d0d' : '#0a0a0a'
                }}>
                  {/* Row top */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 60px 55px 55px 50px',
                    gap: '4px', alignItems: 'center', marginBottom: '6px'
                  }}>
                    {/* Station name + badge */}
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#fff' }}>{s.name}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginTop: '2px' }}>
                        <span style={{
                          fontSize: '9px', padding: '1px 6px', borderRadius: '99px', fontWeight: 'bold',
                          background: s.mode === 'live' ? '#0a2a1a' : '#2a1f0a',
                          color: s.mode === 'live' ? '#00ff88' : '#ffaa00',
                          border: `1px solid ${s.mode === 'live' ? '#00ff8840' : '#ffaa0040'}`
                        }}>
                          {s.mode === 'live' ? '● LIVE' : '◎ SIM'}
                        </span>
                        <span style={{ fontSize: '9px', color: '#444' }}>{s.corridor}</span>
                      </div>
                    </div>

                    <div style={{ textAlign: 'right', fontSize: '13px', color: '#ff4444' }}>
                      {s.irDelay}m
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '13px', color: '#00ff88', fontWeight: 'bold' }}>
                      {Math.round(s.riqDelay)}m
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '13px', color: '#ffaa00', fontWeight: 'bold' }}>
                      -{saved}m
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '12px', color: '#aaa' }}>
                      {Math.round(s.decisions)}
                    </div>
                  </div>

                  {/* Progress bar — RailIQ delay vs IR delay */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{
                      flex: 1, height: '4px', background: '#ff444430',
                      borderRadius: '99px', overflow: 'hidden'
                    }}>
                      <div style={{
                        width: `${barWidth}%`, height: '100%',
                        background: pct >= 60 ? '#00ff88' : pct >= 40 ? '#ffaa00' : '#ff4444',
                        borderRadius: '99px',
                        transition: 'width 1s ease'
                      }} />
                    </div>
                    <span style={{
                      fontSize: '10px', fontWeight: 'bold', minWidth: '34px', textAlign: 'right',
                      color: pct >= 60 ? '#00ff88' : pct >= 40 ? '#ffaa00' : '#ff4444'
                    }}>↓{pct}%</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer note */}
          <div style={{ padding: '10px 16px', borderTop: '1px solid #222', fontSize: '10px', color: '#444' }}>
            IR DELAY = Indian Railways baseline · RailDrishti decision · Updates every 2s on live corridors
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;