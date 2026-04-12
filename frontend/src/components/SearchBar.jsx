import { useState } from 'react';
import STATIONS from '../data/stations';

const SearchBar = ({ onStationSelect }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  const handleSearch = (e) => {
    const val = e.target.value;
    setQuery(val);
    if (val.length < 2) { setResults([]); return; }
    const filtered = STATIONS.filter(s =>
      s.name.toLowerCase().includes(val.toLowerCase())
    ).slice(0, 5);
    setResults(filtered);
  };

  const handleSelect = (station) => {
    setQuery('');
    setResults([]);
    onStationSelect(station);
  };

  return (
    <div style={{ position: 'relative', width: '300px' }}>
      <input
        type="text"
        value={query}
        onChange={handleSearch}
        placeholder="🔍 Search station..."
        style={{
          width: '100%',
          background: '#111',
          border: '1px solid #333',
          borderRadius: '8px',
          padding: '8px 12px',
          color: 'white',
          fontFamily: 'monospace',
          fontSize: '13px',
          boxSizing: 'border-box'
        }}
      />
      {results.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          background: '#111',
          border: '1px solid #333',
          borderRadius: '8px',
          marginTop: '4px',
          zIndex: 1000
        }}>
          {results.map(station => (
            <div
              key={station.id}
              onClick={() => handleSelect(station)}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                fontSize: '13px',
                borderBottom: '1px solid #222',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#222'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <span>🚉 {station.name}</span>
              <span style={{
                fontSize: '10px',
                color: station.congestion >= 0.85 ? '#ff4444' : station.congestion >= 0.60 ? '#ffaa00' : '#00ff88'
              }}>
                {Math.round(station.congestion * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchBar;
