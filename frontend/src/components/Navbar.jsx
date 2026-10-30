import React from 'react';
import { useAuth } from '../context/AuthContext';
import { LogOut, User as UserIcon, Shield, Activity } from 'lucide-react';
import { Link } from 'react-router-dom';

const Navbar = () => {
  const { user, logout } = useAuth();

  const getRoleBadge = (role) => {
    switch (role) {
      case 'admin':
        return <span className="badge badge-cyan"><Shield size={12} /> Administrator</span>;
      case 'reviewer':
        return <span className="badge badge-green"><Activity size={12} /> Reviewer</span>;
      case 'owner':
        return <span className="badge badge-amber"><UserIcon size={12} /> Property owner</span>;
      case 'decision_maker':
        return <span className="badge badge-cyan"><Shield size={12} /> Decision maker</span>;
      default:
        return <span className="badge badge-amber"><UserIcon size={12} /> Property manager</span>;
    }
  };

  return (
    <header className="app-topbar">
      <div className="topbar-context">
        <span className="topbar-dot" />
        <span>Property and claim workspace</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        {user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)' }}>{user.name}</div>
              <div style={{ marginTop: '2px' }}>{getRoleBadge(user.role)}</div>
            </div>

            <button
              onClick={logout}
              className="btn btn-secondary btn-sm"
              title="Logout"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <LogOut size={14} />
              <span>Sign Out</span>
            </button>
          </div>
        ) : (
          <Link to="/login" className="btn btn-primary btn-sm">
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
};

export default Navbar;
