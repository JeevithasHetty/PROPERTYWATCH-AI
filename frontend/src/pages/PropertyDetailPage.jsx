import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import apiClient from '../api/client';
import { useAuth } from '../context/AuthContext';
import LeafletMap from '../components/LeafletMap';
import StatusBadge from '../components/StatusBadge';
import AuditTimeline from '../components/AuditTimeline';
import AuthenticatedImage from '../components/AuthenticatedImage';
import {
  Building2,
  MapPin,
  Calendar,
  Layers,
  Satellite,
  BellRing,
  CheckCircle2,
  FileText,
  FileCheck2,
  History,
  Download,
  Upload,
  PlusCircle,
  Eye,
  ExternalLink
} from 'lucide-react';

const PropertyDetailPage = () => {
  const { id } = useParams();
  const { user } = useAuth();
  const [property, setProperty] = useState(null);
  const [historyEvents, setHistoryEvents] = useState([]);
  const [activeTab, setActiveTab] = useState('overview'); // overview, snapshots, alerts, evidence, history, audit
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [policyMessage, setPolicyMessage] = useState('');
  const [policyError, setPolicyError] = useState('');
  const [policyForm, setPolicyForm] = useState({
    policy_number: '',
    policy_type: '',
    effective_date: '',
    expiry_date: '',
  });
  const [policyDocument, setPolicyDocument] = useState(null);
  const [policyTermsBusy, setPolicyTermsBusy] = useState(false);
  const [policyTerms, setPolicyTerms] = useState({
    coverage_limits: '',
    deductibles: '',
    exclusions: '',
    endorsements: '',
  });

  const fetchPropertyData = async () => {
    try {
      setLoading(true);
      const [propRes, histRes] = await Promise.all([
        apiClient.getProperty(id),
        apiClient.getPropertyHistory(id),
      ]);
      setProperty(propRes.data);
      setHistoryEvents(histRes.data.timeline || []);
    } catch (err) {
      setError('Unable to load property details. Record may not exist.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPropertyData();
  }, [id]);

  const submitPolicy = async (event) => {
    event.preventDefault();
    setPolicyError('');
    setPolicyMessage('');
    try {
      await apiClient.linkPolicy({
        property_id: Number(id),
        policy_number: policyForm.policy_number.trim(),
        policy_type: policyForm.policy_type.trim() || null,
        effective_date: new Date(policyForm.effective_date).toISOString(),
        expiry_date: new Date(policyForm.expiry_date).toISOString(),
      });
      setPolicyMessage('Policy linked. Terms not entered remain unknown until verified.');
      await fetchPropertyData();
    } catch (err) {
      setPolicyError(err.response?.data?.detail || 'Unable to link the policy.');
    }
  };

  const uploadPolicyDocument = async (event) => {
    event.preventDefault();
    if (!policyDocument) return;
    const formData = new FormData();
    formData.append('file', policyDocument);
    try {
      await apiClient.uploadPolicyDocument(property.policy.id, formData);
      setPolicyDocument(null);
      setPolicyMessage('Policy document uploaded and versioned. Extracted terms require human verification.');
      await fetchPropertyData();
    } catch (err) {
      setPolicyError(err.response?.data?.detail || 'Unable to upload the policy document.');
    }
  };

  const downloadPolicyDocument = async () => {
    try {
      const response = await apiClient.downloadPolicyDocument(property.policy.id);
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = property.policy.document_filename || 'policy-document';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setPolicyError(err.response?.data?.detail || 'Unable to download the policy document.');
    }
  };

  const verifyPolicyTerms = async (event) => {
    event.preventDefault();
    setPolicyError('');
    setPolicyTermsBusy(true);
    try {
      if (Object.values(policyTerms).some((value) => !value.trim())) {
        throw new Error('Complete all four term fields. Use an empty object or array only after reviewing the source document.');
      }
      const verifiedTerms = {
        coverage_limits: JSON.parse(policyTerms.coverage_limits),
        deductibles: JSON.parse(policyTerms.deductibles),
        exclusions: JSON.parse(policyTerms.exclusions),
        endorsements: JSON.parse(policyTerms.endorsements),
      };
      await apiClient.verifyPolicyTerms(property.policy.id, {
        verified_terms: verifiedTerms,
        verification_notes: 'Terms checked against source policy document by authorized reviewer.',
      });
      setPolicyMessage('Policy terms verified and versioned.');
      await fetchPropertyData();
    } catch (err) {
      setPolicyError(err.response?.data?.detail || err.message || 'Unable to verify policy terms.');
    } finally {
      setPolicyTermsBusy(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0', color: 'var(--text-muted)' }}>
        <div className="animate-spin" style={{ display: 'inline-block', width: '32px', height: '32px', border: '3px solid #22a866', borderTopColor: 'transparent', borderRadius: '50%', marginBottom: '16px' }} />
        <div>Loading property details...</div>
      </div>
    );
  }

  if (error || !property) {
    return (
      <div className="glass-panel" style={{ padding: '36px', textAlign: 'center' }}>
        <h3>Property not found</h3>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>{error}</p>
        <Link to="/properties" className="btn btn-primary" style={{ marginTop: '16px' }}>
          Back to properties
        </Link>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Property Hero Banner */}
      <div className="glass-panel" style={{ padding: '28px 32px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <span className="font-mono" style={{ fontSize: '0.95rem', fontWeight: 700, color: '#6ee7a8' }}>
                {property.property_reference}
              </span>
              {property.monitoring_enabled ? (
                <span className="badge badge-green">Monitoring on</span>
              ) : (
                <span className="badge badge-gray">Monitoring Paused</span>
              )}
              {property.open_alerts_count > 0 && (
                <span className="badge badge-amber">{property.open_alerts_count} Possible changes</span>
              )}
            </div>

            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>{property.address}</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.86rem', color: 'var(--text-muted)', marginTop: '6px', flexWrap: 'wrap' }}>
              <span>{property.city}, {property.state} {property.postal_code}</span>
              <span>•</span>
              <span>{property.property_type}</span>
              <span>•</span>
              <span>Owner: <b>{property.owner_name}</b></span>
              <span>•</span>
              <span className="font-mono">Policy number: {property.reference_policy_number || 'Not added'}</span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <Link to={`/satellite?property_id=${property.id}`} className="btn btn-secondary">
              <Satellite size={16} />
              <span>Find photos</span>
            </Link>
            <Link to={`/analysis?property_id=${property.id}`} className="btn btn-secondary">
              <Layers size={16} />
              <span>Compare photos</span>
            </Link>
            <a
              href={apiClient.getPropertyReportUrl(property.id)}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary"
            >
              <Download size={16} />
              <span>Download property report</span>
            </a>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-glass)', marginTop: '24px', overflowX: 'auto' }}>
          {[
            { id: 'overview', label: 'Overview', icon: Building2 },
            { id: 'snapshots', label: `Photos (${property.snapshots?.length || 0})`, icon: Eye },
            { id: 'alerts', label: `Possible changes (${property.modifications?.length || 0})`, icon: BellRing },
            { id: 'history', label: 'Activity history', icon: History },
            { id: 'audit', label: `Change log (${property.audit_logs?.length || 0})`, icon: FileCheck2 },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`tab-btn ${isActive ? 'active' : ''}`}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', whiteSpace: 'nowrap' }}
              >
                <Icon size={16} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab 1: Overview */}
      {activeTab === 'overview' && (
        <>
        <div className="property-overview-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px' }}>
          {/* Attributes Card */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '18px' }}>Property Attributes</h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(51, 65, 85, 0.25)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Stories / Floors:</span>
                <span style={{ fontWeight: 600 }}>{property.number_of_floors}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(51, 65, 85, 0.25)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Built-up Area:</span>
                <span style={{ fontWeight: 600 }}>{property.built_up_area ? `${property.built_up_area} sq ft` : 'Unspecified'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(51, 65, 85, 0.25)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Owner Contact:</span>
                <span style={{ fontWeight: 600 }}>{property.owner_contact || 'N/A'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(51, 65, 85, 0.25)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Policy number:</span>
                <span className="font-mono" style={{ color: '#6ee7a8' }}>{property.reference_policy_number || 'N/A'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(51, 65, 85, 0.25)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Registered Date:</span>
                <span>{new Date(property.created_at).toLocaleDateString()}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(51, 65, 85, 0.25)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Last Monitoring Check:</span>
                <span>{property.last_monitoring_date ? new Date(property.last_monitoring_date).toLocaleDateString() : 'Pending Search'}</span>
              </div>
            </div>

            {property.notes && (
              <div style={{ marginTop: '18px', padding: '12px', background: 'rgba(15, 23, 42, 0.4)', borderRadius: '8px', fontSize: '0.84rem', color: 'var(--text-muted)' }}>
                <b>Notes:</b> {property.notes}
              </div>
            )}
          </div>

          {/* Map Location Card */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MapPin size={18} color="#6ee7a8" />
              <span>Confirmed Coordinates</span>
            </h3>

            <div style={{ height: '260px', marginBottom: '14px' }}>
              <LeafletMap latitude={property.latitude} longitude={property.longitude} popupText={property.address} />
            </div>

            <div style={{ display: 'flex', gap: '20px', fontSize: '0.84rem' }}>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Lat:</span> <b className="font-mono">{property.latitude.toFixed(6)}°</b>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Lon:</span> <b className="font-mono">{property.longitude.toFixed(6)}°</b>
              </div>
              <div style={{ marginLeft: 'auto', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={14} />
                <span>Confirmed Pin</span>
              </div>
            </div>
          </div>

          {/* Baseline Image Card */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '14px' }}>Earlier property photo</h3>
            {property.baseline_image_url ? (
              <div style={{ borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--border-glass)', maxHeight: '280px' }}>
                <AuthenticatedImage src={property.baseline_image_url} alt="Baseline" style={{ width: '100%', height: '280px', objectFit: 'cover' }} />
              </div>
            ) : (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dim)' }}>
                No baseline image uploaded yet.
              </div>
            )}
          </div>
        </div>
        <section className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '8px' }}>Insurance Policy</h3>
          {policyError && <p role="alert" style={{ color: '#f87171', marginBottom: '10px' }}>{policyError}</p>}
          {policyMessage && <p role="status" style={{ color: '#34d399', marginBottom: '10px' }}>{policyMessage}</p>}
          {property.policy ? (
            <div style={{ display: 'grid', gap: '16px' }}>
              <div style={{ color: 'var(--text-muted)' }}>
                <b>{property.policy.policy_number}</b> · {property.policy.policy_type || 'Policy type not recorded'} · {new Date(property.policy.effective_date).toLocaleDateString()}–{new Date(property.policy.expiry_date).toLocaleDateString()}
                <div style={{ marginTop: '6px' }}>
                  Terms: {property.policy.terms_verified ? 'Verified by reviewer' : 'Unverified — missing terms are not assumed'}
                </div>
                {property.policy.document_filename && (
                  <button className="btn btn-secondary" type="button" onClick={downloadPolicyDocument}>
                    Download {property.policy.document_filename}
                  </button>
                )}
              </div>
              <form onSubmit={uploadPolicyDocument} style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
                <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setPolicyDocument(e.target.files?.[0] || null)} />
                <button className="btn btn-secondary" type="submit" disabled={!policyDocument}>Upload policy document</button>
              </form>
              {['admin', 'reviewer'].includes(user?.role) && !property.policy.terms_verified && (
                <form onSubmit={verifyPolicyTerms} style={{ display: 'grid', gap: '10px' }}>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
                    Enter the terms as shown in the source document. Use <code>{'{}'}</code> or <code>[]</code> only after confirming that category is absent.
                  </p>
                  {Object.entries(policyTerms).map(([key, value]) => (
                    <label key={key} style={{ display: 'grid', gap: '5px', color: 'var(--text-muted)' }}>
                      {key.replaceAll('_', ' ')}
                      <textarea className="form-input" rows="2" value={value} onChange={(e) => setPolicyTerms({ ...policyTerms, [key]: e.target.value })} placeholder={key === 'exclusions' || key === 'endorsements' ? '[]' : '{}'} />
                    </label>
                  ))}
                  <button className="btn btn-primary" type="submit" disabled={policyTermsBusy}>
                    {policyTermsBusy ? 'Verifying…' : 'Verify policy terms'}
                  </button>
                </form>
              )}
            </div>
          ) : (
            <form onSubmit={submitPolicy} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <label>Policy number<input className="form-input" required value={policyForm.policy_number} onChange={(e) => setPolicyForm({ ...policyForm, policy_number: e.target.value })} /></label>
              <label>Policy type (optional)<input className="form-input" value={policyForm.policy_type} onChange={(e) => setPolicyForm({ ...policyForm, policy_type: e.target.value })} /></label>
              <label>Effective date<input className="form-input" type="date" required value={policyForm.effective_date} onChange={(e) => setPolicyForm({ ...policyForm, effective_date: e.target.value })} /></label>
              <label>Expiry date<input className="form-input" type="date" required value={policyForm.expiry_date} onChange={(e) => setPolicyForm({ ...policyForm, expiry_date: e.target.value })} /></label>
              <div style={{ gridColumn: '1 / -1', color: 'var(--text-muted)', fontSize: '0.84rem' }}>
                Coverage limits, deductibles, exclusions, and endorsements are intentionally left unspecified until documented.
              </div>
              <button className="btn btn-primary" type="submit">Link policy</button>
            </form>
          )}
        </section>
        </>
      )}

      {/* Tab 2: Imagery Snapshots */}
      {activeTab === 'snapshots' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Acquired Optical Snapshots</h3>
            <Link to={`/satellite?property_id=${property.id}`} className="btn btn-primary btn-sm">
              <Satellite size={14} />
              <span>Search & Retrieve Passes</span>
            </Link>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px' }}>
            {property.snapshots?.map((snap) => (
              <div key={snap.id} className="glass-panel" style={{ overflow: 'hidden', padding: 0 }}>
                <div style={{ position: 'relative', aspectRatio: '1/1' }}>
                  <AuthenticatedImage src={snap.image_path} alt={`Snapshot ${snap.acquisition_date}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  {snap.is_baseline && (
                    <div style={{ position: 'absolute', top: '10px', left: '10px', background: '#22a866', color: '#fff', padding: '3px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 700 }}>
                      Earlier photo
                    </div>
                  )}
                  <div style={{ position: 'absolute', bottom: '10px', right: '10px', background: 'rgba(0, 0, 0, 0.75)', color: '#fff', padding: '3px 8px', borderRadius: '4px', fontSize: '0.72rem' }}>
                    Cloud: {snap.cloud_coverage}%
                  </div>
                </div>

                <div style={{ padding: '14px' }}>
                  <div style={{ fontSize: '0.84rem', fontWeight: 700, marginBottom: '4px' }}>
                    Acquired: {new Date(snap.acquisition_date).toLocaleDateString()}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-dim)', marginBottom: '12px' }}>
                    Source: {snap.image_source}
                  </div>
                  <Link to={`/analysis?property_id=${property.id}&comp=${snap.id}`} className="btn btn-secondary btn-sm" style={{ width: '100%' }}>
                    Compare with earlier photos
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Alerts */}
      {activeTab === 'alerts' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '18px' }}>Modification Alerts</h3>

          <div style={{ overflowX: 'auto' }}>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Alert ID</th>
                  <th>Suspected Modification</th>
                  <th>Change Score</th>
                  <th>Detected Date</th>
                  <th>Status</th>
                  <th>Reviewer Action</th>
                </tr>
              </thead>
              <tbody>
                {property.modifications?.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <span className="font-mono" style={{ color: '#6ee7a8', fontWeight: 600 }}>{m.modification_alert_id}</span>
                    </td>
                    <td>{m.suspected_category}</td>
                    <td>
                      <span style={{ fontWeight: 700, color: m.change_score > 25 ? '#f87171' : '#34d399' }}>{m.change_score}%</span>
                    </td>
                    <td>{new Date(m.detected_at).toLocaleDateString()}</td>
                    <td>
                      <StatusBadge status={m.status} />
                    </td>
                    <td>
                      <Link to={`/reviews?case=${m.id}`} className="btn btn-primary btn-sm">
                        Review Workspace
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Chronological History */}
      {activeTab === 'history' && (
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '22px' }}>Property activity</h3>
          <AuditTimeline events={historyEvents} />
        </div>
      )}

      {/* Tab 5: Audit Trail */}
      {activeTab === 'audit' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px' }}>Immutable Audit Records</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {property.audit_logs?.map((a) => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(15, 23, 42, 0.4)', borderRadius: '8px', border: '1px solid rgba(51, 65, 85, 0.25)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="badge badge-gray">{a.action}</span>
                  <span style={{ fontSize: '0.84rem' }}>{a.notes}</span>
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                  {new Date(a.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PropertyDetailPage;
