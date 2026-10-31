import React, { useEffect, useState } from 'react';
import { Download, FileText, RefreshCw, ShieldCheck, Upload } from 'lucide-react';
import apiClient from '../api/client';
import { formatINR } from '../utils/format';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';

const inputStyle = { width: '100%', marginTop: '6px' };
const panelStyle = { padding: '22px' };

const ClaimsPage = () => {
  const { user } = useAuth();
  const [claims, setClaims] = useState([]);
  const [properties, setProperties] = useState([]);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [file, setFile] = useState(null);
  const [evidenceCategory, setEvidenceCategory] = useState('Damage Photograph');
  const [form, setForm] = useState({
    property_id: '',
    incident_date: '',
    reported_cause: '',
    description: '',
    estimated_loss: '',
  });
  const [assessment, setAssessment] = useState({ indicators: '', findings: '' });
  const [calculation, setCalculation] = useState({
    gross: '',
    excluded: '0',
    limitKey: '',
    deductibleKey: '',
    assumptions: '',
  });
  const [recommendation, setRecommendation] = useState({
    recommendation_type: 'REQUEST_MORE_DOCUMENTS',
    reasoning: '',
    clauses: '',
  });
  const [decision, setDecision] = useState({ decision: 'APPROVED', rationale: '', authorized_amount: '', clauses: '' });
  const [declaration, setDeclaration] = useState({ modification_id: '', declaration_type: 'EXPLAIN', statement: '' });

  const loadClaims = async (claimId = selected?.id) => {
    setBusy(true);
    setError('');
    try {
      const [claimResponse, propertyResponse] = await Promise.all([
        apiClient.getClaims(),
        apiClient.getProperties(),
      ]);
      setClaims(claimResponse.data);
      setProperties(propertyResponse.data);
      const nextId = claimId || claimResponse.data[0]?.id;
      if (nextId) {
        const detailResponse = await apiClient.getClaim(nextId);
        setSelected(detailResponse.data);
      } else {
        setSelected(null);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to load claim records.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadClaims(null);
  }, []);

  const refreshSelected = () => loadClaims(selected?.id);

  const createClaim = async (event) => {
    event.preventDefault();
    setMessage('');
    setError('');
    try {
      const response = await apiClient.createClaim({
        ...form,
        property_id: Number(form.property_id),
        incident_date: new Date(form.incident_date).toISOString(),
        estimated_loss: Number(form.estimated_loss),
      });
      setForm({ property_id: '', incident_date: '', reported_cause: '', description: '', estimated_loss: '' });
      setMessage(`Claim ${response.data.claim_reference} registered.`);
      await loadClaims(response.data.id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to register claim.');
    }
  };

  const uploadEvidence = async (event) => {
    event.preventDefault();
    if (!selected || !file) return;
    const payload = new FormData();
    payload.append('file', file);
    payload.append('category', evidenceCategory);
    try {
      await apiClient.uploadClaimEvidence(selected.id, payload);
      setFile(null);
      setMessage('Your file was added to the claim record.');
      await refreshSelected();
    } catch (err) {
      setError(err.response?.data?.detail || 'Evidence upload failed.');
    }
  };

  const downloadResponse = (response, filename) => {
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const submitAssessment = async (event) => {
    event.preventDefault();
    try {
      await apiClient.createDamageAssessment(selected.id, {
        claim_id: selected.id,
        observed_damage_indicators: assessment.indicators.split('\n').map((item) => item.trim()).filter(Boolean),
        human_findings: assessment.findings || null,
      });
      setMessage('Reviewer notes saved separately from automated image checks.');
      await refreshSelected();
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to record the damage assessment.');
    }
  };

  const calculateAmount = async (event) => {
    event.preventDefault();
    const policy = selected?.policy;
    if (!policy?.terms_verified) {
      setError('Policy terms must be verified before a provisional calculation can be made.');
      return;
    }
    try {
      await apiClient.calculateProvisional(selected.id, {
        claim_id: selected.id,
        gross_claimed_loss: Number(calculation.gross || selected.estimated_loss),
        limit_category: calculation.limitKey,
        non_covered_excluded_amount: Number(calculation.excluded),
        deductible_type_applied: calculation.deductibleKey,
        calculation_method: 'max(0, min(gross loss - explicitly assessed excluded amount, verified coverage limit) - verified deductible)',
        assumptions: calculation.assumptions,
      });
      setMessage('Early estimate saved for review. It is not a final claim decision.');
      await refreshSelected();
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to calculate a provisional amount.');
    }
  };

  const submitRecommendation = async (event) => {
    event.preventDefault();
    try {
      await apiClient.recommendClaim(selected.id, {
        recommendation_type: recommendation.recommendation_type,
        reasoning: recommendation.reasoning,
        applicable_policy_clauses: recommendation.clauses.split('\n').map((item) => item.trim()).filter(Boolean),
        evidence_references: selected.evidence_items.map((item) => `Evidence ${item.id}: ${item.file_hash}`),
      });
      setMessage('Reviewer suggestion saved. It does not finalize the claim.');
      await refreshSelected();
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to record reviewer recommendation.');
    }
  };

  const submitDecision = async (event) => {
    event.preventDefault();
    try {
      await apiClient.decideClaim(selected.id, {
        decision: decision.decision,
        rationale: decision.rationale,
        authorized_amount: decision.authorized_amount ? Number(decision.authorized_amount) : null,
        applicable_policy_clauses: decision.clauses.split('\n').map((item) => item.trim()).filter(Boolean),
      });
      setMessage('Final decision saved in the claim history.');
      await refreshSelected();
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to record authorized decision.');
    }
  };

  const [settle, setSettle] = useState({ settled_amount: '', payment_mode: 'NEFT', payment_reference: '' });
  const submitSettlement = async (event) => {
    event.preventDefault();
    try {
      await apiClient.settleClaim(selected.id, { ...settle, settled_amount: Number(settle.settled_amount) });
      setMessage('Payment recorded.');
      setSettle({ settled_amount: '', payment_mode: 'NEFT', payment_reference: '' });
      await refreshSelected();
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to record settlement.');
    }
  };

  const submitDeclaration = async (event) => {
    event.preventDefault();
    try {
      await apiClient.submitOwnerDeclaration({
        property_id: selected.property_id,
        modification_id: declaration.modification_id ? Number(declaration.modification_id) : null,
        declaration_type: declaration.declaration_type,
        statement: declaration.statement,
      });
      setMessage('Owner declaration submitted and added to the property history.');
      setDeclaration({ modification_id: '', declaration_type: 'EXPLAIN', statement: '' });
      await refreshSelected();
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to submit owner declaration.');
    }
  };

  const canRegister = ['owner', 'admin'].includes(user?.role);
  const canReview = ['admin', 'reviewer', 'decision_maker'].includes(user?.role);
  const canDecide = ['admin', 'decision_maker'].includes(user?.role);

  return (
    <div style={{ display: 'grid', gap: '20px' }}>
      <header>
        <h1 style={{ fontSize: '1.7rem', fontWeight: 800 }}>Insurance claims</h1>
        <p style={{ color: 'var(--text-muted)' }}>Submit a claim, share documents, and follow its progress.</p>
      </header>
      <div role="note" className="glass-panel" style={{ ...panelStyle, borderColor: 'rgba(56,189,248,.35)' }}>
        <ShieldCheck size={17} style={{ verticalAlign: 'middle', marginRight: 8 }} />
        Photo checks and policy notes are only supporting information. A person reviews every claim; missing photos or unclear terms do not automatically reject it.
      </div>
      {error && <div role="alert" className="glass-panel" style={{ ...panelStyle, color: '#f87171' }}>{error}</div>}
      {message && <div role="status" className="glass-panel" style={{ ...panelStyle, color: '#34d399' }}>{message}</div>}

      {canRegister && (
        <form className="glass-panel" style={panelStyle} onSubmit={createClaim}>
          <h2 style={{ marginBottom: 6 }}>Start a claim</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: 14 }}>Tell us what happened. You can add photos and documents after creating the claim.</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 12 }}>
            <label>Property
              <select className="form-input" style={inputStyle} required value={form.property_id} onChange={(e) => setForm({ ...form, property_id: e.target.value })}>
                <option value="">Choose a property with a linked policy</option>
                {properties.map((property) => <option value={property.id} key={property.id}>{property.property_reference} — {property.address}</option>)}
              </select>
            </label>
            <label>Date it happened<input className="form-input" style={inputStyle} type="date" required value={form.incident_date} onChange={(e) => setForm({ ...form, incident_date: e.target.value })} /></label>
            <label>What caused the damage?<input className="form-input" style={inputStyle} required value={form.reported_cause} onChange={(e) => setForm({ ...form, reported_cause: e.target.value })} placeholder="For example, a storm" /></label>
            <label>Estimated repair cost<input className="form-input" style={inputStyle} type="number" min="0" step="0.01" required value={form.estimated_loss} onChange={(e) => setForm({ ...form, estimated_loss: e.target.value })} /></label>
          </div>
          <label style={{ display: 'block', margin: '12px 0' }}>Describe what happened<textarea className="form-input" style={inputStyle} rows="3" required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <button className="btn btn-primary" type="submit">Create claim</button>
        </form>
      )}

      <div className="claims-layout" style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, .7fr) minmax(0, 2fr)', gap: '18px', alignItems: 'start' }}>
        <section className="glass-panel" style={panelStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h2>Your claims</h2>
            <button className="btn btn-secondary" type="button" onClick={() => loadClaims()} title="Refresh"><RefreshCw size={15} /></button>
          </div>
          {busy && <p>Loading claims…</p>}
          {claims.map((claim) => (
            <button key={claim.id} type="button" onClick={() => loadClaims(claim.id)} className="glass-panel"
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: 12, marginBottom: 8, color: 'inherit', borderColor: selected?.id === claim.id ? '#6ee7a8' : undefined }}>
              <b>{claim.claim_reference}</b>
              <div style={{ color: 'var(--text-muted)', fontSize: '.82rem', marginTop: 4 }}>{claim.property_reference}</div>
              <StatusBadge status={claim.status} />
              <div style={{ color: 'var(--text-dim)', fontSize: '.78rem' }}>{claim.reported_cause}</div>
            </button>
          ))}
          {!claims.length && !busy && <p style={{ color: 'var(--text-muted)' }}>No claims are available for this account.</p>}
        </section>

        {selected ? (
          <section className="glass-panel" style={{ ...panelStyle, display: 'grid', gap: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
              <div>
                <h2>{selected.claim_reference}</h2>
                <p style={{ color: 'var(--text-muted)' }}>{selected.property_address} · Policy {selected.policy_number}</p>
                <StatusBadge status={selected.status} />
              </div>
              <button className="btn btn-secondary" type="button" onClick={async () => {
                try { downloadResponse(await apiClient.downloadClaimReport(selected.id), `${selected.claim_reference}.pdf`); }
                catch (err) { setError(err.response?.data?.detail || 'Unable to download the claim report.'); }
              }}><Download size={15} /> Download claim summary</button>
            </div>

            <div className="glass-panel" style={panelStyle}>
              <h3>What happened</h3>
              <p>{selected.incident_date?.slice(0, 10)} · {selected.reported_cause} · Estimated cost: {formatINR(selected.estimated_loss)}</p>
              <p>{selected.description}</p>
            </div>

            <div className="glass-panel" style={panelStyle}>
              <h3>Insurance policy information</h3>
              <p style={{ color: 'var(--text-muted)' }}>{selected.policy?.terms_verified
                ? 'Policy details have been checked against the uploaded document.'
                : 'Policy details have not been confirmed yet. A reviewer will check them before any estimate is prepared.'}</p>
              <details style={{ marginTop: 10 }}>
                <summary style={{ cursor: 'pointer' }}>View policy details</summary>
                <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-muted)', marginTop: 10 }}>{JSON.stringify({
                  'Coverage limits': selected.policy?.coverage_limits,
                  Deductibles: selected.policy?.deductibles,
                  'Items not covered': selected.policy?.exclusions,
                  'Additional policy terms': selected.policy?.endorsements,
                }, null, 2)}</pre>
              </details>
            </div>

            {canRegister && selected.user_id === user?.id && (
              <form className="glass-panel" style={panelStyle} onSubmit={submitDeclaration}>
                <h3>Tell us about a possible change</h3>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <select className="form-input" value={declaration.declaration_type} onChange={(e) => setDeclaration({ ...declaration, declaration_type: e.target.value })}>
                    <option value="CONFIRM">Confirm</option><option value="DISPUTE">Dispute</option><option value="EXPLAIN">Explain</option>
                  </select>
                  <select className="form-input" value={declaration.modification_id} onChange={(e) => setDeclaration({ ...declaration, modification_id: e.target.value })}>
                    <option value="">No linked alert</option>
                    {(selected.related_modifications || []).map((mod) => <option key={mod.id} value={mod.id}>{mod.modification_alert_id}</option>)}
                  </select>
                </div>
                <textarea className="form-input" style={inputStyle} rows="2" required value={declaration.statement} onChange={(e) => setDeclaration({ ...declaration, statement: e.target.value })} placeholder="Explain, confirm, or dispute the suspected change" />
                <button className="btn btn-secondary" style={{ marginTop: 10 }} type="submit">Send your response</button>
              </form>
            )}

            <div className="glass-panel" style={panelStyle}>
              <h3>Photos and documents ({selected.evidence_items?.length || 0})</h3>
              {selected.evidence_items?.map((item) => (
                <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, borderTop: '1px solid var(--border-glass)', padding: '10px 0' }}>
                  <span>
                    <FileText size={14} /> {item.original_filename} · {item.category}<br /><small>File verified and recorded</small>
                    <details style={{ marginTop: 5 }}>
                      <summary>File verification details</summary>
                      <small style={{ wordBreak: 'break-all' }}>SHA-256: {item.file_hash}</small>
                    </details>
                  </span>
                  <button className="btn btn-secondary" type="button" onClick={async () => {
                    try { downloadResponse(await apiClient.downloadClaimEvidence(selected.id, item.id), item.original_filename); }
                    catch (err) { setError(err.response?.data?.detail || 'Unable to download evidence.'); }
                  }}><Download size={14} /></button>
                </div>
              ))}
              <form onSubmit={uploadEvidence} style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 10 }}>
                <select className="form-input" value={evidenceCategory} onChange={(e) => setEvidenceCategory(e.target.value)}>
                  <option>Damage Photograph</option><option>Repair Estimate</option><option>Contractor Invoice</option><option>Inspection Report</option><option>Policy Document</option><option>Other</option>
                </select>
                <input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                <button className="btn btn-secondary" type="submit" disabled={!file}><Upload size={15} /> Add file</button>
              </form>
            </div>

            <div className="glass-panel" style={panelStyle}>
              <h3>Related property updates</h3>
              {(selected.related_modifications || []).map((mod) => <p key={mod.id}>{mod.modification_alert_id}: {mod.suspected_category} — {mod.status}</p>)}
              {(selected.related_declarations || []).map((item) => <p key={item.id}>Declaration {item.declaration_type} — {item.status} ({item.created_at?.slice(0, 10)})</p>)}
              {!selected.related_modifications?.length && !selected.related_declarations?.length && <p style={{ color: 'var(--text-muted)' }}>No recorded modification or declaration context.</p>}
            </div>

            {canReview && (
              <>
                <form className="glass-panel" style={panelStyle} onSubmit={submitAssessment}>
                  <h3>Reviewer notes about the damage</h3>
                  <label>What can be seen? (one item per line)<textarea className="form-input" style={inputStyle} rows="3" value={assessment.indicators} onChange={(e) => setAssessment({ ...assessment, indicators: e.target.value })} /></label>
                  <label>Reviewer’s notes<textarea className="form-input" style={inputStyle} rows="2" value={assessment.findings} onChange={(e) => setAssessment({ ...assessment, findings: e.target.value })} /></label>
                  <button className="btn btn-secondary" style={{ marginTop: 10 }} type="submit">Save notes</button>
                  {selected.damage_assessment && <p>Automated image check: {selected.damage_assessment.ai_damage_suggestions?.summary || 'Not available. No automated finding was made.'}</p>}
                </form>

                {selected.policy?.terms_verified && (
                  <form className="glass-panel" style={panelStyle} onSubmit={calculateAmount}>
                    <h3>Early estimate (not a decision)</h3>
                    <p style={{ color: 'var(--text-muted)' }}>This estimate uses the confirmed policy information and the amounts entered below. A reviewer still needs to check it.</p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 10 }}>
                      <label>Total estimated damage<input className="form-input" style={inputStyle} type="number" min="0" value={calculation.gross || selected.estimated_loss} onChange={(e) => setCalculation({ ...calculation, gross: e.target.value })} /></label>
                      <label>Amount not covered (if known)<input className="form-input" style={inputStyle} type="number" min="0" value={calculation.excluded} onChange={(e) => setCalculation({ ...calculation, excluded: e.target.value })} /></label>
                      <label>Policy coverage type<select className="form-input" style={inputStyle} required value={calculation.limitKey} onChange={(e) => setCalculation({ ...calculation, limitKey: e.target.value })}><option value="">Choose</option>{Object.keys(selected.policy.coverage_limits || {}).map((key) => <option key={key}>{key}</option>)}</select></label>
                      <label>Deductible type<select className="form-input" style={inputStyle} required value={calculation.deductibleKey} onChange={(e) => setCalculation({ ...calculation, deductibleKey: e.target.value })}><option value="">Choose</option>{Object.keys(selected.policy.deductibles || {}).map((key) => <option key={key}>{key}</option>)}</select></label>
                    </div>
                    <label>Notes about this estimate<textarea className="form-input" style={inputStyle} required value={calculation.assumptions} onChange={(e) => setCalculation({ ...calculation, assumptions: e.target.value })} /></label>
                    <button className="btn btn-secondary" style={{ marginTop: 10 }} type="submit">Prepare estimate</button>
                  </form>
                )}

                <form className="glass-panel" style={panelStyle} onSubmit={submitRecommendation}>
                  <h3>Reviewer’s suggested next step</h3>
                  <select className="form-input" value={recommendation.recommendation_type} onChange={(e) => setRecommendation({ ...recommendation, recommendation_type: e.target.value })}>
                              <option value="REQUEST_MORE_DOCUMENTS">Ask for more documents</option><option value="REQUEST_INSPECTION">Arrange an inspection</option><option value="APPROVE_PROVISIONAL">Recommend approval for review</option><option value="REDUCE_AMOUNT">Recommend changing the amount</option><option value="DENY_EXCLUDED">Recommend denial for review</option>
                  </select>
                  <textarea className="form-input" style={inputStyle} required value={recommendation.reasoning} onChange={(e) => setRecommendation({ ...recommendation, reasoning: e.target.value })} placeholder="Explain why you suggest this next step" />
                  <textarea className="form-input" style={inputStyle} value={recommendation.clauses} onChange={(e) => setRecommendation({ ...recommendation, clauses: e.target.value })} placeholder="Relevant wording from the verified policy (optional)" />
                  <button className="btn btn-secondary" style={{ marginTop: 10 }} type="submit">Save suggested next step</button>
                </form>
              </>
            )}

            {canDecide && (
              <form className="glass-panel" style={panelStyle} onSubmit={submitDecision}>
                <h3>Final decision (authorized staff only)</h3>
                <select className="form-input" value={decision.decision} onChange={(e) => setDecision({ ...decision, decision: e.target.value })}>
                  <option value="APPROVED">Approved</option><option value="APPROVED_PARTIAL">Approved partial</option><option value="MORE_INFO_REQUESTED">More information requested</option><option value="INSPECTION_ORDERED">Inspection ordered</option><option value="DENIED">Denied</option>
                </select>
                <label>Authorized amount (optional)<input className="form-input" style={inputStyle} type="number" min="0" step="0.01" value={decision.authorized_amount} onChange={(e) => setDecision({ ...decision, authorized_amount: e.target.value })} /></label>
                <textarea className="form-input" style={inputStyle} required value={decision.rationale} onChange={(e) => setDecision({ ...decision, rationale: e.target.value })} placeholder="Authorized reviewer rationale" />
                <textarea className="form-input" style={inputStyle} value={decision.clauses} onChange={(e) => setDecision({ ...decision, clauses: e.target.value })} placeholder="Applicable verified policy clauses (one per line)" />
                <button className="btn btn-primary" style={{ marginTop: 10 }} type="submit">Record authorized decision</button>
              </form>
            )}

            {canDecide && ['Approved', 'Partially Approved'].includes(selected.status) && (
              <form className="glass-panel" style={panelStyle} onSubmit={submitSettlement}>
                <h3>Record settlement payment</h3>
                <label>Amount paid (₹)<input className="form-input" style={inputStyle} type="number" min="0" step="0.01" required value={settle.settled_amount} onChange={(e) => setSettle({ ...settle, settled_amount: e.target.value })} /></label>
                <select className="form-input" value={settle.payment_mode} onChange={(e) => setSettle({ ...settle, payment_mode: e.target.value })}>
                  {['NEFT', 'RTGS', 'UPI', 'IMPS', 'CHEQUE'].map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                <input className="form-input" style={inputStyle} required minLength={3} value={settle.payment_reference} onChange={(e) => setSettle({ ...settle, payment_reference: e.target.value })} placeholder="UTR / cheque number" />
                <button className="btn btn-primary" style={{ marginTop: 10 }} type="submit">Record payment</button>
              </form>
            )}

            <details className="glass-panel" style={panelStyle}>
              <summary>Review notes and claim history</summary>
              {(selected.rule_executions || []).map((rule) => <p key={rule.id}>Policy check: <b>{rule.result.replaceAll('_', ' ').toLowerCase()}</b> — {rule.explanation}</p>)}
              {(selected.calculations || []).map((item) => <p key={item.id}>Early estimate: {formatINR(item.provisional_net_payout)}</p>)}
              {(selected.recommendations || []).map((item) => <p key={item.id}>Reviewer suggestion: {item.reasoning}</p>)}
              {(selected.decisions || []).map((item) => <p key={item.id}>Final decision: {item.decision.replaceAll('_', ' ').toLowerCase()} — {item.rationale}</p>)}
              {(selected.status_history || []).map((item) => <p key={item.id}>{item.timestamp?.slice(0, 19)} · {item.from_status.replaceAll('_', ' ')} → {item.to_status.replaceAll('_', ' ')}</p>)}
            </details>
          </section>
        ) : <div className="glass-panel" style={panelStyle}>Choose a claim to see its details.</div>}
      </div>
    </div>
  );
};

export default ClaimsPage;
