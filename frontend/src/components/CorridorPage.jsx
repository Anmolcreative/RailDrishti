import { useState, useEffect } from 'react';
import Logo from './Logo';

const CORRIDORS = {
  'BPL-ET': {
    name: 'Bhopal → Itarsi',
    from: 'Bhopal Jn',
    to: 'Itarsi Jn',
    distance: '90 km',
    zone: 'WCR',
    trains: [
      { id: 'TN001', name: 'Narmada Express', speed: 60, delay: 0, status: 'on_time', track: 'Track 1', weather: 'Clear', eta: '14:30' },
      { id: 'TN002', name: 'Bhopal Express', speed: 30, delay: 8, status: 'delayed', track: 'Track 2', weather: 'Cloudy', eta: '14:45' },
      { id: 'TN003', name: 'Gondwana Express', speed: 45, delay: 3, status: 'at_risk', track: 'Track 1', weather: 'Clear', eta: '15:00' },
      { id: 'TN004', name: 'Mahakaushal Exp', speed: 55, delay: 0, status: 'on_time', track: 'Track 2', weather: 'Clear', eta: '15:15' },
      { id: 'TN005', name: 'Itarsi Passenger', speed: 20, delay: 12, status: 'delayed', track: 'Track 1', weather: 'Rain', eta: '15:30' },
    ]
  },
  'NDLS-MGS': {
    name: 'Delhi → Mugalsarai',
    from: 'New Delhi',
    to: 'Mugalsarai Jn',
    distance: '1015 km',
    zone: 'NR/NCR',
    trains: [
      { id: 'TN006', name: 'Rajdhani Express', speed: 130, delay: 0, status: 'on_time', track: 'Track 1', weather: 'Clear', eta: '22:00' },
      { id: 'TN007', name: 'Shatabdi Express', speed: 100, delay: 5, status: 'at_risk', track: 'Track 2', weather: 'Foggy', eta: '22:30' },
      { id: 'TN008', name: 'Poorva Express', speed: 40, delay: 15, status: 'delayed', track: 'Track 1', weather: 'Clear', eta: '23:15' },
      { id: 'TN009', name: 'Kashi Express', speed: 70, delay: 0, status: 'on_time', track: 'Track 2', weather: 'Clear', eta: '23:00' },
    ]
  },
  'HWH-DHN': {
    name: 'Howrah → Dhanbad',
    from: 'Howrah Jn',
    to: 'Dhanbad Jn',
    distance: '263 km',
    zone: 'ER/SER',
    trains: [
      { id: 'TN010', name: 'Black Diamond Exp', speed: 80, delay: 0, status: 'on_time', track: 'Track 1', weather: 'Clear', eta: '16:00' },
      { id: 'TN011', name: 'Coalfield Express', speed: 35, delay: 10, status: 'delayed', track: 'Track 2', weather: 'Rain', eta: '16:45' },
      { id: 'TN012', name: 'Howrah Express', speed: 60, delay: 2, status: 'at_risk', track: 'Track 1', weather: 'Cloudy', eta: '16:30' },
    ]
  }
};

const getColor = (status) => {
  if (status === 'on_time') return '#00ff88';
  if (status === 'delayed') return '#ff4444';
  return '#ffaa00';
};

const getWeatherIcon = (weather) => {
  if (weather === 'Rain') return '🌧️';
  if (weather === 'Foggy') return '🌫️';
  if (weather === 'Cloudy') return '⛅';
  return '☀️';
};

