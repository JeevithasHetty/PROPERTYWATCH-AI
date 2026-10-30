import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import AuthenticatedImage from '../components/AuthenticatedImage';
import {
  Building2,
  Search,
  Filter,
  PlusCircle,
  Eye,
  Satellite,
  Calendar,
  Layers,
  CheckCircle2,
  AlertTriangle,
  ArrowUpDown
} from 'lucide-react';

const PropertyInventoryPage = () => {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [monitoringFilter, setMonitoringFilter] = useState('');
  const [viewMode, setViewMode] = useState('table'); // 'table' or 'grid'

  const fetchProperties = async () => {
    try {
      setLoading(true);
      const params = {};
      if (search) params.search = search;
      if (typeFilter) params.property_type = typeFilter;
      if (monitoringFilter !== '') params.monitoring_enabled = monitoringFilter === 'true';

      const res = await apiClient.getProperties(params);
      setProperties(res.data);
    } catch (err) {
      console.error('Failed to load property inventory:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProperties();
  }, [typeFilter, monitoringFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchProperties();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Your properties</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
            View addresses, monitoring status, possible changes, and insurance details.
          </p>
        </div>

        <Link to="/properties/new" className="btn btn-primary">
          <PlusCircle size={16} />
          <span>Add a property</span>
        </Link>
      </div>

      {/* Search and Filters Bar */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '10px', flex: '1', minWidth: '280px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by address, owner, or policy number"
              className="input-field"
              style={{ paddingLeft: '38px' }}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Search
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="input-field"
            style={{ width: 'auto', minWidth: '180px' }}
          >
            <option value="">All Property Types</option>
            <option value="Residential Single Family">Residential Single Family</option>
            <option value="Residential Multi-Family">Residential Multi-Family</option>
            <option value="Residential Luxury Villa">Residential Luxury Villa</option>
            <option value="Commercial Office">Commercial Office</option>
            <option value="Industrial / Warehouse">Industrial / Warehouse</option>
          </select>

          <select
            value={monitoringFilter}
            onChange={(e) => setMonitoringFilter(e.target.value)}
            className="input-field"
            style={{ width: 'auto', minWidth: '160px' }}
          >
            <option value="">All monitoring statuses</option>
            <option value="true">Monitoring on</option>
            <option value="false">Monitoring paused</option>
          </select>

          <div style={{ display: 'flex', border: '1px solid var(--border-glass)', borderRadius: '8px', overflow: 'hidden' }}>
            <button
              onClick={() => setViewMode('table')}
              className={`btn btn-sm ${viewMode === 'table' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ borderRadius: 0 }}
            >
              Table
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`btn btn-sm ${viewMode === 'grid' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ borderRadius: 0 }}
            >
              Cards
            </button>
          </div>
        </div>
      </div>

      {/* Property Results */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          <div className="animate-spin" style={{ display: 'inline-block', width: '28px', height: '28px', border: '3px solid #22a866', borderTopColor: 'transparent', borderRadius: '50%', marginBottom: '12px' }} />
          <div>Loading your properties...</div>
        </div>
      ) : properties.length === 0 ? (
        <div className="glass-panel" style={{ padding: '48px', textAlign: 'center' }}>
          <Building2 size={40} color="#64748b" style={{ marginBottom: '12px' }} />
          <h3>No properties found</h3>
          <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
            Try a different search or add a property to get started.
          </p>
          <Link to="/properties/new" className="btn btn-primary" style={{ marginTop: '16px' }}>
            Add a property
          </Link>
        </div>
      ) : viewMode === 'table' ? (
        /* Table View */
        <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Property ID</th>
                  <th>Address & Location</th>
                  <th>Property Type</th>
                  <th>Owner</th>
                  <th>Monitoring</th>
                  <th>Possible changes</th>
                  <th>Confirmed changes</th>
                  <th>Actions</th>
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
                    <td>
                      <div>
                        <div style={{ fontWeight: 600 }}>{p.address}</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                          {p.city}, {p.state} {p.postal_code} ({p.latitude.toFixed(4)}, {p.longitude.toFixed(4)})
                        </div>
                      </div>
                    </td>
                    <td>{p.property_type}</td>
                    <td>
                      <div>
                        <div>{p.owner_name}</div>
                        <div style={{ fontSize: '0.76rem', color: 'var(--text-dim)' }}>{p.owner_contact}</div>
                      </div>
                    </td>
                    <td>
                      {p.monitoring_enabled ? (
                        <span className="badge badge-green">On</span>
                      ) : (
                        <span className="badge badge-gray">Paused</span>
                      )}
                    </td>
                    <td>
                      {p.open_alerts_count > 0 ? (
                        <span className="badge badge-amber">{p.open_alerts_count} Flagged</span>
                      ) : (
                        <span className="badge badge-gray">0 Alerts</span>
                      )}
                    </td>
                    <td>
                      {p.verified_modifications_count > 0 ? (
                        <span className="badge badge-green">{p.verified_modifications_count} Confirmed</span>
                      ) : (
                        <span className="badge badge-gray">0 Confirmed</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <Link to={`/properties/${p.id}`} className="btn btn-secondary btn-sm" title="View Property Dossier">
                          <Eye size={13} />
                          <span>Dossier</span>
                        </Link>
                        <Link to={`/satellite?property_id=${p.id}`} className="btn btn-secondary btn-sm" title="Satellite Monitoring">
                          <Satellite size={13} />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Card Grid View */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {properties.map((p) => (
            <div key={p.id} className="glass-panel glass-panel-interactive" style={{ padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <span className="font-mono" style={{ fontSize: '0.84rem', color: '#6ee7a8', fontWeight: 600 }}>
                    {p.property_reference}
                  </span>
                  {p.monitoring_enabled ? (
                    <span className="badge badge-green">Monitoring</span>
                  ) : (
                    <span className="badge badge-gray">Paused</span>
                  )}
                </div>

                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '6px' }}>{p.address}</h3>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
                  {p.property_type} • {p.number_of_floors} Floor(s) • {p.built_up_area ? `${p.built_up_area} sq ft` : 'Area Unspecified'}
                </div>

                {p.baseline_image_url && (
                  <div style={{ borderRadius: '8px', overflow: 'hidden', height: '140px', marginBottom: '14px', border: '1px solid var(--border-glass)' }}>
                    <AuthenticatedImage src={p.baseline_image_url} alt={p.address} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', background: 'rgba(15, 23, 42, 0.4)', padding: '10px', borderRadius: '8px', marginBottom: '16px' }}>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Open Alerts</span>
                    <div style={{ fontWeight: 700, color: p.open_alerts_count > 0 ? '#fbbf24' : 'var(--text-main)' }}>
                      {p.open_alerts_count} Flagged
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Verified Mods</span>
                    <div style={{ fontWeight: 700, color: p.verified_modifications_count > 0 ? '#34d399' : 'var(--text-main)' }}>
                      {p.verified_modifications_count} Confirmed
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: 'auto' }}>
                <Link to={`/properties/${p.id}`} className="btn btn-primary btn-sm" style={{ flex: 1 }}>
                  <span>View property</span>
                </Link>
                <Link to={`/satellite?property_id=${p.id}`} className="btn btn-secondary btn-sm" title="Search Satellite Feeds">
                  <Satellite size={14} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PropertyInventoryPage;
