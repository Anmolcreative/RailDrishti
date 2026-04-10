import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import STATIONS from '../data/stations';

const getColor = (status) => {
  if (status === 'on_time') return '#00ff88';
  if (status === 'delayed') return '#ff4444';
  return '#ffaa00';
};

const getStationColor = (congestion) => {
  if (congestion >= 0.85) return '#ff4444';
  if (congestion >= 0.60) return '#ffaa00';
  return '#00ff88';
};

const MapView = ({ trains = [], onStationClick }) => {
  const mapRef = useRef(null);
  const markersRef = useRef({});
  const stationMarkersRef = useRef([]);

  // Initialize map
  useEffect(() => {
    mapRef.current = L.map('map').setView([22.5, 78.9629], 5);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO'
    }).addTo(mapRef.current);
    return () => mapRef.current.remove();
  }, []);

  // Add station markers
  useEffect(() => {
    if (!mapRef.current) return;

    STATIONS.forEach(station => {
      const marker = L.circleMarker(
        [station.lat, station.lng],
        {
          color: getStationColor(station.congestion),
          fillColor: getStationColor(station.congestion),
          radius: 8,
          fillOpacity: 0.5,
          weight: 2,
          dashArray: '4'
        }
      )
      .addTo(mapRef.current)
      .bindPopup(`
        <b>🚉 ${station.name}</b><br/>
        Trains: ${station.trains}<br/>
        Congestion: ${Math.round(station.congestion * 100)}%<br/>
        <button onclick="window.selectStation(${station.id})"
          style="margin-top:6px; background:#ff4444; color:white; 
                 border:none; padding:4px 10px; border-radius:4px; cursor:pointer">
          View Station
        </button>
      `);

      stationMarkersRef.current.push(marker);
    });

    // Global function for popup button click
    window.selectStation = (id) => {
      const station = STATIONS.find(s => s.id === id);
      if (onStationClick) onStationClick(station);
    };
  }, []);

  // Update train markers
  useEffect(() => {
    if (!mapRef.current) return;
    trains.forEach(train => {
      if (markersRef.current[train.id]) {
        markersRef.current[train.id].remove();
      }
      markersRef.current[train.id] = L.circleMarker(
        [train.lat, train.lng],
        { color: getColor(train.status), fillColor: getColor(train.status), radius: 10, fillOpacity: 0.9, weight: 2 }
      )
      .addTo(mapRef.current)
      .bindPopup(`
        <b>🚂 ${train.id}</b><br/>
        Speed: ${train.speed} km/h<br/>
        Delay: ${train.delay} mins<br/>
        Status: ${train.status}
      `);
    });
  }, [trains]);

  return <div id="map" style={{ height: '60vh', width: '100%' }} />;
};

export default MapView;