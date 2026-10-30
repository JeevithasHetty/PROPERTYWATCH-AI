import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import {
  MapPin,
  Satellite,
  Crosshair,
  Maximize2
} from 'lucide-react';

// Fix Leaflet's default icon path issue with Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const DashboardMap = ({ properties = [] }) => {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({});
  const [selectedPropertyId, setSelectedPropertyId] = useState(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Filter valid coordinates
    const validProps = properties.filter(
      (p) => typeof p.latitude === 'number' && typeof p.longitude === 'number' && !isNaN(p.latitude) && !isNaN(p.longitude)
    );

    // Initial center (default Atlanta or first property)
    const initialLat = validProps.length > 0 ? validProps[0].latitude : 33.7749;
    const initialLon = validProps.length > 0 ? validProps[0].longitude : -84.3541;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        scrollWheelZoom: true,
        zoomControl: true,
      }).setView([initialLat, initialLon], 6);

      // OpenStreetMap Tiles with Attribution
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      mapInstanceRef.current = map;
    }

    const map = mapInstanceRef.current;

    // Clear previous markers
    Object.values(markersRef.current).forEach((m) => map.removeLayer(m));
    markersRef.current = {};

    const markerGroup = [];

    validProps.forEach((prop) => {
      const popupContent = document.createElement('div');
      popupContent.style.fontFamily = 'var(--font-sans, sans-serif)';
      popupContent.style.padding = '4px';
      popupContent.style.color = '#0f172a';
      popupContent.innerHTML = `
        <div style="font-weight: 700; font-size: 0.95rem; color: #22a866; margin-bottom: 2px;">
          ${prop.property_reference}
        </div>
        <div style="font-size: 0.82rem; font-weight: 600; color: #1e293b; margin-bottom: 4px;">
          ${prop.address}
        </div>
        <div style="font-size: 0.75rem; color: #64748b; margin-bottom: 8px;">
          ${prop.city ? prop.city + ', ' : ''}${prop.state || ''} ${prop.postal_code || ''}
        </div>
        <div style="font-size: 0.74rem; background: #f1f5f9; padding: 4px 6px; border-radius: 4px; margin-bottom: 8px;">
          <b>Owner:</b> ${prop.owner_name}<br/>
          <b>Area:</b> ${prop.built_up_area ? prop.built_up_area.toLocaleString() + ' sq ft' : 'N/A'}<br/>
          <b>Type:</b> ${prop.property_type || 'Residential'}
        </div>
        <div style="display: flex; gap: 6px; margin-top: 6px;">
          <a href="/properties/${prop.id}" style="display: inline-block; padding: 4px 8px; background: #22a866; color: #fff; text-decoration: none; border-radius: 4px; font-size: 0.72rem; font-weight: 600;">
            View property
          </a>
          <a href="/satellite?property_id=${prop.id}" style="display: inline-block; padding: 4px 8px; background: #0f172a; color: #6ee7a8; text-decoration: none; border-radius: 4px; font-size: 0.72rem; font-weight: 600;">
            Find photos
          </a>
        </div>
      `;

      const marker = L.marker([prop.latitude, prop.longitude]).addTo(map);
      marker.bindPopup(popupContent, { minWidth: 220 });

      marker.on('click', () => {
        setSelectedPropertyId(prop.id);
      });

      markersRef.current[prop.id] = marker;
      markerGroup.push(marker);
    });

    // Auto-fit bounds if we have markers
    if (markerGroup.length > 0) {
      const group = L.featureGroup(markerGroup);
      map.fitBounds(group.getBounds().pad(0.2), { maxZoom: 15 });
    }
  }, [properties]);

  const handleFlyTo = (prop) => {
    setSelectedPropertyId(prop.id);
    if (mapInstanceRef.current && prop.latitude && prop.longitude) {
      mapInstanceRef.current.flyTo([prop.latitude, prop.longitude], 16, {
        duration: 1.2,
      });
      const marker = markersRef.current[prop.id];
      if (marker) {
        marker.openPopup();
      }
    }
  };

  const handleFitAll = () => {
    if (!mapInstanceRef.current) return;
    const markers = Object.values(markersRef.current);
    if (markers.length > 0) {
      const group = L.featureGroup(markers);
      mapInstanceRef.current.fitBounds(group.getBounds().pad(0.2));
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '24px', overflow: 'hidden' }}>
      {/* Header Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MapPin size={20} color="#6ee7a8" />
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
              Property locations
            </h3>
          </div>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Select a marker or a property in the list to see its location and details.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span className="badge badge-cyan" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Satellite size={12} />
            <span>Map view</span>
          </span>
          <span className="badge badge-green" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>OpenStreetMap</span>
          </span>
          <button
            onClick={handleFitAll}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
            title="Show all properties on the map"
          >
            <Maximize2 size={13} />
            <span>Show all ({properties.length})</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Map (70%) + Property Quick Selector (30%) */}
      <div className="dashboard-map-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 280px', gap: '16px', minHeight: '440px' }}>
        {/* Leaflet Map Canvas */}
        <div
          style={{
            position: 'relative',
            borderRadius: '12px',
            overflow: 'hidden',
            border: '1px solid var(--border-subtle)',
            minHeight: '440px',
            boxShadow: '0 8px 30px rgba(0, 0, 0, 0.45)'
          }}
        >
          <div ref={mapContainerRef} style={{ width: '100%', height: '100%', minHeight: '440px' }} />

          {/* Map Overlay Badge */}
          <div
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              zIndex: 1000,
              background: 'rgba(15, 23, 42, 0.88)',
              backdropFilter: 'blur(8px)',
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid rgba(110, 231, 168, 0.3)',
              fontSize: '0.74rem',
              color: '#6ee7a8',
              pointerEvents: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Crosshair size={13} />
            <span>Select a marker to view this property</span>
          </div>
        </div>

        {/* Property Quick Navigation Sidebar */}
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.65)',
            border: '1px solid var(--border-glass)',
            borderRadius: '12px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            maxHeight: '440px',
            overflowY: 'auto'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#e2e8f0' }}>Properties</span>
            <span className="badge badge-gray" style={{ fontSize: '0.7rem' }}>{properties.length} total</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto' }}>
            {properties.map((prop) => {
              const isSelected = selectedPropertyId === prop.id;
              return (
                <div
                  key={prop.id}
                  onClick={() => handleFlyTo(prop)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      handleFlyTo(prop);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(34, 168, 102, 0.18)' : 'rgba(30, 41, 59, 0.4)',
                    border: `1px solid ${isSelected ? '#6ee7a8' : 'rgba(51, 65, 85, 0.3)'}`,
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.84rem', color: isSelected ? '#6ee7a8' : '#f8fafc' }}>
                      {prop.property_reference}
                    </span>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>
                      {prop.state || 'US'}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {prop.address}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px', fontSize: '0.7rem' }}>
                    <span style={{ color: 'var(--text-dim)' }}>{prop.owner_name}</span>
                    <span style={{ color: '#6ee7a8', fontWeight: 600 }}>Show on map →</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardMap;
