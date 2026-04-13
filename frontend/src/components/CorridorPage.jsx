import { useState, useEffect } from 'react';
import Logo from './Logo';

const CORRIDORS = {
  'bhopal-itarsi': {
    name: 'Bhopal → Itarsi',
    from: 'Bhopal Jn',
    to: 'Itarsi Jn',
    distance: '90 km',
    trains: [
      { id: 'TN001', name: 'Narmada Express', speed: 60, delay: 0, status: 'on_time', lat: 23.25, lng: 77.41, track: 'Track 1', weather: 'Clear', eta: '14:30' },
      { id: 'TN002', name: 'Bhopal Express', speed: 30, delay: 8, status: 'delayed', lat: 22.90, lng: 77.58, track: 'Track 2', weather: 'Cloudy', eta: '14:45' },
      { id: 'TN003', name: 'Gondwana Express', speed: 45, delay: 3, status: 'at_risk', lat: 22.80, lng: 77.63, track: 'Track 1', weather: 'Clear', eta: '15:00' },
      { id: 'TN004', name: 'Mahakaushal Exp', speed: 55, delay: 0, status: 'on_time', lat: 22.70, lng: 77.70, track: 'Track 2', weather: 'Clear', eta: '15:15' },
      { id: 'TN005', name: 'Itarsi Passenger', speed: 20, delay: 12, status: 'delayed', lat: 22.65, lng: 77.75, track: 'Track 1', weather: 'Rain', eta: '15:30' },
    ]
  },
  'delhi-mugalsarai': {
    name: 'Delhi → Mugalsarai',
    from: 'New Delhi',
    to: 'Mugalsarai Jn',
    distance: '780 km',
    trains: [
      { id: 'TN006', name: 'Rajdhani Express', speed: 130, delay: 0, status: 'on_time', lat: 28.63, lng: 77.22, track: 'Track 1', weather: 'Clear', eta: '22:00' },
      { id: 'TN007', name: 'Shatabdi Express', speed: 100, delay: 5, status: 'at_risk', lat: 27.17, lng: 78.01, track: 'Track 2', weather: 'Foggy', eta: '22:30' },
      { id: 'TN008', name: 'Poorva Express', speed: 40, delay: 15, status: 'delayed', lat: 25.43, lng: 81.84, track: 'Track 1', weather: 'Clear', eta: '23:15' },
      { id: 'TN009', name: 'Kashi Express', speed: 70, delay: 0, status: 'on_time', lat: 26.44, lng: 80.33, track: 'Track 2', weather: 'Clear', eta: '23:00' },
    ]
  },
  'howrah-dhanbad': {
    name: 'Howrah → Dhanbad',
    from: 'Howrah Jn',
    to: 'Dhanbad Jn',
    distance: '260 km',
    trains: [
      { id: 'TN010', name: 'Black Diamond Exp', speed: 80, delay: 0, status: 'on_time', lat: 22.56, lng: 88.34, track: 'Track 1', weather: 'Clear', eta: '16:00' },
      { id: 'TN011', name: 'Coalfield Express', speed: 35, delay: 10, status: 'delayed', lat: 23.25, lng: 87.08, track: 'Track 2', weather: 'Rain', eta: '16:45' },
      { id: 'TN012', name: 'Howrah Express', speed: 60, delay: 2, status: 'at_risk', lat: 23.52, lng: 87.31, track: 'Track 1', weather: 'Cloudy', eta: '16:30' },
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
  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [trains, setTrains] = useState([]);
  const [search, setSearch] = useState('');
  const [approvedCount, setApprovedCount] = useState(0);

  useEffect(() => {
    if (!selectedCorridor) return;
    setTrains(CORRIDORS[selectedCorridor].trains);

    // Simulate live updates every 2 seconds
    const interval = setInterval(() => {
      setTrains(prev => prev.map(t => ({
        ...t,
        speed: Math.max(10, t.speed + Math.floor((Math.random() - 0.5) * 10)),
        lat: t.lat + (Math.random() - 0.5) * 0.02,
        lng: t.lng + (Math.random() - 0.5) * 0.02,
        delay: Math.max(0, t.delay + Math.floor((Math.random() - 0.5) * 2)),
      })));
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedCorridor]);

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

  const filteredCorridors = Object.keys(CORRIDORS).filter(k =>
    CORRIDORS[k].name.toLowerCase().includes(search.toLowerCase()) ||
    CORRIDORS[k].from.toLowerCase().includes(search.toLowerCase()) ||
    CORRIDORS[k].to.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{
      background: '#0a0a0a', color: 'white',
      minHeight: '100vh', fontFamily: 'monospace',
      position: 'relative'
    }}>

      {/* WATERMARK */}
      <img src="/logo-watermark.png" alt="" style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        width: '500px', height: '500px',
        objectFit: 'contain', opacity: 0.04,
        pointerEvents: 'none', zIndex: 0
      }} />

      {/* HEADER */}
      <div style={{
        padding: '10px 20px', borderBottom: '1px solid #222',
        display: 'flex', alignItems: 'center', gap: '15px',
        position: 'relative', zIndex: 2
      }}>
        <button onClick={onBack} style={{
          background: '#222', border: '1px solid #333',
          color: '#aaa', padding: '6px 14px',
          borderRadius: '6px', cursor: 'pointer',
          fontFamily: 'monospace', fontSize: '13px'
        }}>← Back</button>
        <Logo />
        <h2 style={{ margin: 0, fontSize: '16px', color: '#aaa' }}>
          CORRIDOR CONTROL
        </h2>
        {selectedCorridor && (
          <button onClick={handleOptimizeAll} style={{
            background: '#00ff88', color: '#000',
            border: 'none', borderRadius: '6px',
            padding: '6px 16px', cursor: 'pointer',
            fontWeight: 'bold', fontFamily: 'monospace',
            fontSize: '13px', marginLeft: 'auto'
          }}>
            ⚡ OPTIMIZE CORRIDOR
          </button>
        )}
      </div>

      <div style={{ display: 'flex', position: 'relative', zIndex: 2 }}>

        {/* LEFT - CORRIDOR LIST */}
        <div style={{
          width: '280px', borderRight: '1px solid #222',
          padding: '15px'
        }}>
          <div style={{ marginBottom: '15px' }}>
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search corridor..."
              style={{
                width: '100%', background: '#111',
                border: '1px solid #333', borderRadius: '8px',
                padding: '8px 12px', color: 'white',
                fontFamily: 'monospace', fontSize: '13px',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div style={{ fontSize: '11px', color: '#666', letterSpacing: '2px', marginBottom: '10px' }}>
            SELECT CORRIDOR
          </div>

          {filteredCorridors.map(key => (
            <div key={key} onClick={() => setSelectedCorridor(key)}
              style={{
                background: selectedCorridor === key ? '#1a1a1a' : 'transparent',
                border: `1px solid ${selectedCorridor === key ? '#ff4444' : '#222'}`,
                borderRadius: '8px', padding: '12px',
                marginBottom: '8px', cursor: 'pointer'
              }}>
              <div style={{ fontWeight: 'bold', fontSize: '13px', marginBottom: '4px' }}>
                🚂 {CORRIDORS[key].name}
              </div>
              <div style={{ fontSize: '11px', color: '#aaa' }}>
                Distance: {CORRIDORS[key].distance}<br />
                Trains: {CORRIDORS[key].trains.length}
              </div>
            </div>
          ))}

          {/* Stats */}
          {approvedCount > 0 && (
            <div style={{
              marginTop: '20px', background: '#111',
              border: '1px solid #00ff88', borderRadius: '8px',
              padding: '12px'
            }}>
              <div style={{ fontSize: '10px', color: '#00ff88', letterSpacing: '2px' }}>
                AI DECISIONS TODAY
              </div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#00ff88' }}>
                {approvedCount}
              </div>
              <div style={{ fontSize: '11px', color: '#aaa' }}>
                approvals made
              </div>
            </div>
          )}
        </div>

        {/* RIGHT - TRAIN LIST */}
        <div style={{ flex: 1, padding: '15px' }}>
          {!selectedCorridor ? (
            <div style={{
              display: 'flex', alignItems: 'center',
              justifyContent: 'center', height: '60vh',
              color: '#444', fontSize: '16px'
            }}>
              ← Select a corridor to view trains
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
                {[
                  { label: 'TOTAL', val: trains.length, color: '#fff' },
                  { label: 'ON TIME', val: trains.filter(t => t.status === 'on_time').length, color: '#00ff88' },
                  { label: 'DELAYED', val: trains.filter(t => t.status === 'delayed').length, color: '#ff4444' },
                  { label: 'AT RISK', val: trains.filter(t => t.status === 'at_risk').length, color: '#ffaa00' },
                ].map(s => (
                  <div key={s.label} style={{
                    flex: 1, background: '#111', border: '1px solid #222',
                    borderRadius: '8px', padding: '10px'
                  }}>
                    <div style={{ fontSize: '10px', color: '#666', letterSpacing: '2px' }}>{s.label}</div>
                    <div style={{ fontSize: '22px', fontWeight: 'bold', color: s.color }}>{s.val}</div>
                  </div>
                ))}
              </div>

              {/* Train cards */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {trains.map(train => (
                  <div key={train.id} style={{
                    background: '#111',
                    border: `1px solid ${getColor(train.status)}`,
                    borderRadius: '8px', padding: '12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ fontWeight: 'bold' }}>🚂 {train.id}</div>
                      <span style={{
                        background: getColor(train.status),
                        color: '#000', padding: '2px 8px',
                        borderRadius: '10px', fontSize: '10px', fontWeight: 'bold'
                      }}>
                        {train.status.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: '#ccc', marginBottom: '4px' }}>
                      {train.name}
                    </div>
                    <div style={{ fontSize: '11px', color: '#aaa', lineHeight: 1.8 }}>
                      🏎️ Speed: {train.speed} km/h<br />
                      ⏱️ Delay: {train.delay} mins<br />
                      🛤️ {train.track}<br />
                      {getWeatherIcon(train.weather)} Weather: {train.weather}<br />
                      🕐 ETA: {train.eta}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
                      <button onClick={() => handleApprove(train.id)}
                        style={{ background: '#00ff88', color: '#000', border: 'none', borderRadius: '4px', padding: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace' }}>
                        ✅ APPROVE AI
                      </button>
                      <button onClick={() => alert(`✋ Override set for ${train.id}`)}
                        style={{ background: '#ffaa00', color: '#000', border: 'none', borderRadius: '4px', padding: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace' }}>
                        ✋ OVERRIDE
                      </button>
                      <button onClick={() => alert(`📡 MRDC sent to ${train.name}`)}
                        style={{ background: '#1a6fff', color: '#fff', border: 'none', borderRadius: '4px', padding: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace' }}>
                        📡 MRDC SEND
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default CorridorPage;