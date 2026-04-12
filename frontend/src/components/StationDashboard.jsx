import Logo from './Logo';
import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';

const STATION_TRAINS = {
  0: [
    { id: 'TN001', speed: 60, delay: 0, status: 'on_time' },
    { id: 'TN002', speed: 30, delay: 8, status: 'delayed' },
    { id: 'TN003', speed: 45, delay: 3, status: 'at_risk' },
    { id: 'TN004', speed: 55, delay: 0, status: 'on_time' },
    { id: 'TN005', speed: 20, delay: 12, status: 'delayed' },
  ],
  4: [
    { id: 'TN006', speed: 50, delay: 5, status: 'at_risk' },
    { id: 'TN007', speed: 25, delay: 15, status: 'delayed' },
    { id: 'TN008', speed: 60, delay: 0, status: 'on_time' },
  ],
  13: [
    { id: 'TN009', speed: 40, delay: 10, status: 'delayed' },
    { id: 'TN010', speed: 60, delay: 0, status: 'on_time' },
    { id: 'TN011', speed: 35, delay: 6, status: 'at_risk' },
    { id: 'TN012', speed: 60, delay: 0, status: 'on_time' },
  ],
  14: [
    { id: 'TN013', speed: 55, delay: 2, status: 'at_risk' },
    { id: 'TN014', speed: 60, delay: 0, status: 'on_time' },
    { id: 'TN015', speed: 60, delay: 0, status: 'on_time' },
  ],
  7: [
    { id: 'TN016', speed: 30, delay: 9, status: 'delayed' },
    { id: 'TN017', speed: 60, delay: 0, status: 'on_time' },
    { id: 'TN018', speed: 45, delay: 4, status: 'at_risk' },
  ],
  15: [
    { id: 'TN019', speed: 55, delay: 0, status: 'on_time' },
    { id: 'TN020', speed: 30, delay: 7, status: 'delayed' },
    { id: 'TN021', speed: 45, delay: 3, status: 'at_risk' },
    { id: 'TN022', speed: 60, delay: 0, status: 'on_time' },
  ],
  16: [
    { id: 'TN023', speed: 60, delay: 0, status: 'on_time' },
    { id: 'TN024', speed: 35, delay: 5, status: 'at_risk' },
    { id: 'TN025', speed: 25, delay: 11, status: 'delayed' },
  ],
  17: [
    { id: 'TN026', speed: 60, delay: 0, status: 'on_time' },
    { id: 'TN027', speed: 40, delay: 6, status: 'delayed' },
    { id: 'TN028', speed: 50, delay: 2, status: 'at_risk' },
    { id: 'TN029', speed: 60, delay: 0, status: 'on_time' },
  ],
  12: [
    { id: 'TN030', speed: 30, delay: 14, status: 'delayed' },
    { id: 'TN031', speed: 60, delay: 0, status: 'on_time' },
    { id: 'TN032', speed: 45, delay: 4, status: 'at_risk' },
    { id: 'TN033', speed: 60, delay: 0, status: 'on_time' },
  ],
  23: [
    { id: 'TN034', speed: 55, delay: 0, status: 'on_time' },
    { id: 'TN035', speed: 30, delay: 8, status: 'delayed' },
    { id: 'TN036', speed: 60, delay: 0, status: 'on_time' },
  ],
};

const getStationTrains = (stationId) => {
  if (STATION_TRAINS[stationId]) return STATION_TRAINS[stationId];
  const count = Math.floor(Math.random() * 4) + 2;
  return Array.from({ length: count }, (_, i) => ({
    id: `TN${stationId}${i}`,
    speed: Math.random() > 0.5 ? 60 : Math.floor(Math.random() * 40 + 20),
    delay: Math.random() > 0.6 ? 0 : Math.floor(Math.random() * 10 + 1),
    status: Math.random() > 0.6 ? 'on_time' : Math.random() > 0.5 ? 'delayed' : 'at_risk'
  }));
};

const getColor = (status) => {
  if (status === 'on_time') return '#00ff88';
  if (status === 'delayed') return '#ff4444';
  return '#ffaa00';
};

