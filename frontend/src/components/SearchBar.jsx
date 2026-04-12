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
    <div style={{ position: 'relative', width: '280px' }}>
      
      {/* Search bar container */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: '#2a2a2a',
        borderRadius: '20px',
        padding: '5px 12px',
        gap: '8px',
        border: '1px solid #3a3a3a'
      }}>
        {/* Search icon */}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>

        {/* Input */}
        <input
          type="text"
          value={query}
          onChange={handleSearch}
          placeholder="Search station"
          style={{
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#fff',
            fontFamily: 'Arial, sans-serif',
            fontSize: '13px',
            width: '100%',
            letterSpacing: '0.3px'
          }}
        />
      </div>

      {/* Dropdown results */}
      {results.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '110%',
          left: 0,
          right: 0,
          background: '#1a1a1a',
          border: '1px solid #333',
          borderRadius: '10px',
          marginTop: '4px',
          zIndex: 1000,
          overflow: 'hidden'
        }}>
          {results.map(station => (
            <div
              key={station.id}
              onClick={() => handleSelect(station)}
              style={{
                padding: '8px 14px',
                cursor: 'pointer',
                fontSize: '13px',
                borderBottom: '1px solid #222',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontFamily: 'Arial, sans-serif'
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#222'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <span>🚉 {station.name}</span>
              <span style={{
                fontSize: '10px',
                color: station.congestion >= 0.85 ? '#ff4444' : 
                       station.congestion >= 0.60 ? '#ffaa00' : '#00ff88'
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