const CorridorPage = ({ onBack }) => {
  const [selectedCorridor, setSelectedCorridor] = useState('BPL-ET');
  const [trains, setTrains] = useState(CORRIDORS['BPL-ET'].trains);
  const [search, setSearch] = useState('Bhopal → Itarsi');
  const [showDropdown, setShowDropdown] = useState(false);
  const [approvedCount, setApprovedCount] = useState(0);

  const filteredCorridors = Object.keys(CORRIDORS).filter(k =>
    CORRIDORS[k].name.toLowerCase().includes(search.toLowerCase()) ||
    CORRIDORS[k].from.toLowerCase().includes(search.toLowerCase()) ||
    CORRIDORS[k].to.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    if (!selectedCorridor) return;
    setTrains(CORRIDORS[selectedCorridor].trains);

    const interval = setInterval(() => {
      setTrains(prev => prev.map(t => ({
        ...t,
        speed: Math.max(10, t.speed + Math.floor((Math.random() - 0.5) * 10)),
        delay: Math.max(0, t.delay + Math.floor((Math.random() - 0.5) * 2)),
      })));
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedCorridor]);

  const handleCorridorSelect = (key) => {
    setSelectedCorridor(key);
    setSearch(CORRIDORS[key].name);
    setShowDropdown(false);
  };

  const handleApprove = (id) => {
    setTrains(prev => prev.map(t =>
      t.id === id ? { ...t, status: 'on_time', delay: 0, speed: 60 } : t
    ));
    setApprovedCount(prev => prev + 1);
  };

  const handleOptimizeAll = () => {
    setTrains(prev => prev.map(t => ({
      ...t, status: 'on_time', delay: 0, speed: 60
    })));
    setApprovedCount(prev => prev + trains.filter(t => t.status !== 'on_time').length);
  };

  return (
    <div style={{
      background: '#0a0a0a', color: 'white',
      minHeight: '100vh', fontFamily: 'monospace',
      position: 'relative', overflow: 'hidden'
    }}>

      {/* WATERMARK */}
      <img src="/logo-watermark.png" alt="" style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        width: '600px', height: '600px',
        objectFit: 'contain', opacity: 0.06,
        pointerEvents: 'none', zIndex: 0
      }} />

      {/* HEADER */}
      <div style={{
        padding: '10px 20px', borderBottom: '1px solid #222',
        display: 'flex', alignItems: 'center', gap: '15px',
        position: 'relative', zIndex: 10          // ← bumped from 2 to 10
      }}>
        <button onClick={onBack} style={{
          background: '#222', border: '1px solid #333',
          color: '#aaa', padding: '6px 14px',
          borderRadius: '6px', cursor: 'pointer',
          fontFamily: 'monospace', fontSize: '13px'
        }}>← Back</button>

        <Logo />

        <span style={{ color: '#555', fontSize: '13px' }}>|</span>
        <span style={{ color: '#aaa', fontSize: '13px', letterSpacing: '2px' }}>
          CORRIDOR CONTROL
        </span>

        {/* SEARCH BAR WITH DROPDOWN */}
        <div style={{ position: 'relative', marginLeft: '10px' }}>
          <div style={{
            display: 'flex', alignItems: 'center',
            background: '#111', border: '1px solid #333',
            borderRadius: '20px', padding: '6px 14px', gap: '8px',
            width: '280px'
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="text"
              value={search}
              onChange={e => { setSearch(e.target.value); setShowDropdown(true); }}
              onFocus={() => setShowDropdown(true)}
              placeholder="Search corridor..."
              style={{
                background: 'transparent', border: 'none',
                outline: 'none', color: 'white',
                fontFamily: 'monospace', fontSize: '13px',
                width: '100%'
              }}
            />
          </div>

          {/* DROPDOWN — FIX: zIndex 9999 + isolation */}
          {showDropdown && (
            <div style={{
              position: 'absolute', top: '110%', left: 0,
              background: '#111', border: '1px solid #333',
              borderRadius: '10px', width: '280px',
              zIndex: 9999,                        // ← was 1000, now 9999
              isolation: 'isolate',                // ← new: forces own stacking context
              overflow: 'hidden'
            }}>
              {filteredCorridors.map(key => (
                <div key={key}
                  onClick={() => handleCorridorSelect(key)}
                  style={{
                    padding: '10px 14px', cursor: 'pointer',
                    borderBottom: '1px solid #222',
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = '#1a1a1a'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 'bold' }}>
                      🚂 {CORRIDORS[key].name}
                    </div>
                    <div style={{ fontSize: '10px', color: '#666', marginTop: '2px' }}>
                      {CORRIDORS[key].distance} · {CORRIDORS[key].zone}
                    </div>
                  </div>
                  <span style={{ fontSize: '11px', color: '#aaa' }}>
                    {CORRIDORS[key].trains.length} trains
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* RIGHT SIDE */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '10px', alignItems: 'center' }}>
          {approvedCount > 0 && (
            <span style={{ color: '#00ff88', fontSize: '12px' }}>
              ✅ {approvedCount} decisions today
            </span>
          )}
          <button onClick={handleOptimizeAll} style={{
            background: '#00ff88', color: '#000',
            border: 'none', borderRadius: '6px',
            padding: '6px 16px', cursor: 'pointer',
            fontWeight: 'bold', fontFamily: 'monospace',
            fontSize: '13px'
          }}>
            ⚡ OPTIMIZE CORRIDOR
          </button>
        </div>
      </div>

      {/* STATS BAR */}
      <div style={{
        display: 'flex', gap: '10px', padding: '12px 20px',
        borderBottom: '1px solid #222', position: 'relative', zIndex: 2
      }}>
        {[
          { label: 'TOTAL', val: trains.length, color: '#fff' },
          { label: 'ON TIME', val: trains.filter(t => t.status === 'on_time').length, color: '#00ff88' },
          { label: 'DELAYED', val: trains.filter(t => t.status === 'delayed').length, color: '#ff4444' },
          { label: 'AT RISK', val: trains.filter(t => t.status === 'at_risk').length, color: '#ffaa00' },
          { label: 'CORRIDOR', val: CORRIDORS[selectedCorridor].name, color: '#aaa' },
          { label: 'DISTANCE', val: CORRIDORS[selectedCorridor].distance, color: '#aaa' },
          { label: 'ZONE', val: CORRIDORS[selectedCorridor].zone, color: '#aaa' },
        ].map(s => (
          <div key={s.label} style={{
            background: '#111', border: '1px solid #222',
            borderRadius: '8px', padding: '8px 14px',
            flex: s.label === 'CORRIDOR' ? 2 : 1
          }}>
            <div style={{ fontSize: '9px', color: '#555', letterSpacing: '2px' }}>{s.label}</div>
            <div style={{ fontSize: s.label === 'CORRIDOR' ? '12px' : '18px', fontWeight: 'bold', color: s.color }}>
              {s.val}
            </div>
          </div>
        ))}
      </div>

      {/* TRAIN LIST */}
      <div style={{ padding: '15px 20px', position: 'relative', zIndex: 2, display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {trains.map(train => (
          <div key={train.id} style={{
            background: '#111',
            border: `1px solid ${getColor(train.status)}`,
            borderRadius: '10px', padding: '12px 16px',
            display: 'flex', alignItems: 'center', gap: '20px'
          }}>
            <div style={{ minWidth: '160px' }}>
              <div style={{ fontWeight: 'bold', fontSize: '14px' }}>🚂 {train.id}</div>
              <div style={{ fontSize: '11px', color: '#ccc', marginTop: '3px' }}>{train.name}</div>
            </div>
            <span style={{
              background: getColor(train.status),
              color: '#000', padding: '3px 10px',
              borderRadius: '10px', fontSize: '10px',
              fontWeight: 'bold', minWidth: '70px', textAlign: 'center'
            }}>
              {train.status.toUpperCase()}
            </span>
            <div style={{ display: 'flex', gap: '20px', flex: 1, fontSize: '12px', color: '#aaa' }}>
              <span>🏎️ {train.speed} km/h</span>
              <span>⏱️ {train.delay} mins delay</span>
              <span>🛤️ {train.track}</span>
              <span>{getWeatherIcon(train.weather)} {train.weather}</span>
              <span>🕐 ETA: {train.eta}</span>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button onClick={() => handleApprove(train.id)}
                style={{ background: '#00ff88', color: '#000', border: 'none', borderRadius: '5px', padding: '5px 10px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                ✅ APPROVE AI
              </button>
              <button onClick={() => alert(`✋ Override set for ${train.id}`)}
                style={{ background: '#ffaa00', color: '#000', border: 'none', borderRadius: '5px', padding: '5px 10px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                ✋ OVERRIDE
              </button>
              <button onClick={() => alert(`📡 MRDC sent to ${train.name}`)}
                style={{ background: '#1a6fff', color: '#fff', border: 'none', borderRadius: '5px', padding: '5px 10px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                📡 MRDC SEND
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Click outside to close dropdown */}
      {showDropdown && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 1 }}
          onClick={() => setShowDropdown(false)}
        />
      )}
    </div>
  );
};

export default CorridorPage;