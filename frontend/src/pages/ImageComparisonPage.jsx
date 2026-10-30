import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import apiClient from '../api/client';
import ImageSlider from '../components/ImageSlider';
import {
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  BellRing,
  Info,
  ChevronRight
} from 'lucide-react';

const ImageComparisonPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const propertyIdParam = searchParams.get('property_id') || '';
  const baseIdParam = searchParams.get('base') || '';
  const compIdParam = searchParams.get('comp') || '';

  const [properties, setProperties] = useState([]);
  const [loadingProperties, setLoadingProperties] = useState(true);
  const [selectedPropertyId, setSelectedPropertyId] = useState(propertyIdParam);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [loadingSnapshots, setLoadingSnapshots] = useState(false);

  const [baselineSnapshotId, setBaselineSnapshotId] = useState(baseIdParam);
  const [comparisonSnapshotId, setComparisonSnapshotId] = useState(compIdParam);

  // Analysis State
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  // Modification Alert Modal / Creation Form State
  const [showModal, setShowModal] = useState(false);
  const [alertCategory, setAlertCategory] = useState('Rooftop Solar Array');
  const [alertDescription, setAlertDescription] = useState('');
  const [creatingAlert, setCreatingAlert] = useState(false);
  const [createdAlertId, setCreatedAlertId] = useState(null);

  // Load properties
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
        setError("Couldn't load your properties. Check your connection and try again.");
      } finally {
        setLoadingProperties(false);
      }
    };
    loadProps();
  }, []);

  // When property changes, load its snapshots
  useEffect(() => {
    if (!selectedPropertyId) return;
    const loadProperty = async () => {
      setLoadingSnapshots(true);
      setSelectedProperty(null);
      setSnapshots([]);
      setAnalysisResult(null);
      setError(null);
      try {
        const res = await apiClient.getProperty(selectedPropertyId);
        setSelectedProperty(res.data);
        const snaps = res.data.snapshots || [];
        setSnapshots(snaps);

        const base = snaps.find((s) => s.id.toString() === baselineSnapshotId)
          || snaps.find((s) => s.is_baseline)
          || snaps[0];
        const comp = snaps.find((s) => s.id.toString() === comparisonSnapshotId)
          || snaps.find((s) => !s.is_baseline)
          || snaps[1]
          || snaps[0];

        setBaselineSnapshotId(base?.id.toString() || '');
        setComparisonSnapshotId(comp?.id.toString() || '');
      } catch (err) {
        console.error('Failed to load property snapshots', err);
        setError("Couldn't load photos for this property. Please try selecting it again.");
      } finally {
        setLoadingSnapshots(false);
      }
    };
    loadProperty();
  }, [selectedPropertyId]);

  const handleRunAnalysis = async () => {
    if (!selectedPropertyId || !baselineSnapshotId || !comparisonSnapshotId) {
      setError('Please select both a baseline snapshot and a comparison snapshot.');
      return;
    }

    if (baselineSnapshotId === comparisonSnapshotId) {
      setError('Baseline snapshot and comparison snapshot cannot be identical.');
      return;
    }

    setError(null);
    setAnalysisResult(null);
    setAnalyzing(true);
    try {
      const res = await apiClient.compareImages({
        property_id: parseInt(selectedPropertyId, 10),
        baseline_snapshot_id: parseInt(baselineSnapshotId, 10),
        comparison_snapshot_id: parseInt(comparisonSnapshotId, 10),
      });
      setAnalysisResult(res.data);

      // Pre-fill suggested category
      if (res.data.change_score > 25) {
        setAlertCategory('Building Extension / Additional Story');
      } else if (res.data.change_score > 8) {
        setAlertCategory('Rooftop Solar Array');
      } else {
        setAlertCategory('Minor Physical Variance');
      }
      setAlertDescription(res.data.explanation || 'Computer vision difference flagged.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Computer vision analysis failed.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCreateAlert = async (e) => {
    e.preventDefault();
    if (!analysisResult) return;

    setCreatingAlert(true);
    try {
      const res = await apiClient.createModification({
        property_id: parseInt(selectedPropertyId, 10),
        analysis_id: analysisResult.id,
        suspected_category: alertCategory,
        description: alertDescription,
        change_score: analysisResult.change_score,
      });
      setCreatedAlertId(res.data.modification_alert_id);
      setShowModal(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create modification alert.');
    } finally {
      setCreatingAlert(false);
    }
  };

  const selectedBaseSnap = snapshots.find((s) => s.id.toString() === baselineSnapshotId);
  const selectedCompSnap = snapshots.find((s) => s.id.toString() === comparisonSnapshotId);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Compare property photos</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
          View two images side by side or use the slider to look for visible differences.
        </p>
      </div>

      {/* Critical Status Boundary Notice */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Info size={20} color="#6ee7a8" />
          <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
            <b>What this comparison can tell you:</b>{' '}
            It can highlight visual differences, but it cannot tell when or why something changed. A reviewer must confirm any suspected change.
          </div>
        </div>
      </div>

      {error && (
        <div style={{ background: 'var(--color-danger-bg)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '14px 16px', borderRadius: '10px', color: '#f87171', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {createdAlertId && (
        <div style={{ background: 'var(--color-success-bg)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '16px', borderRadius: '10px', color: '#34d399', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle2 size={20} />
            <span>Possible change saved for review. Reference: <b>{createdAlertId}</b></span>
          </div>
          <Link to={`/reviews`} className="btn btn-success btn-sm">
            <span>Open review case</span>
            <ChevronRight size={14} />
          </Link>
        </div>
      )}

      <section className="glass-panel comparison-guide" aria-label="How photo comparison works">
        <h2>What do I do here?</h2>
        <ol>
          <li><b>Choose a property</b> and two photos taken on different dates.</li>
          <li><b>Select Compare photos</b> to highlight parts that look different.</li>
          <li><b>Look over the photos</b> and decide whether a possible change needs review.</li>
        </ol>
        <p>
          This is a visual check, not a decision. Shadows, weather, season, or image quality can also make photos look different.
        </p>
      </section>

      {/* Snapshot Selection Controls */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ marginBottom: '18px' }}>
          <h2 style={{ fontSize: '1.05rem', marginBottom: '4px' }}>Choose the photos to compare</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Start with an earlier photo, then choose a photo from a later date.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
              Property
            </label>
            <select
              value={selectedPropertyId}
              onChange={(e) => {
                setSelectedPropertyId(e.target.value);
                setBaselineSnapshotId('');
                setComparisonSnapshotId('');
              }}
              className="input-field"
              disabled={loadingProperties || properties.length === 0}
            >
              {properties.length === 0 && <option value="">{loadingProperties ? 'Loading properties…' : 'No properties available'}</option>}
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.property_reference} — {p.address}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
              Earlier photo (before)
            </label>
            <select
              value={baselineSnapshotId}
              onChange={(e) => {
                setBaselineSnapshotId(e.target.value);
                setAnalysisResult(null);
              }}
              className="input-field"
              disabled={loadingSnapshots || snapshots.length === 0}
            >
              {snapshots.length === 0 && <option value="">{loadingSnapshots ? 'Loading photos…' : 'No photos available'}</option>}
              {snapshots.map((s) => (
                <option key={s.id} value={s.id}>
                  {new Date(s.acquisition_date).toLocaleDateString()} {s.is_baseline ? '(starting photo)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
              Later photo (after)
            </label>
            <select
              value={comparisonSnapshotId}
              onChange={(e) => {
                setComparisonSnapshotId(e.target.value);
                setAnalysisResult(null);
              }}
              className="input-field"
              disabled={loadingSnapshots || snapshots.length === 0}
            >
              {snapshots.length === 0 && <option value="">{loadingSnapshots ? 'Loading photos…' : 'No photos available'}</option>}
              {snapshots.map((s) => (
                <option key={s.id} value={s.id}>
                  {new Date(s.acquisition_date).toLocaleDateString()} {!s.is_baseline ? '(later photo)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <button
              onClick={handleRunAnalysis}
              disabled={analyzing || loadingSnapshots || snapshots.length < 2 || baselineSnapshotId === comparisonSnapshotId}
              className="btn btn-primary"
              style={{ width: '100%', padding: '11px' }}
            >
              <Sparkles size={16} />
              <span>{analyzing ? 'Checking the photos…' : 'Compare photos'}</span>
            </button>
          </div>
        </div>
        {snapshots.length > 1 && baselineSnapshotId === comparisonSnapshotId && (
          <p className="comparison-selection-help">Choose two different photos before comparing.</p>
        )}
      </div>

      {!loadingProperties && properties.length === 0 && !error && (
        <div className="glass-panel comparison-empty-state">
          <h3>No properties to compare yet</h3>
          <p>Add a property and save at least two photos for it. You can then compare the earlier and later photos here.</p>
          <Link to="/properties/new" className="btn btn-primary">Add a property</Link>
        </div>
      )}

      {selectedProperty && !loadingSnapshots && snapshots.length < 2 && (
        <div className="glass-panel comparison-empty-state">
          <h3>Two photos are needed</h3>
          <p>
            {snapshots.length === 0
              ? 'There are no photos saved for this property yet.'
              : 'Only one photo is saved for this property so far.'}{' '}
            Add another photo on the Property photos page, then come back to compare them.
          </p>
          <Link to={`/satellite?property_id=${selectedProperty.id}`} className="btn btn-primary">Go to Property photos</Link>
        </div>
      )}

      {/* Main Analysis Display */}
      {selectedBaseSnap && selectedCompSnap && baselineSnapshotId !== comparisonSnapshotId && (
        <div style={{ display: 'grid', gridTemplateColumns: analysisResult ? '1fr 380px' : '1fr', gap: '24px' }}>
          {/* Interactive Viewer */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px' }}>
              Compare the pictures
            </h3>

            <ImageSlider
              beforeImage={selectedBaseSnap.image_path}
              afterImage={selectedCompSnap.image_path}
              heatmapImage={analysisResult?.heatmap_image_path}
              beforeLabel={`Earlier photo · ${new Date(selectedBaseSnap.acquisition_date).toLocaleDateString()}`}
              afterLabel={`Later photo · ${new Date(selectedCompSnap.acquisition_date).toLocaleDateString()}`}
              heatmapLabel="Highlighted differences"
            />
          </div>

          {/* AI Signal Analysis Dossier */}
          {analysisResult && (
            <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>What looks different</h3>
                  <span
                    className={`badge ${
                      analysisResult.analysis_result === 'High'
                        ? 'badge-red'
                        : analysisResult.analysis_result === 'Moderate'
                        ? 'badge-amber'
                        : 'badge-green'
                    }`}
                  >
                    {analysisResult.analysis_result === 'High'
                      ? 'Many visible differences'
                      : analysisResult.analysis_result === 'Moderate'
                      ? 'Some visible differences'
                      : 'Few visible differences'}
                  </span>
                </div>

                {/* Metrics Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '18px' }}>
                  <div className="comparison-metric">
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Visual difference score</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--accent-cyan-light)' }}>
                      {analysisResult.change_score}%
                    </div>
                    <div className="comparison-metric-help">Not a chance or confidence score.</div>
                  </div>

                  <div className="comparison-metric">
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Picture area that looks different</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--color-success)' }}>
                      {analysisResult.changed_area_percentage}%
                    </div>
                  </div>
                </div>

                {/* Explanation */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                    What the computer noticed
                  </div>
                  <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    {analysisResult.explanation}
                  </p>
                </div>

                {/* Technical Limitations Notice */}
                <div style={{ background: 'var(--color-warning-bg)', border: '1px solid rgba(168, 103, 8, 0.25)', padding: '12px', borderRadius: '8px', marginBottom: '20px' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-warning)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                    <AlertTriangle size={13} />
                    <span>Keep in mind</span>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                    {analysisResult.limitations}
                  </p>
                </div>
              </div>

              {/* Action: Create Modification Alert */}
              <button
                onClick={() => setShowModal(true)}
                className="btn btn-primary"
                style={{ width: '100%', padding: '12px' }}
              >
                <BellRing size={16} />
                <span>Send for review</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Modal: Create Modification Alert */}
      {showModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(29, 43, 33, 0.45)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '20px',
          }}
        >
          <div className="glass-panel" style={{ maxWidth: '520px', width: '100%', padding: '30px' }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BellRing size={20} color="#6ee7a8" />
              <span>Send a possible change for review</span>
            </h2>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
              This creates a review item. It does not confirm that a property was changed.
            </p>

            <form onSubmit={handleCreateAlert} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                  What might have changed? *
                </label>
                <select
                  value={alertCategory}
                  onChange={(e) => setAlertCategory(e.target.value)}
                  className="input-field"
                >
                  <option value="Rooftop Solar Array">Rooftop Solar Array</option>
                  <option value="Building Extension / Additional Story">Building Extension / Additional Story</option>
                  <option value="Swimming Pool Construction">Swimming Pool Construction</option>
                  <option value="Outbuilding / Shed Addition">Outbuilding / Shed Addition</option>
                  <option value="Paving / Impervious Surface">Paving / Impervious Surface</option>
                  <option value="Roof Replacement">Roof Replacement</option>
                  <option value="General Physical Modification">General Physical Modification</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                  What did you notice? *
                </label>
                <textarea
                  required
                  rows="3"
                  value={alertDescription}
                  onChange={(e) => setAlertDescription(e.target.value)}
                  className="input-field"
                  placeholder="Describe the visible difference. If you are unsure, say so."
                />
              </div>

              <div className="comparison-metric-help" style={{ padding: '12px' }}>
                A reference number will be added so the review can be found later.
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingAlert}
                  className="btn btn-primary"
                >
                  {creatingAlert ? 'Sending for review…' : 'Send for review'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageComparisonPage;
