import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import StatusBadge from '../components/StatusBadge';
import { FileText, Download, Building2, BellRing, CheckCircle2, Shield, ExternalLink } from 'lucide-react';

const ReportsPage = () => {
  const [properties, setProperties] = useState([]);
  const [modifications, setModifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [propsRes, modsRes] = await Promise.all([
          apiClient.getProperties(),
          apiClient.getModifications(),
        ]);
        setProperties(propsRes.data);
        setModifications(modsRes.data);
      } catch (err) {
        console.error('Failed to load reports data', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Reports</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
          Download a property report or a summary of a possible change, including the available photos and review notes.
        </p>
      </div>

      {/* Reports by Modification Case */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <BellRing size={18} color="#6ee7a8" />
          <span>Possible change reports</span>
        </h3>

        <div style={{ overflowX: 'auto' }}>
          <table className="custom-table">
            <thead>
              <tr>
                <th>Alert number</th>
                <th>Property and address</th>
                <th>Possible change</th>
                <th>Photo difference</th>
                <th>Status</th>
                <th>Reviewer notes</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {modifications.map((m) => (
                <tr key={m.id}>
                  <td>
                    <span className="font-mono" style={{ color: '#6ee7a8', fontWeight: 700 }}>
                      {m.modification_alert_id}
                    </span>
                  </td>
                  <td>
                    <div>
                      <div style={{ fontWeight: 600 }}>{m.property_reference}</div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{m.property_address}</div>
                    </div>
                  </td>
                  <td>{m.suspected_category}</td>
                  <td>
                    <span style={{ fontWeight: 700, color: m.change_score > 25 ? '#f87171' : '#34d399' }}>
                      {m.change_score}%
                    </span>
                  </td>
                  <td>
                    <StatusBadge status={m.status} />
                  </td>
                  <td style={{ fontSize: '0.84rem' }}>
                    {m.decision_reason ? (
                      <span title={m.decision_reason} style={{ color: '#e2e8f0' }}>
                        {m.decision_reason.slice(0, 36)}...
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>Waiting for review</span>
                    )}
                  </td>
                  <td>
                    <a
                      href={apiClient.getModificationReportUrl(m.id)}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-primary btn-sm"
                    >
                      <Download size={13} />
                      <span>Download PDF</span>
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reports by Property Profile */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Building2 size={18} color="#34d399" />
          <span>Property reports</span>
        </h3>

        <div style={{ overflowX: 'auto' }}>
          <table className="custom-table">
            <thead>
              <tr>
                <th>Property ID</th>
                <th>Address</th>
                <th>Owner</th>
                <th>Type</th>
                <th>Policy number</th>
                <th>Confirmed changes</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {properties.map((p) => (
                <tr key={p.id}>
                  <td>
                    <span className="font-mono" style={{ color: '#6ee7a8', fontWeight: 600 }}>
                      {p.property_reference}
                    </span>
                  </td>
                  <td>{p.address}</td>
                  <td>{p.owner_name}</td>
                  <td>{p.property_type}</td>
                  <td className="font-mono" style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>
                    {p.reference_policy_number || 'N/A'}
                  </td>
                  <td>
                    <span className="badge badge-green">{p.verified_modifications_count} Confirmed</span>
                  </td>
                  <td>
                    <a
                      href={apiClient.getPropertyReportUrl(p.id)}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-secondary btn-sm"
                    >
                      <Download size={13} />
                      <span>Download report</span>
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ReportsPage;
