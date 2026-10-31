import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import apiClient from '../api/client';
import ImageSlider from '../components/ImageSlider';
import {
  Satellite,
  Search,
  Calendar,
  Cloud,
  CheckCircle2,
  AlertTriangle,
  DownloadCloud,
  Layers,
  ArrowRight,
  Info
} from 'lucide-react';

const SatelliteMonitoringPage = () => {
  const [searchParams] = useSearchParams();
  const initialPropertyId = searchParams.get('property_id') || '';

  const [properties, setProperties] = useState([]);
  const [selectedPropertyId, setSelectedPropertyId] = useState(initialPropertyId);
  const [selectedProperty, setSelectedProperty] = useState(null);

  // Search parameters
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [maxCloudCover, setMaxCloudCover] = useState(20);

  // Results & Snapshots
  const [searchResults, setSearchResults] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [searching, setSearching] = useState(false);
  const [retrievingId, setRetrievingId] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  // Active comparison state
  const [baselineSnapshot, setBaselineSnapshot] = useState(null);
  const [comparisonSnapshot, setComparisonSnapshot] = useState(null);

  // Fetch properties list
  useEffect(() => {
    const loadProps = async () => {
      try {
        const res = await apiClient.getProperties();
        setProperties(res.data);
        if (res.data.length > 0 && !selectedPropertyId) {
          setSelectedPropertyId(res.data[0].id.toString());
        }
      } catch (err) {
        console.error('Failed to load properties', err);
      }
    };
    loadProps();
  }, []);

  // When selected property changes, fetch its full detail & snapshots
  useEffect(() => {
    if (!selectedPropertyId) return;
    const loadSelectedProp = async () => {
      try {
        const res = await apiClient.getProperty(selectedPropertyId);
        setSelectedProperty(res.data);
        setSnapshots(res.data.snapshots || []);

        const base = res.data.snapshots?.find((s) => s.is_baseline);
        setBaselineSnapshot(base || res.data.snapshots?.[0] || null);

        const comp = res.data.snapshots?.find((s) => !s.is_baseline);
        setComparisonSnapshot(comp || null);
      } catch (err) {
        console.error('Failed to load property detail', err);
      }
    };
    loadSelectedProp();
  }, [selectedPropertyId]);

  const handleSearchPasses = async (e) => {
    if (e) e.preventDefault();
    if (!selectedProperty) return;

    setError(null);
    setMessage(null);
    setSearching(true);
    try {
      const res = await apiClient.searchSatellite({
        property_id: selectedProperty.id,
        start_date: startDate,
        end_date: endDate,
        max_cloud_cover: maxCloudCover,
      });
      setSearchResults(res.data);
      if (res.data.length === 0) {
        setMessage('No images matched those dates and the selected cloud cover. Try widening the dates or cloud cover.');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not search for property photos.');
    } finally {
      setSearching(false);
    }
  };

  const handleRetrievePass = async (item) => {
    if (!selectedProperty) return;
    setError(null);
    setMessage(null);
    setRetrievingId(item.catalog_id);
    try {
      const res = await apiClient.retrieveSatellite({
        property_id: selectedProperty.id,
        catalog_id: item.catalog_id,
        acquisition_date: item.acquisition_date,
        satellite_name: item.satellite_name,
        cloud_coverage: item.cloud_coverage,
        is_baseline: false,
      });
      setMessage(`Photo from ${item.acquisition_date} saved.`);
      // Refresh snapshots
      const updatedProp = await apiClient.getProperty(selectedProperty.id);
      setSnapshots(updatedProp.data.snapshots || []);
      setComparisonSnapshot(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save that photo.');
    } finally {
      setRetrievingId(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Property photos over time</h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
              Find available images for a property, save them, and compare them with earlier photos.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span className="badge badge-cyan" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Satellite size={12} />
              <span>Satellite images</span>
            </span>
            <span className="badge badge-purple" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Layers size={12} />
              <span>Image catalogue</span>
            </span>
            <span className="badge badge-green" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span>Map location</span>
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div style={{ background: 'var(--color-danger-bg)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '14px 16px', borderRadius: '10px', color: '#f87171', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {message && (
        <div style={{ background: 'var(--color-success-bg)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '14px 16px', borderRadius: '10px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
          <CheckCircle2 size={18} />
          <span>{message}</span>
        </div>
      )}

      {/* Query Bar */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <form onSubmit={handleSearchPasses} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
              Select Property *
            </label>
            <select
              value={selectedPropertyId}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="input-field"
            >
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.property_reference} — {p.address}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="input-field"
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="input-field"
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
              Max Cloud Cover: <b>{maxCloudCover}%</b>
            </label>
            <input
              type="range"
              min="0"
              max="50"
              step="5"
              value={maxCloudCover}
              onChange={(e) => setMaxCloudCover(parseInt(e.target.value, 10))}
              style={{ width: '100%', accentColor: '#22a866' }}
            />
          </div>

          <div>
            <button
              type="submit"
              disabled={searching || !selectedProperty}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              <Search size={16} />
              <span>{searching ? 'Searching...' : 'Find available photos'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Catalogue Search Results */}
      {searchResults.length > 0 && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Satellite size={18} color="#6ee7a8" />
              <span>Available photos ({searchResults.length})</span>
            </h3>
            <span className="badge badge-cyan">
              <Info size={12} />
              {searchResults[0].mode}
            </span>
            {searchResults[0].data_origin === 'DEMO_SYNTHETIC' && (
              <span className="badge badge-amber" style={{ marginLeft: 8 }}>DEMO: synthetic images, not real satellite data</span>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px' }}>
            {searchResults.map((item) => {
              const alreadyRetrieved = snapshots.some(
                (s) => new Date(s.acquisition_date).toISOString().slice(0, 10) === item.acquisition_date
              );
              return (
                <div
                  key={item.catalog_id}
                  style={{
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid var(--border-glass)',
                    borderRadius: '10px',
                    padding: '16px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span className="font-mono" style={{ fontSize: '0.88rem', fontWeight: 700, color: '#6ee7a8' }}>
                        {item.acquisition_date}
                      </span>
                      <span className="badge badge-gray" style={{ fontSize: '0.72rem' }}>
                        <Cloud size={11} /> {item.cloud_coverage}%
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                      {item.satellite_name}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginBottom: '14px' }}>
                      Image detail: {item.resolution_meters} m
                    </div>
                  </div>

                  {alreadyRetrieved ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981', fontSize: '0.8rem', fontWeight: 600 }}>
                      <CheckCircle2 size={14} />
                      <span>Already saved</span>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleRetrievePass(item)}
                      disabled={retrievingId === item.catalog_id}
                      className="btn btn-secondary btn-sm"
                      style={{ width: '100%' }}
                    >
                      <DownloadCloud size={14} />
                      <span>{retrievingId === item.catalog_id ? 'Saving...' : 'Save photo'}</span>
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Side-by-Side / Interactive Comparison Preview */}
      {baselineSnapshot && comparisonSnapshot && (
        <div className="glass-panel" style={{ padding: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Compare earlier and later photos</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Baseline ({new Date(baselineSnapshot.acquisition_date).toLocaleDateString()}) vs Comparison Snapshot ({new Date(comparisonSnapshot.acquisition_date).toLocaleDateString()})
              </p>
            </div>

            <Link
              to={`/analysis?property_id=${selectedProperty.id}&base=${baselineSnapshot.id}&comp=${comparisonSnapshot.id}`}
              className="btn btn-primary"
            >
              <Layers size={16} />
              <span>Compare these photos</span>
            </Link>
          </div>

          <ImageSlider
            beforeImage={baselineSnapshot.image_path}
            afterImage={comparisonSnapshot.image_path}
            beforeLabel={`Baseline (${new Date(baselineSnapshot.acquisition_date).toLocaleDateString()})`}
            afterLabel={`Pass (${new Date(comparisonSnapshot.acquisition_date).toLocaleDateString()})`}
          />
        </div>
      )}
    </div>
  );
};

export default SatelliteMonitoringPage;
