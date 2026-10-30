import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

// Fix Leaflet's default icon path issue with bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const LeafletMap = ({
  latitude,
  longitude,
  zoom = 16,
  onLocationSelect,
  editable = false,
  popupText = 'Property Location'
}) => {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerRef = useRef(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    const lat = latitude || 33.7749;
    const lon = longitude || -84.3541;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current).setView([lat, lon], zoom);
      
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      const marker = L.marker([lat, lon]).addTo(map);
      marker.bindPopup(`<b>${popupText}</b><br/>${lat.toFixed(5)}, ${lon.toFixed(5)}`);
      
      if (editable && onLocationSelect) {
        map.on('click', (e) => {
          const { lat: clickLat, lng: clickLon } = e.latlng;
          marker.setLatLng([clickLat, clickLon]);
          marker.setPopupContent(`<b>Selected Coordinate</b><br/>${clickLat.toFixed(5)}, ${clickLon.toFixed(5)}`).openPopup();
          onLocationSelect(clickLat, clickLon);
        });
      }

      mapInstanceRef.current = map;
      markerRef.current = marker;
    } else {
      // Update existing map view & marker
      const map = mapInstanceRef.current;
      const marker = markerRef.current;
      map.setView([lat, lon], zoom);
      if (marker) {
        marker.setLatLng([lat, lon]);
        marker.setPopupContent(`<b>${popupText}</b><br/>${lat.toFixed(5)}, ${lon.toFixed(5)}`);
      }
    }

    return () => {
      // cleanup on unmount
    };
  }, [latitude, longitude, zoom, editable, popupText]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '260px', borderRadius: '12px', overflow: 'hidden' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />
      {editable && (
        <div style={{ position: 'absolute', bottom: '10px', left: '10px', zIndex: 1000, background: 'rgba(15, 23, 42, 0.85)', padding: '4px 10px', borderRadius: '6px', fontSize: '0.75rem', color: '#6ee7a8', backdropFilter: 'blur(4px)', pointerEvents: 'none' }}>
          Click anywhere on map to reposition coordinates pin
        </div>
      )}
    </div>
  );
};

export default LeafletMap;
