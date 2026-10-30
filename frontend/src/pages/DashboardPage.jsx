import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import {
  Building2,
  Activity,
  AlertTriangle,
  Clock,
  CheckCircle2,
  FileQuestion,
  TrendingUp,
  ArrowRight,
  Layers,
  Calendar,
  Satellite
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';
import DashboardMap from '../components/DashboardMap';

const DashboardPage = () => {
  const [metrics, setMetrics] = useState(null);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const [metricsRes, propsRes] = await Promise.all([
        apiClient.getDashboardMetrics(),
        apiClient.getProperties()
      ]);
      setMetrics(metricsRes.data);
      setProperties(propsRes.data);
    } catch (err) {
      setError('Failed to load operational metrics from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0', color: 'var(--text-muted)' }}>
        <div className="animate-spin" style={{ display: 'inline-block', width: '32px', height: '32px', border: '3px solid #22a866', borderTopColor: 'transparent', borderRadius: '50%', marginBottom: '16px' }} />
        <div>Loading your property overview...</div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="glass-panel" style={{ padding: '36px', textAlign: 'center' }}>
        <AlertTriangle size={36} color="#ef4444" style={{ marginBottom: '12px' }} />
        <h3>We couldn’t load your overview</h3>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>{error}</p>
        <button onClick={fetchMetrics} className="btn btn-primary" style={{ marginTop: '16px' }}>
          Retry
        </button>
      </div>
    );
  }

  const categoryColors = ['#22a866', '#6ee7a8', '#059669', '#d97706', '#dc2626', '#9333ea'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Page Title & Actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Your property overview</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
            See your properties, photo comparisons, possible changes, and claim activity in one place.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <Link to="/satellite" className="btn btn-secondary">
            <Satellite size={16} />
            <span>Find property photos</span>
          </Link>
          <Link to="/properties/new" className="btn btn-primary">
            <Building2 size={16} />
            <span>Add a property</span>
          </Link>
        </div>
      </div>

      {/* Primary KPI Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '18px' }}>
        <StatCard
          title="Properties registered"
          value={metrics.total_properties}
          icon={Building2}
          color="cyan"
          trend="All properties"
          linkTo="/properties"
        />
        <StatCard
          title="Properties being monitored"
          value={metrics.monitored_properties}
          icon={Activity}
          color="green"
          trend="Monitoring on"
          linkTo="/properties"
        />
        <StatCard
          title="Possible changes"
          value={metrics.new_alerts_count}
          icon={AlertTriangle}
          color="amber"
          trend="Needs a closer look"
          linkTo="/modifications?status=New"
        />
        <StatCard
          title="Waiting for review"
          value={metrics.awaiting_review_count}
          icon={Clock}
          color="cyan"
          trend="Open cases"
          linkTo="/reviews"
        />
        <StatCard
          title="Changes confirmed"
          value={metrics.confirmed_modifications_count}
          icon={CheckCircle2}
          color="green"
          trend="Checked by a reviewer"
          linkTo="/history"
        />
        <StatCard
          title="More information requested"
          value={metrics.additional_evidence_count}
          icon={FileQuestion}
          color="purple"
          trend="May need your response"
          linkTo="/modifications?status=Additional%20Evidence%20Required"
        />
      </div>

      {/* Interactive Geographic Distribution & Earth Observation Map */}
      <DashboardMap properties={properties} />

      {/* Analytics Charts Section */}
      <div className="dashboard-charts" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '22px' }}>
        {/* Monthly Trend Area Chart */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={18} color="#6ee7a8" />
              <span>Possible changes over time</span>
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Based on recorded alerts</span>
          </div>

          <div style={{ height: '240px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={metrics.alerts_by_month}>
                <defs>
                  <linearGradient id="colorAlerts" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22a866" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#22a866" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="month" stroke="#64748b" fontSize={12} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#fff' }}
                />
                <Area type="monotone" dataKey="alerts" stroke="#6ee7a8" strokeWidth={2} fillOpacity={1} fill="url(#colorAlerts)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Suspected Categories Distribution */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="#34d399" />
              <span>Modification Categories Breakdown</span>
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Detected Signatures</span>
          </div>

          <div style={{ height: '240px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics.modification_categories} layout="vertical">
                <XAxis type="number" stroke="#64748b" fontSize={12} tickLine={false} allowDecimals={false} />
                <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={11} width={130} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#fff' }}
                />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {metrics.modification_categories.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={categoryColors[index % categoryColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Modification Cases Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Recent Modification Cases</h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Photo differences that still need a person to review them</p>
          </div>
          <Link to="/modifications" className="btn btn-secondary btn-sm">
            <span>View All Cases</span>
            <ArrowRight size={14} />
          </Link>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="custom-table">
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Property Reference</th>
                <th>Suspected Category</th>
                <th>Change Score</th>
                <th>Detected Date</th>
                <th>Status</th>
                <th>Reviewer</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {metrics.recent_cases.length > 0 ? (
                metrics.recent_cases.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span className="font-mono" style={{ color: '#6ee7a8', fontWeight: 600 }}>
                        {c.modification_alert_id}
                      </span>
                    </td>
                    <td>
                      <div>
                        <div style={{ fontWeight: 600 }}>{c.property_reference}</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{c.property_address}</div>
                      </div>
                    </td>
                    <td>{c.suspected_category}</td>
                    <td>
                      <span style={{ fontWeight: 700, color: c.change_score > 25 ? '#f87171' : (c.change_score > 10 ? '#fbbf24' : '#34d399') }}>
                        {c.change_score}%
                      </span>
                    </td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      {new Date(c.detected_at).toLocaleDateString()}
                    </td>
                    <td>
                      <StatusBadge status={c.status} />
                    </td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      {c.reviewer_name || 'Unassigned'}
                    </td>
                    <td>
                      <Link to={`/reviews?case=${c.id}`} className="btn btn-secondary btn-sm">
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-dim)' }}>
                    No modification cases recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Activity Stream (Recent Audit Trail) */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} color="#22a866" />
            <span>Recent System & Reviewer Activity</span>
          </h3>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>Immutable SQLite Audit Trail</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {metrics.recent_activity.slice(0, 5).map((log) => (
            <div
              key={log.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                background: 'rgba(15, 23, 42, 0.4)',
                borderRadius: '8px',
                border: '1px solid rgba(51, 65, 85, 0.25)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span className="badge badge-gray">{log.entity_type}</span>
                <span style={{ fontSize: '0.86rem', color: 'var(--text-main)', fontWeight: 500 }}>
                  {log.action.replace(/_/g, ' ')}
                </span>
                {log.notes && (
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>— {log.notes}</span>
                )}
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({log.user_name})
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
