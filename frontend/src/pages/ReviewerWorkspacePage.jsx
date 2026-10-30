import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import ImageSlider from '../components/ImageSlider';
import StatusBadge from '../components/StatusBadge';
import {
  FileCheck2,
  Building2,
  Calendar,
  Layers,
  Upload,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
  Download,
  Info,
  Clock,
  Send,
  Eye,
  EyeOff,
  Activity,
  Hash
} from 'lucide-react';

const ReviewerWorkspacePage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const caseIdParam = searchParams.get('case') || '';

  const [pendingCases, setPendingCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState(caseIdParam);
  const [caseDossier, setCaseDossier] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [expandedHeatmaps, setExpandedHeatmaps] = useState({});

  const toggleHeatmap = (evId) => {
    setExpandedHeatmaps(prev => ({ ...prev, [evId]: !prev[evId] }));
  };

  // Decision Form State
  const [decision, setDecision] = useState('Verified');
  const [decisionReason, setDecisionReason] = useState('');
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [updatedFloors, setUpdatedFloors] = useState('');
  const [updatedArea, setUpdatedArea] = useState('');
  const [submittingDecision, setSubmittingDecision] = useState(false);

  // Evidence Upload State
  const [uploadCategory, setUploadCategory] = useState('Building Permit');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  // AI Assistance State
  const [aiSummary, setAiSummary] = useState(null);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [analyzingAuthId, setAnalyzingAuthId] = useState(null);

  // Fetch pending review cases
  const loadPendingCases = async () => {
    try {
      const res = await apiClient.getPendingReviews();
      setPendingCases(res.data);
      if (res.data.length > 0 && !selectedCaseId) {
        setSelectedCaseId(res.data[0].id.toString());
      }
    } catch (err) {
      console.error('Failed to load pending reviews', err);
    }
  };

  useEffect(() => {
    loadPendingCases();
  }, []);

  // Fetch full dossier for selected case
  const loadCaseDossier = async (id) => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      setSuccessMsg(null);
      const res = await apiClient.getModification(id);
      setCaseDossier(res.data);
      setAiSummary(null);

      // Pre-fill existing review notes if any
      if (res.data.decision_reason) setDecisionReason(res.data.decision_reason);
      if (res.data.reviewer_notes) setReviewerNotes(res.data.reviewer_notes);
    } catch (err) {
      setError('Could not load this review case.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedCaseId) {
      loadCaseDossier(selectedCaseId);
    }
  }, [selectedCaseId]);

  // Handle Evidence Upload
  const handleEvidenceUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile || !caseDossier) return;

    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('category', uploadCategory);
      formData.append('description', uploadDescription);

      await apiClient.uploadEvidence(caseDossier.id, formData);
      setSuccessMsg(`Successfully uploaded evidence item: ${uploadFile.name}`);
      setUploadFile(null);
      setUploadDescription('');
      // Reload case
      loadCaseDossier(caseDossier.id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Evidence upload failed.');
    } finally {
      setUploading(false);
    }
  };

  // Handle Authenticity Evaluation
  const handleAnalyzeAuthenticity = async (evidenceId) => {
    setAnalyzingAuthId(evidenceId);
    setError(null);
    try {
      await apiClient.analyzeAuthenticity(evidenceId);
      setSuccessMsg('Automated image checks completed. The result is not proof that the image was altered.');
      loadCaseDossier(caseDossier.id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Authenticity analysis failed.');
    } finally {
      setAnalyzingAuthId(null);
    }
  };

  // Handle AI Evidence Summary
  const handleGenerateSummary = async () => {
    if (!caseDossier) return;
    setGeneratingSummary(true);
    setError(null);
    try {
      const res = await apiClient.getEvidenceSummary(caseDossier.id);
      setAiSummary(res.data.summary);
    } catch (err) {
      setError('Failed to generate evidence summary.');
    } finally {
      setGeneratingSummary(false);
    }
  };

  // Submit Formal Verification Decision
  const handleSubmitDecision = async (e) => {
    e.preventDefault();
    if (!decisionReason.trim()) {
      setError('Reviewer decision rationale is required.');
      return;
    }

    setSubmittingDecision(true);
    setError(null);
    try {
      const payload = {
        decision,
        reason: decisionReason,
        notes: reviewerNotes,
        updated_floors: updatedFloors ? parseInt(updatedFloors, 10) : undefined,
        updated_area: updatedArea ? parseFloat(updatedArea) : undefined,
      };

      await apiClient.submitDecision(caseDossier.id, payload);
      setSuccessMsg(`Review saved: ${decision}. The property history has been updated.`);
      loadPendingCases();
      loadCaseDossier(caseDossier.id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit review decision.');
    } finally {
      setSubmittingDecision(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Review possible changes</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
          Check photo differences alongside owner information and supporting documents. Record your finding when you are ready.
        </p>
      </div>

      {/* Boundary Alert Banner */}
      <div style={{ background: 'rgba(34, 168, 102, 0.1)', border: '1px solid rgba(110, 231, 168, 0.3)', padding: '14px 18px', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <ShieldCheck size={20} color="#6ee7a8" />
        <div style={{ fontSize: '0.84rem', color: '#e2e8f0', lineHeight: 1.4 }}>
          <b>Modification review only:</b> This workspace records property-change findings. Claim recommendations and authorized claim decisions are managed separately in the Claims workspace.
        </div>
      </div>

      {error && (
        <div style={{ background: 'var(--color-danger-bg)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '14px 16px', borderRadius: '10px', color: '#f87171', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div style={{ background: 'var(--color-success-bg)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '14px 16px', borderRadius: '10px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
          <CheckCircle2 size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Case Selector Dropdown / Status Bar */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1, minWidth: '320px' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            Choose a case to review:
          </span>
          <select
            value={selectedCaseId}
            onChange={(e) => setSelectedCaseId(e.target.value)}
            className="input-field"
          >
            {pendingCases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.modification_alert_id} — {c.suspected_category} ({c.status}) — {c.property_reference}
              </option>
            ))}
          </select>
        </div>

        {caseDossier && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>Status:</span>
            <StatusBadge status={caseDossier.status} />
            <a
              href={apiClient.getModificationReportUrl(caseDossier.id)}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-sm"
            >
              <Download size={14} />
              <span>Download report</span>
            </a>
          </div>
        )}
      </div>

      {loading || !caseDossier ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          <div className="animate-spin" style={{ display: 'inline-block', width: '28px', height: '28px', border: '3px solid #22a866', borderTopColor: 'transparent', borderRadius: '50%', marginBottom: '12px' }} />
          <div>Loading case details...</div>
        </div>
      ) : (
        <div className="review-case-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '24px' }}>
          {/* Left Column: Visual Difference & Property Context */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Property Profile Strip */}
            <div className="glass-panel" style={{ padding: '20px 24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                <div>
                  <span className="font-mono" style={{ fontSize: '0.86rem', color: '#6ee7a8', fontWeight: 700 }}>
                    {caseDossier.property_reference}
                  </span>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 800 }}>{caseDossier.property_address}</h3>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Change Score</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: caseDossier.change_score > 25 ? '#f87171' : '#34d399' }}>
                    {caseDossier.change_score}%
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
                <b>Suspected Category:</b> {caseDossier.suspected_category}
              </div>
              <p style={{ fontSize: '0.84rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                {caseDossier.description}
              </p>
            </div>

            {/* Visual Slider & Heatmap */}
            {caseDossier.analysis && (
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Layers size={18} color="#6ee7a8" />
                  <span>Photo comparison</span>
                </h3>

                <ImageSlider
                  beforeImage={caseDossier.analysis.diff_image_path}
                  afterImage={caseDossier.analysis.diff_image_path}
                  heatmapImage={caseDossier.analysis.heatmap_image_path}
                  beforeLabel="Image difference"
                  afterLabel="Image difference"
                  heatmapLabel="Highlighted areas"
                />

                <div style={{ marginTop: '16px', fontSize: '0.84rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  <b>Comparison notes:</b> {caseDossier.analysis.explanation}
                </div>
              </div>
            )}

            {/* AI Evidence Summarizer Section */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={18} color="#6ee7a8" />
                  <span>Summary of the submitted documents</span>
                </h3>

                <button
                  onClick={handleGenerateSummary}
                  disabled={generatingSummary}
                  className="btn btn-secondary btn-sm"
                >
                  <Sparkles size={14} />
                  <span>{generatingSummary ? 'Preparing summary...' : 'Create a summary'}</span>
                </button>
              </div>

              {aiSummary ? (
                <div style={{ background: 'rgba(34, 168, 102, 0.08)', border: '1px solid rgba(110, 231, 168, 0.25)', padding: '14px', borderRadius: '8px', fontSize: '0.86rem', color: '#e2e8f0', lineHeight: 1.5 }}>
                  {aiSummary}
                </div>
              ) : (
                <div style={{ fontSize: '0.82rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>
                  Create a short summary of the documents and notes shared for this case.
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Evidence Inventory, Authenticity Analysis & Decision Form */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Supporting Evidence Inventory & Authenticity Check */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>
                  Photos and documents ({caseDossier.evidence_items?.length || 0})
                </h3>
              </div>

              {caseDossier.evidence_items && caseDossier.evidence_items.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {caseDossier.evidence_items.map((ev) => {
                    const latestAuth = ev.authenticity_analyses?.[0];
                    return (
                      <div
                        key={ev.id}
                        style={{
                          background: 'rgba(15, 23, 42, 0.55)',
                          border: '1px solid var(--border-glass)',
                          borderRadius: '10px',
                          padding: '16px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                          <span className="badge badge-cyan">{ev.category}</span>
                          <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>
                            {new Date(ev.uploaded_at).toLocaleDateString()}
                          </span>
                        </div>

                        <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px' }}>
                          {ev.original_filename}
                        </div>
                        {ev.description && (
                          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                            {ev.description}
                          </div>
                        )}

                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: 'var(--text-dim)', marginBottom: '12px' }}>
                          <Hash size={12} />
                          <span>File securely recorded</span>
                        </div>
                        <details style={{ marginBottom: '10px' }}>
                          <summary>View file verification code</summary>
                          <div className="font-mono" style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 6, wordBreak: 'break-all' }}>
                            <Hash size={12} /> SHA-256: {ev.file_hash}
                          </div>
                        </details>

                        {/* Authenticity Assessment Block */}
                        {latestAuth ? (
                          <div
                            style={{
                              background: latestAuth.result.includes('No AI')
                                ? 'rgba(16, 185, 129, 0.08)'
                                : latestAuth.result.includes('Potential')
                                ? 'rgba(239, 68, 68, 0.12)'
                                : 'rgba(245, 158, 11, 0.1)',
                              border: `1px solid ${
                                latestAuth.result.includes('No AI')
                                  ? 'rgba(16, 185, 129, 0.35)'
                                  : latestAuth.result.includes('Potential')
                                  ? 'rgba(239, 68, 68, 0.45)'
                                  : 'rgba(245, 158, 11, 0.35)'
                              }`,
                              padding: '14px',
                              borderRadius: '10px',
                              marginBottom: '12px',
                            }}
                          >
                            {/* Header */}
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                {latestAuth.result.includes('Potential') ? (
                                  <ShieldAlert size={16} color="#ef4444" />
                                ) : (
                                  <ShieldCheck size={16} color="#10b981" />
                                )}
                                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: latestAuth.result.includes('Potential') ? '#f87171' : '#34d399' }}>
                                  {latestAuth.raw_response?.summary_finding || latestAuth.result}
                                </span>
                              </div>
                              {latestAuth.raw_response?.deepfake_probability !== undefined && (
                                <span
                                  className="badge"
                                  style={{
                                    background: latestAuth.raw_response.deepfake_probability >= 0.75
                                      ? 'rgba(239, 68, 68, 0.25)'
                                      : latestAuth.raw_response.deepfake_probability >= 0.45
                                      ? 'rgba(245, 158, 11, 0.25)'
                                      : 'rgba(16, 185, 129, 0.25)',
                                    color: latestAuth.raw_response.deepfake_probability >= 0.75
                                      ? '#fca5a5'
                                      : latestAuth.raw_response.deepfake_probability >= 0.45
                                      ? '#fcd34d'
                                      : '#6ee7b7',
                                    border: '1px solid currentColor',
                                    fontWeight: 700,
                                    fontSize: '0.75rem'
                                  }}
                                >
                                  {(latestAuth.raw_response.deepfake_probability * 100).toFixed(1)}% automated image-check score
                                </span>
                              )}
                            </div>

                            {/* Explanation */}
                            <div style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: 1.4, marginBottom: '10px' }}>
                              {latestAuth.explanation}
                            </div>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '10px' }}>
                              This automated score is not proof of editing, fraud, or misleading evidence. Review the original file and other information.
                            </p>

                            {/* Forensic Signal Metrics */}
                            {latestAuth.raw_response && (
                              <div
                                style={{
                                  display: 'grid',
                                  gridTemplateColumns: 'repeat(2, 1fr)',
                                  gap: '8px',
                                  padding: '10px',
                                  background: 'rgba(15, 23, 42, 0.65)',
                                  borderRadius: '8px',
                                  border: '1px solid rgba(255, 255, 255, 0.06)',
                                  fontSize: '0.73rem',
                                  marginBottom: '10px'
                                }}
                              >
                                <div>
                                  <span style={{ color: 'var(--text-dim)' }}>Image pattern check:</span>{' '}
                                  <b style={{ color: '#6ee7a8' }}>{(latestAuth.raw_response.diffusion_spectral_score * 100).toFixed(0)}%</b>
                                </div>
                                <div>
                                  <span style={{ color: 'var(--text-dim)' }}>File compression check:</span>{' '}
                                  <b style={{ color: '#e2e8f0' }}>{latestAuth.raw_response.ela_metric}</b>
                                </div>
                                <div>
                                  <span style={{ color: 'var(--text-dim)' }}>Image noise check:</span>{' '}
                                  <b style={{ color: '#e2e8f0' }}>{latestAuth.raw_response.noise_variance}</b>
                                </div>
                                <div>
                                  <span style={{ color: 'var(--text-dim)' }}>Camera information:</span>{' '}
                                  <b style={{ color: latestAuth.raw_response.has_camera_exif ? '#34d399' : '#f59e0b' }}>
                                    {latestAuth.raw_response.has_camera_exif ? 'Found in file' : 'Not found in file'}
                                  </b>
                                </div>
                              </div>
                            )}

                            {/* Forensic Heatmap Toggle */}
                            {latestAuth.raw_response?.forensic_heatmap_url && (
                              <div style={{ marginTop: '8px' }}>
                                <button
                                  type="button"
                                  onClick={() => toggleHeatmap(ev.id)}
                                  className="btn btn-secondary btn-sm"
                                  style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                                >
                                  {expandedHeatmaps[ev.id] ? <EyeOff size={13} /> : <Eye size={13} />}
                                  <span>                                  {expandedHeatmaps[ev.id] ? 'Hide image check' : 'View image check'}</span>
                                </button>

                                {expandedHeatmaps[ev.id] && (
                                  <div style={{ marginTop: '10px', borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(110, 231, 168, 0.3)' }}>
                                    <img
                                      src={latestAuth.raw_response.forensic_heatmap_url}
                                      alt="Image file check result"
                                      style={{ width: '100%', display: 'block', maxHeight: '260px', objectFit: 'contain', background: '#000' }}
                                    />
                                    <div style={{ padding: '6px 10px', background: 'rgba(15, 23, 42, 0.95)', fontSize: '0.72rem', color: '#94a3b8', textAlign: 'center' }}>
                                      These highlights are automated checks. They cannot prove that an image was altered or misleading.
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Re-analyze Button */}
                            <div style={{ marginTop: '8px' }}>
                              <button
                                onClick={() => handleAnalyzeAuthenticity(ev.id)}
                                disabled={analyzingAuthId === ev.id}
                                style={{
                                  background: 'transparent',
                                  border: 'none',
                                  color: '#6ee7a8',
                                  fontSize: '0.72rem',
                                  cursor: 'pointer',
                                  textDecoration: 'underline',
                                  padding: 0
                                }}
                              >
                                {analyzingAuthId === ev.id ? 'Checking image...' : 'Run image checks again'}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div style={{ marginBottom: '12px' }}>
                            {ev.file_type.startsWith('image/') ? (
                              <button
                                onClick={() => handleAnalyzeAuthenticity(ev.id)}
                                disabled={analyzingAuthId === ev.id}
                                className="btn btn-secondary btn-sm"
                                style={{ width: '100%' }}
                              >
                                <Sparkles size={13} />
                                <span>{analyzingAuthId === ev.id ? 'Checking image...' : 'Check this photo'}</span>
                              </button>
                            ) : (
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Automated image checks are available for photos only.</span>
                            )}
                          </div>
                        )}

                        <a
                          href={apiClient.getEvidenceDownloadUrl(ev.id)}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-secondary btn-sm"
                          style={{ width: '100%' }}
                        >
                          <Download size={13} />
                          <span>Download file</span>
                        </a>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)', fontSize: '0.84rem' }}>
                  No photos or documents have been added to this case yet.
                </div>
              )}

              {/* Upload New Evidence Form */}
              <div style={{ marginTop: '20px', paddingTop: '18px', borderTop: '1px solid var(--border-glass)' }}>
                <h4 style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Upload size={15} color="#6ee7a8" />
                  <span>Add a document or photo</span>
                </h4>

                <form onSubmit={handleEvidenceUpload} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <select
                      value={uploadCategory}
                      onChange={(e) => setUploadCategory(e.target.value)}
                      className="input-field"
                    >
                      <option value="Building Permit">Building Permit</option>
                      <option value="Contractor Invoice">Contractor Invoice</option>
                      <option value="Photograph">Current Photograph</option>
                      <option value="Architectural Drawing">Architectural Drawing</option>
                      <option value="Other">Other Document</option>
                    </select>

                    <input
                      type="file"
                      required
                      onChange={(e) => setUploadFile(e.target.files[0])}
                      className="input-field"
                      style={{ padding: '6px' }}
                    />
                  </div>

                  <input
                    type="text"
                    value={uploadDescription}
                    onChange={(e) => setUploadDescription(e.target.value)}
                    placeholder="Description (e.g. Electrical Permit for 14.4kW rooftop array)..."
                    className="input-field"
                  />

                  <button
                    type="submit"
                    disabled={uploading || !uploadFile}
                    className="btn btn-secondary btn-sm"
                  >
                    <Upload size={14} />
                    <span>{uploading ? 'Computing Hash & Uploading...' : 'Upload & Compute SHA-256'}</span>
                  </button>
                </form>
              </div>
            </div>

            {/* Formal Verification Decision Form */}
            <div className="glass-panel" style={{ padding: '26px', border: '1px solid rgba(110, 231, 168, 0.3)' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileCheck2 size={20} color="#10b981" />
                <span>Formal Modification Determination</span>
              </h3>

              <form onSubmit={handleSubmitDecision} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
                    Verification Decision *
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                    <button
                      type="button"
                      onClick={() => setDecision('Verified')}
                      className={`btn btn-sm ${decision === 'Verified' ? 'btn-success' : 'btn-secondary'}`}
                    >
                      <CheckCircle2 size={14} />
                      <span>Verified</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setDecision('Not Confirmed')}
                      className={`btn btn-sm ${decision === 'Not Confirmed' ? 'btn-danger' : 'btn-secondary'}`}
                    >
                      <XCircle size={14} />
                      <span>Not Confirmed</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setDecision('Additional Evidence Required')}
                      className={`btn btn-sm ${decision === 'Additional Evidence Required' ? 'btn-primary' : 'btn-secondary'}`}
                    >
                      <Clock size={14} />
                      <span>Request Evidence</span>
                    </button>
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                    Decision Rationale & Corroborating Evidence *
                  </label>
                  <textarea
                    required
                    rows="3"
                    value={decisionReason}
                    onChange={(e) => setDecisionReason(e.target.value)}
                    className="input-field"
                    placeholder="Document the exact basis for verification (e.g. Building permit #1042 matches rooftop solar footprint)..."
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                    Internal Reviewer Notes
                  </label>
                  <input
                    type="text"
                    value={reviewerNotes}
                    onChange={(e) => setReviewerNotes(e.target.value)}
                    className="input-field"
                    placeholder="Optional administrative notes for audit log..."
                  />
                </div>

                {/* Property Attribute Update on Verified */}
                {decision === 'Verified' && (
                  <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '14px', borderRadius: '10px' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#34d399', marginBottom: '8px' }}>
                      Update Verified Property Record Attributes (Optional)
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '4px' }}>
                          Updated Stories / Floors
                        </label>
                        <input
                          type="number"
                          value={updatedFloors}
                          onChange={(e) => setUpdatedFloors(e.target.value)}
                          placeholder="e.g. 2"
                          className="input-field"
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '4px' }}>
                          Updated Built-up Area (sq ft)
                        </label>
                        <input
                          type="number"
                          value={updatedArea}
                          onChange={(e) => setUpdatedArea(e.target.value)}
                          placeholder="e.g. 3500"
                          className="input-field"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={submittingDecision}
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '13px' }}
                >
                  <Send size={16} />
                  <span>{submittingDecision ? 'Recording Determination...' : 'Commit Verification Determination'}</span>
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReviewerWorkspacePage;
