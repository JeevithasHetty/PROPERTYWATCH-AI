import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import apiClient from '../api/client';
import StatusBadge from '../components/StatusBadge';
import {
  BellRing,
  Search,
  Filter,
  Eye,
  FileCheck2,
  Upload,
  Calendar,
  Layers,
  Building2,
  ArrowRight
} from 'lucide-react';

const ModificationAlertsPage = () => {
  const [searchParams] = useSearchParams();
  const initialStatus = searchParams.get('status') || '';

  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [search, setSearch] = useState('');

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter) params.status = statusFilter;
      const res = await apiClient.getModifications(params);
      setAlerts(res.data);
    } catch (err) {
      console.error('Failed to load modification alerts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [statusFilter]);

  const filteredAlerts = alerts.filter((a) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      a.modification_alert_id.toLowerCase().includes(q) ||
      (a.property_reference && a.property_reference.toLowerCase().includes(q)) ||
      (a.property_address && a.property_address.toLowerCase().includes(q)) ||
      a.suspected_category.toLowerCase().includes(q)
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Possible property changes</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
            Photo comparisons can highlight differences. A reviewer should check each one before it is treated as a real change.
          </p>
        </div>

        <Link to="/analysis" className="btn btn-primary">
          <Layers size={16} />
          <span>Compare property photos</span>
        </Link>
      </div>

      {/* Filter and Search Toolbar */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: '280px' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by alert number, address, or change type"
            className="input-field"
            style={{ paddingLeft: '38px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field"
            style={{ width: 'auto', minWidth: '180px' }}
          >
            <option value="">All case statuses</option>
            <option value="New">New</option>
            <option value="Awaiting Evidence">Waiting for information</option>
            <option value="Under Review">Being reviewed</option>
            <option value="Additional Evidence Required">More information needed</option>
            <option value="Verified">Confirmed by reviewer</option>
            <option value="Not Confirmed">Not confirmed</option>
          </select>
        </div>
      </div>

      {/* Alerts Table */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          <div className="animate-spin" style={{ display: 'inline-block', width: '28px', height: '28px', border: '3px solid #22a866', borderTopColor: 'transparent', borderRadius: '50%', marginBottom: '12px' }} />
          <div>Loading possible changes...</div>
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="glass-panel" style={{ padding: '48px', textAlign: 'center' }}>
          <BellRing size={40} color="#64748b" style={{ marginBottom: '12px' }} />
          <h3>No possible changes found</h3>
          <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
            Compare two property photos to look for visible differences.
          </p>
          <Link to="/analysis" className="btn btn-primary" style={{ marginTop: '16px' }}>
            Compare photos
          </Link>
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Alert number</th>
                  <th>Property and address</th>
                  <th>Possible change</th>
                  <th>Difference score</th>
                  <th>Date noticed</th>
                  <th>Status</th>
                  <th>Files shared</th>
                  <th>Reviewer</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <span className="font-mono" style={{ color: '#6ee7a8', fontWeight: 700, fontSize: '0.92rem' }}>
                        {a.modification_alert_id}
                      </span>
                    </td>
                    <td>
                      <div>
                        <div style={{ fontWeight: 600 }}>{a.property_reference}</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{a.property_address}</div>
                      </div>
                    </td>
                    <td>{a.suspected_category}</td>
                    <td>
                      <span style={{ fontWeight: 700, color: a.change_score > 25 ? '#f87171' : (a.change_score > 10 ? '#fbbf24' : '#34d399') }}>
                        {a.change_score}%
                      </span>
                    </td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      {new Date(a.detected_at).toLocaleDateString()}
                    </td>
                    <td>
                      <StatusBadge status={a.status} />
                    </td>
                    <td>
                      <span className="badge badge-gray" style={{ fontSize: '0.75rem' }}>
                        {a.evidence_count} Item(s)
                      </span>
                    </td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      {a.reviewer_name || 'Unassigned'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <Link to={`/reviews?case=${a.id}`} className="btn btn-primary btn-sm" title="Open case review">
                          <FileCheck2 size={13} />
                          <span>Review</span>
                        </Link>
                        <Link to={`/properties/${a.property_id}`} className="btn btn-secondary btn-sm" title="View Property">
                          <Building2 size={13} />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModificationAlertsPage;
