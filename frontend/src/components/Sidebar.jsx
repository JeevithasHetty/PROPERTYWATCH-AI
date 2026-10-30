import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Building2,
  PlusCircle,
  Satellite,
  Layers,
  BellRing,
  FileCheck2,
  History,
  FileText,
  FilePlus2,
  Sliders,
  Eye
} from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/properties', label: 'Properties', icon: Building2 },
    { to: '/properties/new', label: 'Add a property', icon: PlusCircle },
    { to: '/satellite', label: 'Property photos', icon: Satellite },
    { to: '/analysis', label: 'Compare photos', icon: Layers },
    { to: '/modifications', label: 'Possible changes', icon: BellRing },
    { to: '/claims', label: 'Insurance claims', icon: FilePlus2 },
    { to: '/reviews', label: 'Review cases', icon: FileCheck2 },
    { to: '/history', label: 'Activity history', icon: History },
    { to: '/reports', label: 'Reports', icon: FileText },
    { to: '/settings', label: 'Settings', icon: Sliders },
  ];

  return (
    <aside
      className="glass-panel app-sidebar"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        bottom: 0,
        width: '260px',
        borderRadius: 0,
        borderTop: 'none',
        borderBottom: 'none',
        borderLeft: 'none',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 40,
        background: '#090e1a',
      }}
    >
      {/* Brand Header */}
      <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--border-glass)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #35c77b 0%, #16824e 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 15px rgba(34, 168, 102, 0.4)',
              color: '#fff',
            }}
          >
            <Eye size={22} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.05rem', letterSpacing: '-0.02em', color: '#fff' }}>
              PropertyWatch<span style={{ color: 'var(--accent-cyan-light)' }}>AI</span>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Property and claim support
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }}>
        <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', padding: '6px 12px', letterSpacing: '0.06em' }}>
          Workspace
        </div>
        <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  style={({ isActive }) => ({
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    fontSize: '0.88rem',
                    fontWeight: isActive ? 600 : 500,
                    textDecoration: 'none',
                    color: isActive ? 'var(--accent-cyan-light)' : 'var(--text-muted)',
                    background: isActive ? 'rgba(52, 211, 153, 0.12)' : 'transparent',
                    border: isActive ? '1px solid rgba(110, 231, 168, 0.25)' : '1px solid transparent',
                    transition: 'all 0.15s ease',
                  })}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer System Boundaries Notice */}
      <div style={{ padding: '16px', borderTop: '1px solid var(--border-glass)', background: 'rgba(15, 23, 42, 0.4)' }}>
        <div className="sidebar-note">
          <b>People make the decisions.</b> This app helps organize property records and claim information. It does not decide claims automatically.
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
