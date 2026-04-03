import { useEffect } from 'react';

const MapView = () => {
  useEffect(() => {
    const L = window.L;
    if (!L) return;

    const map = L.map('map').setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    L.marker([19.0760, 72.8777])
      .addTo(map)
      .bindPopup('🚂 Train TN001');

    return () => map.remove();
  }, []);

  return <div id="map" style={{ height: '100vh', width: '100%' }} />;
};

export default MapView;