const StationDashboard = ({ station, onBack }) => {
  const svgRef = useRef(null);
  const [localTrains, setLocalTrains] = useState(getStationTrains(station.id));
  const localConflicts = localTrains.filter(t => t.status !== 'on_time');

  useEffect(() => {
    if (!svgRef.current || !localTrains.length) return;
    const width = 380;
    const height = 160;
    const margin = { top: 20, right: 10, bottom: 30, left: 45 };

    d3.select(svgRef.current).selectAll('*').remove();
    const svg = d3.select(svgRef.current)
      .attr('width', width).attr('height', height);

    const x = d3.scaleBand()
      .domain(localTrains.map(d => d.id))
      .range([margin.left, width - margin.right])
      .padding(0.3);

    const y = d3.scaleLinear()
      .domain([0, d3.max(localTrains, d => d.delay) + 5])
      .range([height - margin.bottom, margin.top]);

    svg.selectAll('rect')
      .data(localTrains).join('rect')
      .attr('x', d => x(d.id))
      .attr('y', d => y(d.delay))
      .attr('width', x.bandwidth())
      .attr('height', d => y(0) - y(d.delay))
      .attr('fill', d => getColor(d.status))
      .attr('rx', 4);

    svg.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
      .style('fill', '#aaa').style('font-size', '10px');

    svg.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(4))
      .selectAll('text')
      .style('fill', '#aaa');

    svg.selectAll('.domain, .tick line').style('stroke', '#444');
  }, [localTrains]);

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
        width: '500px', height: '500px',
        objectFit: 'contain', opacity: 0.04,
        pointerEvents: 'none'
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
        <h2 style={{ margin: 0, fontSize: '18px' }}>
          🚉 {station.name}
        </h2>
        <span style={{
          background: station.congestion >= 0.85 ? '#ff4444' : station.congestion >= 0.60 ? '#ffaa00' : '#00ff88',
          color: '#000', padding: '3px 10px',
          borderRadius: '20px', fontSize: '11px', fontWeight: 'bold'
        }}>
          {Math.round(station.congestion * 100)}% CONGESTED
        </span>
        <button onClick={() => {
          setLocalTrains(prev => prev.map(t => ({
            ...t, status: 'on_time', delay: 0, speed: 60
          })));
        }} style={{
          background: '#00ff88', color: '#000',
          border: 'none', borderRadius: '6px',
          padding: '6px 16px', cursor: 'pointer',
          fontWeight: 'bold', fontFamily: 'monospace',
          fontSize: '13px', marginLeft: 'auto'
        }}>
          ⚡ OPTIMIZE STATION
        </button>
      </div>

      {/* STAT CARDS */}
      <div style={{
        display: 'flex', gap: '10px', padding: '15px 20px',
        position: 'relative', zIndex: 2
      }}>
        {[
          { label: 'TOTAL TRAINS', val: station.trains, color: '#fff' },
          { label: 'DELAYED', val: localTrains.filter(t => t.status === 'delayed').length, color: '#ff4444' },
          { label: 'AT RISK', val: localTrains.filter(t => t.status === 'at_risk').length, color: '#ffaa00' },
          { label: 'ON TIME', val: localTrains.filter(t => t.status === 'on_time').length, color: '#00ff88' },
        ].map(s => (
          <div key={s.label} style={{
            flex: 1, background: '#111', border: '1px solid #222',
            borderRadius: '8px', padding: '10px 15px'
          }}>
            <div style={{ fontSize: '10px', color: '#666', letterSpacing: '2px', marginBottom: '4px' }}>
              {s.label}
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: s.color }}>
              {s.val}
            </div>
          </div>
        ))}
      </div>

      {/* MAIN CONTENT */}
      <div style={{ display: 'flex', position: 'relative', zIndex: 2 }}>

        {/* LEFT - CHART */}
        <div style={{ flex: 1, padding: '0 20px' }}>
          <div style={{ fontSize: '11px', color: '#ff4444', letterSpacing: '2px', marginBottom: '10px' }}>
            DELAY CHART (mins)
          </div>
          <div style={{ background: '#111', borderRadius: '8px', padding: '10px' }}>
            <svg ref={svgRef} />
          </div>
        </div>

        {/* RIGHT - CONFLICTS */}
        <div style={{
          width: '280px', borderLeft: '1px solid #222',
          padding: '0 15px', maxHeight: '60vh', overflowY: 'auto'
        }}>
          <div style={{ fontSize: '11px', color: '#ff4444', letterSpacing: '2px', marginBottom: '10px' }}>
            CONFLICT ALERTS ({localConflicts.length})
          </div>

          {localConflicts.length === 0 ? (
            <div style={{ color: '#00ff88', fontSize: '13px' }}>✅ All trains running smoothly!</div>
          ) : localConflicts.map(train => (
            <div key={train.id} style={{
              background: '#1a1a1a',
              border: `1px solid ${getColor(train.status)}`,
              borderRadius: '8px', padding: '10px', marginBottom: '8px'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>🚂 {train.id}</div>
              <div style={{ fontSize: '11px', color: '#aaa', lineHeight: 1.6 }}>
                Status: <span style={{ color: getColor(train.status) }}>{train.status.toUpperCase()}</span><br />
                Delay: {train.delay} mins | Speed: {train.speed} km/h
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
                <button onClick={() => setLocalTrains(prev => prev.map(t =>
                  t.id === train.id ? { ...t, status: 'on_time', delay: 0, speed: 60 } : t
                ))} style={{ background: '#00ff88', color: '#000', border: 'none', borderRadius: '4px', padding: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace' }}>
                  ✅ APPROVE AI
                </button>
                <button onClick={() => {
                  setLocalTrains(prev => prev.map(t =>
                    t.id === train.id ? { ...t, status: 'at_risk', delay: 2 } : t
                  ));
                  alert(`✋ Override set for ${train.id}`);
                }} style={{ background: '#ffaa00', color: '#000', border: 'none', borderRadius: '4px', padding: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace' }}>
                  ✋ OVERRIDE MANUAL
                </button>
                <button onClick={() => alert(`📡 MRDC sent for ${train.id}`)}
                  style={{ background: '#1a6fff', color: '#fff', border: 'none', borderRadius: '4px', padding: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', fontFamily: 'monospace' }}>
                  📡 MRDC SEND
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default StationDashboard;
