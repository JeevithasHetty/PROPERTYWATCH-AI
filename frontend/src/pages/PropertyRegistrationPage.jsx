import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import LeafletMap from '../components/LeafletMap';
import {
  Building2,
  MapPin,
  Search,
  CheckCircle2,
  AlertCircle,
  Upload,
  Satellite,
  ArrowRight,
  ShieldAlert
} from 'lucide-react';

const PropertyRegistrationPage = () => {
  const navigate = useNavigate();

  // Form State
  const [formData, setFormData] = useState({
    owner_name: '',
    owner_contact: '',
    address: '',
    city: '',
    state: '',
    postal_code: '',
    latitude: null,
    longitude: null,
    property_type: 'Residential Single Family',
    number_of_floors: 1,
    built_up_area: '',
    reference_policy_number: '',
    monitoring_enabled: true,
    notes: '',
  });

  // Geocoding & Confirmation State
  const [geocodingLoading, setGeocodingLoading] = useState(false);
  const [locationConfirmed, setLocationConfirmed] = useState(false);
  const [matchedAddress, setMatchedAddress] = useState('');
  const [geocodeSource, setGeocodeSource] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Baseline Photo State
  const [baselineFile, setBaselineFile] = useState(null);
  const [baselinePreview, setBaselinePreview] = useState(null);
  const [registeredProperty, setRegisteredProperty] = useState(null);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    // If address changed, reset location confirmation
    if (name === 'address' || name === 'city' || name === 'state' || name === 'postal_code') {
      setLocationConfirmed(false);
    }
  };

  const handleGeocode = async () => {
    const fullQuery = [formData.address, formData.city, formData.state, formData.postal_code]
      .filter(Boolean)
      .join(', ');

    if (!fullQuery.trim()) {
      setError('Please enter a street address to locate coordinates.');
      return;
    }

    setError('');
    setGeocodingLoading(true);
    try {
      const res = await apiClient.geocode(fullQuery);
      const data = res.data;
      setFormData((prev) => ({
        ...prev,
        latitude: data.latitude,
        longitude: data.longitude,
        city: prev.city || data.city || '',
        state: prev.state || data.state || '',
        postal_code: prev.postal_code || data.postal_code || '',
      }));
      setMatchedAddress(data.display_name);
      setGeocodeSource(data.source);
      if (data.precision === 'approximate') {
        setLocationConfirmed(false);
        setError('Approximate location only (street/house number not found in OpenStreetMap). Click the map to place the pin on your building, then confirm.');
      } else {
        setLocationConfirmed(true);
      }
    } catch (err) {
      setError((err.response?.data?.detail || 'Could not locate this address.') + ' You can also click the map to place the pin manually.');
    } finally {
      setGeocodingLoading(false);
    }
  };

  const handleMapPinSelected = (lat, lon) => {
    setFormData((prev) => ({
      ...prev,
      latitude: parseFloat(lat.toFixed(6)),
      longitude: parseFloat(lon.toFixed(6)),
    }));
    setLocationConfirmed(true);
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setBaselineFile(file);
      setBaselinePreview(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!locationConfirmed) {
      setError('      Confirm the property location on the map before saving.');
      return;
    }

    setError('');
    setSubmitting(true);
    try {
      const payload = {
        ...formData,
        number_of_floors: parseInt(formData.number_of_floors, 10) || 1,
        built_up_area: formData.built_up_area ? parseFloat(formData.built_up_area) : null,
      };

      const res = await apiClient.createProperty(payload);
      const created = res.data;
      setRegisteredProperty(created);

      // If baseline photo selected, upload it immediately
      if (baselineFile) {
        const uploadData = new FormData();
        uploadData.append('file', baselineFile);
        await apiClient.uploadBaselinePhoto(created.id, uploadData);
      }

      // Automatically retrieve baseline satellite pass tile
      try {
        await apiClient.retrieveSatellite({
          property_id: created.id,
          catalog_id: `S2B_BASELINE_${created.property_reference}`,
          acquisition_date: new Date().toISOString().slice(0, 10),
          satellite_name: 'Sentinel-2B MSI (True Color)',
          cloud_coverage: 0.2,
          is_baseline: true,
        });
      } catch (satErr) {
        console.warn('Baseline satellite retrieval info:', satErr);
      }

      navigate(`/properties/${created.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to register property record.');
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Add a property</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
          Enter the address, confirm its location on the map, and add basic property details.
        </p>
      </div>

      {error && (
        <div
          style={{
            background: 'var(--color-danger-bg)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            padding: '14px 16px',
            borderRadius: '10px',
            color: '#f87171',
            fontSize: '0.88rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Section 1: Address & Geolocation */}
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h2 style={{ fontSize: '1.15rem', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MapPin size={20} color="#6ee7a8" />
            <span>Step 1: Find the property on the map</span>
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Street Address *
              </label>
              <div className="address-lookup-row" style={{ display: 'flex', gap: '10px' }}>
                <input
                  type="text"
                  name="address"
                  required
                  value={formData.address}
                  onChange={handleInputChange}
                  className="input-field"
                  placeholder="e.g. Flat 1204, Sea Breeze Apartments, Pali Hill, Bandra West"
                />
                <button
                  type="button"
                  onClick={handleGeocode}
                  disabled={geocodingLoading}
                  className="btn btn-primary"
                  style={{ minWidth: '160px' }}
                >
                  <Search size={16} />
                  <span>{geocodingLoading ? 'Finding address...' : 'Find on map'}</span>
                </button>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                City
              </label>
              <input
                type="text"
                name="city"
                value={formData.city}
                onChange={handleInputChange}
                className="input-field"
                placeholder="Mumbai"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                State / UT
              </label>
              <input
                type="text"
                name="state"
                value={formData.state}
                onChange={handleInputChange}
                className="input-field"
                placeholder="Maharashtra"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                PIN code
              </label>
              <input
                type="text"
                name="postal_code"
                value={formData.postal_code}
                onChange={handleInputChange}
                className="input-field"
                placeholder="400050"
              />
            </div>
          </div>

          {/* Interactive Map & Geocoded Output */}
          <div className="registration-map-layout" style={{ marginTop: '22px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
            <div style={{ height: '300px' }}>
              <LeafletMap
                latitude={formData.latitude}
                longitude={formData.longitude}
                editable={true}
                onLocationSelect={handleMapPinSelected}
                popupText={formData.address || 'Property Pin'}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '18px', borderRadius: '10px', border: '1px solid var(--border-glass)' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Map location
                </div>
                <div style={{ display: 'flex', gap: '16px', marginBottom: '12px' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Latitude:</span>
                    <div className="font-mono" style={{ fontSize: '1.05rem', fontWeight: 700, color: '#6ee7a8' }}>
                      {formData.latitude != null ? `${formData.latitude.toFixed(6)}° N` : 'Not set'}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Longitude:</span>
                    <div className="font-mono" style={{ fontSize: '1.05rem', fontWeight: 700, color: '#6ee7a8' }}>
                      {formData.longitude != null ? `${formData.longitude.toFixed(6)}° E` : 'Not set'}
                    </div>
                  </div>
                </div>

                {matchedAddress && (
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.4, marginBottom: '8px' }}>
                    <b>Address found:</b> {matchedAddress}
                  </div>
                )}
                {geocodeSource && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    <b>Map source:</b> {geocodeSource}
                  </div>
                )}
              </div>

              {/* Location Confirmation Requirement */}
              <div
                style={{
                  background: locationConfirmed ? 'var(--color-success-bg)' : 'rgba(245, 158, 11, 0.1)',
                  border: `1px solid ${locationConfirmed ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                  padding: '14px',
                  borderRadius: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  marginTop: '12px',
                }}
              >
                <input
                  type="checkbox"
                  id="confirmLocationCheckbox"
                  checked={locationConfirmed}
                  disabled={formData.latitude == null}
                  onChange={(e) => setLocationConfirmed(e.target.checked)}
                  style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: '#10b981' }}
                />
                <label htmlFor="confirmLocationCheckbox" style={{ fontSize: '0.84rem', cursor: 'pointer', color: locationConfirmed ? '#34d399' : '#fbbf24' }}>
                  <b>Location looks right:</b> I checked the map pin and it marks this property.
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Property Profile & Reference Policy */}
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h2 style={{ fontSize: '1.15rem', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Building2 size={20} color="#34d399" />
            <span>Step 2: Add property details</span>
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Owner name *
              </label>
              <input
                type="text"
                name="owner_name"
                required
                value={formData.owner_name}
                onChange={handleInputChange}
                className="input-field"
                placeholder="e.g. Rohan & Meera Deshmukh"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Owner Contact Details
              </label>
              <input
                type="text"
                name="owner_contact"
                value={formData.owner_contact}
                onChange={handleInputChange}
                className="input-field"
                placeholder="Email or phone number"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Property type
              </label>
              <select
                name="property_type"
                value={formData.property_type}
                onChange={handleInputChange}
                className="input-field"
              >
                <option value="Residential Single Family">Residential Single Family</option>
                <option value="Residential Multi-Family">Residential Multi-Family</option>
                <option value="Residential Luxury Villa">Residential Luxury Villa</option>
                <option value="Commercial Office">Commercial Office</option>
                <option value="Commercial Retail">Commercial Retail</option>
                <option value="Industrial / Warehouse">Industrial / Warehouse</option>
                <option value="Mixed Use">Mixed Use</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Number of floors
              </label>
              <input
                type="number"
                name="number_of_floors"
                min="1"
                max="100"
                value={formData.number_of_floors}
                onChange={handleInputChange}
                className="input-field"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Property size (sq ft)
              </label>
              <input
                type="number"
                name="built_up_area"
                value={formData.built_up_area}
                onChange={handleInputChange}
                className="input-field"
                placeholder="e.g. 2850"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Existing policy number (optional)
              </label>
              <input
                type="text"
                name="reference_policy_number"
                value={formData.reference_policy_number}
                onChange={handleInputChange}
                className="input-field"
                placeholder="e.g. POL-MH-89210-V"
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
                This helps match your property to its policy. You can add the policy details later.
              </span>
            </div>

            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Notes (optional)
              </label>
              <textarea
                name="notes"
                rows="2"
                value={formData.notes}
                onChange={handleInputChange}
                className="input-field"
                placeholder="Add any helpful details about the property"
              />
            </div>
          </div>
        </div>

        {/* Section 3: Baseline Imagery & Monitoring Toggle */}
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h2 style={{ fontSize: '1.15rem', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Upload size={20} color="#f59e0b" />
            <span>Step 3: Photos and monitoring</span>
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Add an existing property photo (optional)
              </label>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
                className="input-field"
                style={{ padding: '8px' }}
              />
              {baselinePreview && (
                <div style={{ marginTop: '12px', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-glass)', maxHeight: '180px' }}>
                  <img src={baselinePreview} alt="Baseline Preview" style={{ width: '100%', height: '180px', objectFit: 'cover' }} />
                </div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Satellite size={20} color="#6ee7a8" />
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Look for an available satellite photo</span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                We’ll try to find an available image for this location after you save. Image availability depends on the imagery provider; you can add your own photo above.
              </p>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <input
                  type="checkbox"
                  name="monitoring_enabled"
                  id="monitoringToggle"
                  checked={formData.monitoring_enabled}
                  onChange={handleInputChange}
                  style={{ width: '18px', height: '18px', accentColor: '#22a866' }}
                />
                <label htmlFor="monitoringToggle" style={{ fontSize: '0.88rem', fontWeight: 600 }}>
                  Turn on property monitoring
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Submit Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '14px' }}>
          <button
            type="button"
            onClick={() => navigate('/properties')}
            className="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !locationConfirmed}
            className="btn btn-primary"
            style={{ minWidth: '200px' }}
          >
            <CheckCircle2 size={18} />
            <span>{submitting ? 'Saving property...' : 'Save property'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};

export default PropertyRegistrationPage;
