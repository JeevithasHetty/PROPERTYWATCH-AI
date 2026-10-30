import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import AuditTimeline from '../components/AuditTimeline';
import { History, Building2, Calendar, ShieldCheck, Download, Search } from 'lucide-react';

const ChronologicalHistoryPage = () => {
  const [properties, setProperties] = useState([]);
  const [selectedPropertyId, setSelectedPropertyId] = useState('');
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadProps = async () => {
      try {
        setLoading(true);
        const res = await apiClient.getProperties();
        setProperties(res.data);
        if (res.data.length > 0) {
          setSelectedPropertyId(res.data[0].id.toString());
        }
      } catch (err) {
        console.error('Failed to load properties', err);
      } finally {
        setLoading(false);
      }
    };
    loadProps();
  }, []);

  useEffect(() => {
    if (!selectedPropertyId) return;
    const loadTimeline = async () => {
      try {
        const res = await apiClient.getPropertyHistory(selectedPropertyId);
        setTimeline(res.data.timeline || []);
      } catch (err) {
        console.error('Failed to load timeline', err);
      }
    };
    loadTimeline();
  }, [selectedPropertyId]);

  const selectedProp = properties.find((p) => p.id.toString() === selectedPropertyId);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Verified Chronological History</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
          Auditable timeline of verified physical modifications, baseline snapshots, and historical property changes.
        </p>
      </div>

      {/* Property Selector Bar */}
      <div className="glass-panel" style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '300px' }}>
          <Building2 size={18} color="#6ee7a8" />
          <span style={{ fontSize: '0.88rem', fontWeight: 600 }}>Select Property:</span>
          <select
            value={selectedPropertyId}
            onChange={(e) => setSelectedPropertyId(e.target.value)}
            className="input-field"
            style={{ maxWidth: '420px' }}
          >
            {properties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.property_reference} — {p.address}
              </option>
            ))}
          </select>
        </div>

        {selectedProp && (
          <a
            href={apiClient.getPropertyReportUrl(selectedProp.id)}
            target="_blank"
            rel="noreferrer"
            className="btn btn-secondary btn-sm"
          >
            <Download size={14} />
            <span>Download Dossier Report</span>
          </a>
        )}
      </div>

      {/* Timeline Display Card */}
      <div className="glass-panel" style={{ padding: '32px' }}>
        {selectedProp && (
          <div style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '18px', marginBottom: '24px' }}>
            <span className="font-mono" style={{ fontSize: '0.88rem', color: '#6ee7a8', fontWeight: 700 }}>
              {selectedProp.property_reference}
            </span>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 800, marginTop: '2px' }}>{selectedProp.address}</h2>
            <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Owner: <b>{selectedProp.owner_name}</b> • Type: {selectedProp.property_type} • Policy Ref: {selectedProp.reference_policy_number || 'N/A'}
            </div>
          </div>
        )}

        <AuditTimeline events={timeline} />
      </div>
    </div>
  );
};

export default ChronologicalHistoryPage;
