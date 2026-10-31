import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { INDIA_CENTER, INDIA_ZOOM } from '../utils/format';

// Leaflet's default icon URLs break under bundlers; point them at the CDN copies.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const hasCoord = (v) => typeof v === 'number' && !Number.isNaN(v);
// Restrict the viewport to India (plus margin) so the map never wanders to other countries.
const INDIA_BOUNDS = [[2, 60], [40, 100]];

const LeafletMap = ({ latitude, longitude, zoom = 16, onLocationSelect, editable = false, popupText = 'Property Location' }) => {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const onSelectRef = useRef(onLocationSelect);
  onSelectRef.current = onLocationSelect; // avoid stale click handlers

  const located = hasCoord(latitude) && hasCoord(longitude);

  // create / destroy the map exactly once per mount
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const center = located ? [latitude, longitude] : INDIA_CENTER;
    const map = L.map(containerRef.current, { maxBounds: INDIA_BOUNDS, minZoom: 4 }).setView(center, located ? zoom : INDIA_ZOOM);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);
    if (editable) {
      map.on('click', (e) => {
        const { lat, lng } = e.latlng;
        if (!markerRef.current) markerRef.current = L.marker([lat, lng]).addTo(map);
        else markerRef.current.setLatLng([lat, lng]);
        markerRef.current.bindPopup(`<b>Selected coordinate</b><br/>${lat.toFixed(5)}, ${lng.toFixed(5)}`).openPopup();
        if (onSelectRef.current) onSelectRef.current(lat, lng);
      });
    }
    mapRef.current = map;
    // containers inside flex/grid/tab layouts often have 0 size at mount; fix tiles once laid out
    const t = setTimeout(() => map.invalidateSize(), 150);
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => map.invalidateSize()) : null;
    if (ro) ro.observe(containerRef.current);
    return () => {
      clearTimeout(t);
      if (ro) ro.disconnect();
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // keep marker/view in sync with props
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !located) return;
    if (!markerRef.current) markerRef.current = L.marker([latitude, longitude]).addTo(map);
    else markerRef.current.setLatLng([latitude, longitude]);
    markerRef.current.bindPopup(`<b>${popupText}</b><br/>${latitude.toFixed(5)}, ${longitude.toFixed(5)}`);
    map.setView([latitude, longitude], Math.max(map.getZoom(), zoom > 12 ? 15 : zoom));
  }, [latitude, longitude, zoom, popupText, located]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '260px', borderRadius: '12px', overflow: 'hidden' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%', minHeight: '260px' }} />
      {editable && (
        <div style={{ position: 'absolute', bottom: '10px', left: '10px', zIndex: 1000, background: 'rgba(15, 23, 42, 0.85)', padding: '4px 10px', borderRadius: '6px', fontSize: '0.75rem', color: '#6ee7a8', pointerEvents: 'none' }}>
          Click the map to place the pin
        </div>
      )}
    </div>
  );
};

export default LeafletMap;
