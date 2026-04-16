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

const CUSTOM_STATION_ICONS = {
  12: '/station-kolkata.png',    // Howrah Jn - Kolkata
  13: '/station-delhi.png',       // New Delhi
  14: '/station-mumbai.png',      // Mumbai CST
  15: '/station-chennai.png',     // Chennai Central
  17: '/station-hyderabad.png',   // Hyderabad Deccan
  23: '/station-jaipur.png',      // Jaipur Jn
  26: '/station-agra.png',        // Agra Cantt
  80: '/station-amritsar.png',    // Amritsar Jn
};

// Adjustable icon sizes - modify these to change map marker size
const ICON_SIZES = {
  custom: { width: 34, height: 34 },      // Delhi, Mumbai, Kolkata, Chennai, Hyderabad, Jaipur
  default: { width: 32, height: 32 },      // 94 remaining stations - ADJUST THIS!
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
      let stationIcon;

      // Check if station has custom icon
      if (CUSTOM_STATION_ICONS[station.id]) {
        stationIcon = L.icon({
          iconUrl: CUSTOM_STATION_ICONS[station.id],
          iconSize: [ICON_SIZES.custom.width, ICON_SIZES.custom.height],
          iconAnchor: [ICON_SIZES.custom.width / 2, ICON_SIZES.custom.height / 2],
          popupAnchor: [0, -ICON_SIZES.custom.height / 2],
        });
      } else {
        // Use default icon for other 90 stations
        stationIcon = L.icon({
          iconUrl: '/station-default.png',
          iconSize: [ICON_SIZES.default.width, ICON_SIZES.default.height],
          iconAnchor: [ICON_SIZES.default.width / 2, ICON_SIZES.default.height / 2],
          popupAnchor: [0, -ICON_SIZES.default.height / 2],
        });
      }

      const marker = L.marker(
        [station.lat, station.lng],
        { icon: stationIcon }
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

    window.selectStation = (id) => {
      const station = STATIONS.find(s => s.id === id);
      if (onStationClick) onStationClick(station);
    };
  }, []);

  // Update train markers with custom icon
  useEffect(() => {
    if (!mapRef.current) return;
    trains.forEach(train => {
      if (markersRef.current[train.id]) {
        markersRef.current[train.id].remove();
      }

      const color = getColor(train.status);

     const trainIcon = L.divIcon({
  html: `<div style="
    width: 32px;
    height: 32px;
    filter: hue-rotate(${
      train.status === 'on_time' ? '120deg' : 
      train.status === 'delayed' ? '0deg' : 
      '40deg'
    }) saturate(2) brightness(1.2);
  ">
    <img src="/train-icon.png" 
      style="width:32px;height:32px;object-fit:contain;"
    />
  </div>`,
  className: '',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
});

      markersRef.current[train.id] = L.marker(
        [train.lat, train.lng],
        { icon: trainIcon }
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