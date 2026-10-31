import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, Lock, Mail, AlertCircle, ArrowRight } from 'lucide-react';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      if (!err.response) {
        setError("Can't reach the sign-in service. Check that the backend is running, then try again.");
      } else if (err.response.status === 401) {
        setError("That email and password don't match. Check them or choose a demo role below to fill them in.");
      } else {
        setError(err.response.data?.detail || 'Sign-in failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fillCredentials = (userEmail, userPass) => {
    setEmail(userEmail);
    setPassword(userPass);
    setError('');
  };

  return (
    <div className="login-page">
      <div className="login-layout">
        <section className="login-visual" aria-label="PropertyWatch introduction">
          <div className="login-visual-brand">
            <span className="login-brandmark"><Eye size={26} /></span>
            <span>PropertyWatch<span className="login-visual-brand-accent">AI</span></span>
          </div>

          <div className="login-visual-copy">
            <span className="login-visual-kicker">Property &amp; claim support</span>
            <h1>A clearer view of every property.</h1>
            <p>Bring property photos, policy details, and claim information together in one place.</p>
          </div>

          <div className="login-visual-note">
            <span className="login-visual-note-dot" />
            <span>People stay in control of every review and decision.</span>
          </div>
        </section>

        <div className="login-content">
          <div className="login-form-heading">
            <h2>Welcome back</h2>
            <p>Sign in to continue to your workspace.</p>
          </div>

          <div className="glass-panel login-card">
            <h2 className="login-card-title">
              <Lock size={18} color="var(--accent-cyan-light)" />
              <span>Sign in to your account</span>
            </h2>

            {error && (
              <div className="login-error" role="alert">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="login-form">
              <div>
                <label htmlFor="login-email">Email address</label>
                <div className="login-input-wrap">
                  <Mail size={16} aria-hidden="true" />
                  <input
                    id="login-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field"
                    placeholder="name@propertywatch.ai"
                    autoComplete="username"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="login-password">Password</label>
                <div className="login-input-wrap">
                  <Lock size={16} aria-hidden="true" />
                  <input
                    id="login-password"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-field"
                    placeholder="Enter your password"
                    autoComplete="current-password"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary login-submit"
              >
                {loading ? 'Signing in...' : 'Sign in'}
                <ArrowRight size={16} />
              </button>
            </form>

            <div className="login-demo-section">
              <div className="login-demo-heading">Trying the demo?</div>
              <p className="login-demo-intro">
                Choose one role to fill in the form. You only need one account.
              </p>
              <div className="login-demo-list">
                <button
                  type="button"
                  onClick={() => fillCredentials('admin@propertywatch.ai', 'AdminPass123!')}
                  className="btn btn-secondary btn-sm login-demo-button"
                >
                  <span className="login-demo-copy">
                    <b>Administrator</b>
                    <span>Manage the workspace and properties</span>
                  </span>
                  <span className="badge badge-cyan">Admin</span>
                </button>

                <button
                  type="button"
                  onClick={() => fillCredentials('reviewer@propertywatch.ai', 'ReviewerPass123!')}
                  className="btn btn-secondary btn-sm login-demo-button"
                >
                  <span className="login-demo-copy">
                    <b>Reviewer</b>
                    <span>Review possible changes and evidence</span>
                  </span>
                  <span className="badge badge-green">Review</span>
                </button>

                <button
                  type="button"
                  onClick={() => fillCredentials('manager@propertywatch.ai', 'ManagerPass123!')}
                  className="btn btn-secondary btn-sm login-demo-button"
                >
                  <span className="login-demo-copy">
                    <b>Property manager</b>
                    <span>View properties and submit photos or documents</span>
                  </span>
                  <span className="badge badge-amber">Submit</span>
                </button>
              </div>
            </div>
          </div>

          <p className="login-disclaimer">
            Independent property monitoring and claim-assistance workspace. No Guidewire integration or automatic claim decisions.
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
