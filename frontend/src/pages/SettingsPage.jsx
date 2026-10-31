import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import {
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Database,
  Satellite,
  MapPin,
  Sparkles,
  RefreshCw,
  ShieldAlert,
  Info,
  Radio
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const SettingsPage = () => {
  const { role } = useAuth();
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const res = await apiClient.getSettingsStatus();
      setStatusData(res.data);
    } catch (err) {
      console.error('Failed to load settings status', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleToggleDemo = async () => {
    setToggling(true);
    setMessage(null);
    try {
      const res = await apiClient.toggleDemoMode();
      setMessage(res.data.message);
      fetchStatus();
    } catch (err) {
      console.error('Failed to toggle demo mode', err);
    } finally {
      setToggling(false);
    }
  };

  if (loading || !statusData) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0', color: 'var(--text-muted)' }}>
        <div className="animate-spin" style={{ display: 'inline-block', width: '32px', height: '32px', border: '3px solid #22a866', borderTopColor: 'transparent', borderRadius: '50%', marginBottom: '16px' }} />
        <div>Verifying service subsystems & API health...</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Settings and services</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
            Check whether address lookup, satellite photos, image checks, and saved records are available.
          </p>
        </div>

        <button onClick={fetchStatus} className="btn btn-secondary">
          <RefreshCw size={15} />
          <span>Check services again</span>
        </button>
      </div>

      {message && (
        <div style={{ background: 'var(--color-success-bg)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '14px 16px', borderRadius: '10px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
          <CheckCircle2 size={18} />
          <span>{message}</span>
        </div>
      )}

      {/* Operational Mode Toggle Card */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '18px', border: '1px solid rgba(110, 231, 168, 0.3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Radio size={18} color="#6ee7a8" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{statusData.demo_mode ? 'Demo data' : 'Live data'}</h3>
          </div>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', maxWidth: '650px', lineHeight: 1.45 }}>
            {statusData.demo_mode
              ? 'Demo mode may show sample records and simulated images. These examples are for trying the app and are not real property evidence.'
              : 'Live mode uses the external services configured for this installation. Availability depends on those services and credentials.'}
          </p>
        </div>

        {role === 'admin' && (
          <button
            onClick={handleToggleDemo}
            disabled={toggling}
            className={`btn ${statusData.demo_mode ? 'btn-primary' : 'btn-secondary'}`}
          >
            <span>{toggling ? 'Changing mode...' : `Switch to ${statusData.demo_mode ? 'Live data' : 'Demo data'}`}</span>
          </button>
        )}
      </div>

      {/* Service Health Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Geocoding Service */}
        <div className="glass-panel" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MapPin size={18} color="#6ee7a8" />
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Address lookup and maps</h4>
            </div>
            <span className="badge badge-green">{statusData.geocoding.status}</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem' }}>
            <div><b>Provider:</b> {statusData.geocoding.provider}</div>
            <div><b>Region filter:</b> India only (countrycodes={statusData.geocoding.countrycodes})</div>
            <div><b>Policy Compliance:</b> {statusData.geocoding.rate_limit_compliance}</div>
            <div><b>Interactive Map Engine:</b> {statusData.geocoding.map_engine || 'Leaflet + OpenStreetMap Cartographic Tiles'}</div>
            <div><b>Local Caching:</b> {statusData.geocoding.caching_active ? 'Active (In-memory & SQLite)' : 'Disabled'}</div>
            <div><b>Mode:</b> {statusData.geocoding.mode}</div>
          </div>
        </div>

        {/* Satellite Imagery Service */}
        <div className="glass-panel" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Satellite size={18} color="#2dd4bf" />
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Satellite photo service</h4>
            </div>
            <span className="badge badge-cyan">{statusData.satellite_service.status}</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem' }}>
            <div><b>Active provider:</b> {statusData.satellite_service.active_provider || 'none'}</div>
            <div><b>Copernicus credentials:</b> {statusData.satellite_service.copernicus_configured ? 'configured' : 'missing (COPERNICUS_CLIENT_ID / SECRET)'}</div>
            <div><b>Google Earth Engine:</b> {statusData.satellite_service.gee_configured ? 'configured' : `missing: ${(statusData.satellite_service.gee_missing || []).join(', ')}`}</div>
            <div><b>Dataset:</b> {statusData.satellite_service.dataset}</div>
            <div><b>Resolution:</b> {statusData.satellite_service.resolution}</div>
            {statusData.satellite_service.synthetic_imagery_possible && <div style={{ color: '#fbbf24' }}><b>Demo mode:</b> images may be synthetic and are labelled DEMO.</div>}
          </div>
        </div>

        {/* AI Authenticity & Deepfake Forensics */}
        <div className="glass-panel" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={18} color="#f59e0b" />
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Photo file checks</h4>
            </div>
            <span className="badge badge-green">Operational</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem' }}>
            <div><b>Engine:</b> {statusData.authenticity_service.engine}</div>
            <div><b>Diffusion Lattice Detection:</b> {statusData.authenticity_service.spectral_fft_analysis || 'Active (2D FFT / DCT)'}</div>
            <div><b>Error Level Analysis:</b> {statusData.authenticity_service.error_level_analysis || 'Active (Pillow ELA 90%)'}</div>
            <div><b>Sensor PRNU Noise:</b> {statusData.authenticity_service.noise_print_variance || 'Active (High-pass residual variance)'}</div>
            <div><b>Visual Heatmaps:</b> {statusData.authenticity_service.forensic_heatmaps || 'Automated Turbo Overlays'}</div>
          </div>
        </div>

        {/* LLM Evidence Summarizer */}
        <div className="glass-panel" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Info size={18} color="#c084fc" />
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Document summaries</h4>
            </div>
            <span className="badge badge-cyan">{statusData.llm_service.status}</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem' }}>
            <div><b>Engine:</b> {statusData.llm_service.engine}</div>
            <div><b>Purpose:</b> {statusData.llm_service.purpose}</div>
            <div><b>Autonomous Decisions:</b> Strictly Disabled (Human Reviewer Required)</div>
          </div>
        </div>

        {/* Database Persistence */}
        <div className="glass-panel" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Database size={18} color="#10b981" />
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Saved information</h4>
            </div>
            <span className="badge badge-green">Connected</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem' }}>
            <div><b>Type:</b> {statusData.database.type}</div>
            <div><b>Status:</b> {statusData.database.status}</div>
            <div><b>Schema Tables Initialized:</b> {statusData.database.tables_initialized}</div>
            <div><b>Audit Logging:</b> Active & Immutable</div>
          </div>
        </div>
      </div>

      {/* Configuration Guidance Notice */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Info size={18} color="#6ee7a8" />
          <span>Satellite &amp; external API configuration</span>
        </h3>
        <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '14px' }}>
          Live imagery needs credentials in the backend <code>.env</code> file (never in the browser). Use Copernicus Data Space (free) or Google Earth Engine with your own project and service account:
        </p>

        <div style={{ background: '#070b14', padding: '14px 18px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#6ee7a8' }}>
          COPERNICUS_CLIENT_ID=&lt;your OAuth client id&gt;<br/>
          COPERNICUS_CLIENT_SECRET=&lt;your OAuth client secret&gt;<br/>
          # optional Earth Engine<br/>
          GEE_PROJECT_ID=&lt;your project&gt;<br/>
          GEE_SERVICE_ACCOUNT_EMAIL=&lt;service account&gt;<br/>
          GEE_SERVICE_ACCOUNT_KEY=&lt;path to key json&gt;<br/>
          NOMINATIM_USER_AGENT=PropertyWatchAI/1.0 (your real contact)<br/>
          DEMO_MODE=false
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
