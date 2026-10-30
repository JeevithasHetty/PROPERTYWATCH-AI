import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// Attach JWT access token to every outgoing request if present
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('pw_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Intercept 401 unauthorized and clear token
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Don't auto-redirect if already on login page
      if (!window.location.pathname.includes('/login')) {
        localStorage.removeItem('pw_token');
        localStorage.removeItem('pw_user');
      }
    }
    return Promise.reject(error);
  }
);

export const apiClient = {
  // Auth
  login: (email, password) => api.post('/auth/login', { email, password }),
  getMe: () => api.get('/auth/me'),

  // Properties
  getProperties: (params) => api.get('/properties', { params }),
  getProperty: (id) => api.get(`/properties/${id}`),
  createProperty: (data) => api.post('/properties', data),
  updateProperty: (id, data) => api.put(`/properties/${id}`, data),
  getPropertyHistory: (id) => api.get(`/properties/${id}/history`),
  uploadBaselinePhoto: (id, formData) =>
    api.post(`/properties/${id}/baseline-photo`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  // Insurance policies
  linkPolicy: (data) => api.post('/policies', data),
  uploadPolicyDocument: (policyId, formData) =>
    api.post(`/policies/${policyId}/document`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  downloadPolicyDocument: (policyId) =>
    api.get(`/policies/${policyId}/document`, { responseType: 'blob' }),
  verifyPolicyTerms: (policyId, data) => api.post(`/policies/${policyId}/verify-terms`, data),

  // Geocoding
  geocode: (address) => api.post('/geocode', { address }),

  // Satellite Monitoring
  searchSatellite: (params) => api.get('/satellite/search', { params }),
  retrieveSatellite: (data) => api.post('/satellite/retrieve', data),
  getPropertySnapshots: (propId) => api.get(`/satellite/properties/${propId}/snapshots`),
  getPropertySnapshotImage: (propertyId, snapshotId) =>
    api.get(`/properties/${propertyId}/snapshots/${snapshotId}/image`, { responseType: 'blob' }),

  // Image Analysis & CV
  compareImages: (data) => api.post('/analysis/compare', data),
  getAnalysis: (id) => api.get(`/analysis/${id}`),

  // Modification Alerts
  getModifications: (params) => api.get('/modifications', { params }),
  getModification: (id) => api.get(`/modifications/${id}`),
  createModification: (data) => api.post('/modifications', data),
  updateModification: (id, data) => api.put(`/modifications/${id}`, data),

  // Evidence
  uploadEvidence: (modId, formData) =>
    api.post(`/modifications/${modId}/evidence`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  getEvidence: (modId) => api.get(`/modifications/${modId}/evidence`),
  getEvidenceDownloadUrl: (evidenceId) => `/api/evidence/${evidenceId}/download`,

  // Authenticity
  analyzeAuthenticity: (evidenceId) => api.post(`/evidence/${evidenceId}/analyze-authenticity`),
  getAuthenticityHistory: (evidenceId) => api.get(`/evidence/${evidenceId}/authenticity`),

  // Human Reviewer
  getPendingReviews: (status) => api.get('/reviews', { params: { status } }),
  submitDecision: (modId, data) => api.post(`/reviews/${modId}/decision`, data),
  getEvidenceSummary: (modId) => api.get(`/reviews/${modId}/summary`),

  // Reports
  getModificationReportUrl: (modId) => `/api/reports/modifications/${modId}`,
  getPropertyReportUrl: (propId) => `/api/reports/properties/${propId}`,

  // Insurance claims
  getClaims: (params) => api.get('/claims', { params }),
  getClaim: (id) => api.get(`/claims/${id}`),
  createClaim: (data) => api.post('/claims', data),
  uploadClaimEvidence: (id, formData) =>
    api.post(`/claims/${id}/evidence`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  recommendClaim: (id, data) => api.post(`/claims/${id}/recommendation`, data),
  decideClaim: (id, data) => api.post(`/claims/${id}/decision`, data),
  createDamageAssessment: (id, data) => api.post(`/claims/${id}/damage-assessment`, data),
  calculateProvisional: (id, data) => api.post(`/claims/${id}/provisional-calculation`, data),
  getClaimReportUrl: (id) => `/api/reports/claims/${id}`,
  downloadClaimEvidence: (claimId, evidenceId) =>
    api.get(`/claims/${claimId}/evidence/${evidenceId}/download`, { responseType: 'blob' }),
  submitOwnerDeclaration: (data) => api.post('/declarations', data),
  downloadClaimReport: (id) =>
    api.get(`/reports/claims/${id}`, { responseType: 'blob' }),

  // Settings
  getSettingsStatus: () => api.get('/settings/status'),
  toggleDemoMode: () => api.post('/settings/toggle-demo'),

  // Audit & Dashboard
  getAuditLogs: (params) => api.get('/audit-logs', { params }),
  getDashboardMetrics: () => api.get('/dashboard/metrics'),
};

export default apiClient;
