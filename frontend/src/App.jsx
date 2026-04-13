import { useState, useEffect } from 'react';
import MapView from './components/MapView';
import ConflictSidebar from './components/ConflictSidebar';
import DelayChart from './components/DelayChart';
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

function App() {
  const [trains, setTrains] = useState(DUMMY_TRAINS);
  const [selectedStation, setSelectedStation] = useState(null);
  const [showStationDashboard, setShowStationDashboard] = useState(false);
  const [showCorridorPage, setShowCorridorPage] = useState(false);
  const [time, setTime] = useState(new Date().toLocaleTimeString());

  // Live clock
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // WebSocket connection with dummy fallback
  useEffect(() => {
    const ws = new WebSocket('ws://10.208.200.223:8000/ws/live');

    ws.onopen = () => console.log('✅ WebSocket connected!');

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setTrains(data.trains);
    };

    ws.onerror = () => {
      console.log('WebSocket error, using dummy data');
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
      const res = await fetch('http://10.208.200.223:8000/optimize', {
        method: 'POST'
      });
      const data = await res.json();
      console.log('✅ Optimized:', data);
    } catch (err) {
      console.log('API not available, using local optimize');
    }
    setTrains(prev => prev.map(t => ({
      ...t,
      status: 'on_time',
      delay: 0,
      speed: 60
    })));
  };

  const delayed = trains.filter(t => t.status === 'delayed').length;
  const atRisk = trains.filter(t => t.status === 'at_risk').length;
  const onTime = trains.filter(t => t.status === 'on_time').length;

  // Show corridor page
  if (showCorridorPage) {
    return <CorridorPage onBack={() => setShowCorridorPage(false)} />;
  }

  // Show station dashboard
  if (showStationDashboard && selectedStation) {
    return (
      <StationDashboard
        station={selectedStation}
        onBack={() => setShowStationDashboard(false)}
      />
    );
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
          <span>🟢 On Time: {onTime}</span>
          <span>🔴 Delayed: {delayed}</span>
          <span>🟡 At Risk: {atRisk}</span>
          <button onClick={() => setShowCorridorPage(true)}
            style={{
              background: '#1a6fff', color: '#fff',
              padding: '8px 16px', border: 'none',
              borderRadius: '6px', cursor: 'pointer',
              fontWeight: 'bold', fontSize: '13px',
              fontFamily: 'monospace'
            }}>
            🛤️ CORRIDORS
          </button>
          <button onClick={handleOptimize}
            style={{ background: '#00ff88', color: '#000', padding: '8px 20px',
                     border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>
            ⚡ OPTIMIZE
          </button>
        </div>
      </div>

      {/* MAIN LAYOUT */}
      <div style={{ display: 'flex' }}>

        {/* MAP */}
        <div style={{ flex: 1 }}>
          <MapView
            trains={trains}
            onStationClick={(station) => {
              setSelectedStation(station);
              setShowStationDashboard(true);
            }}
          />
          {/* D3 CHART */}
          <div style={{ padding: '15px' }}>
            <DelayChart trains={trains} />
          </div>
        </div>

        {/* SIDEBAR */}
        <ConflictSidebar
          trains={trains}
          selectedStation={selectedStation}
          onApprove={(id) => {
            setTrains(prev => prev.map(t =>
              t.id === id ? { ...t, status: 'on_time', delay: 0, speed: 60 } : t
            ));
          }}
          onOverride={(id) => {
            setTrains(prev => prev.map(t =>
              t.id === id ? { ...t, status: 'at_risk', delay: 2 } : t
            ));
            alert(`✋ Manual override set for ${id} — monitoring closely`);
          }}
          onMRDC={(id) => alert(`📡 Message sent to loco pilot of ${id} via MRDC!`)}
        />

      </div>
    </div>
  );
}

export default App;