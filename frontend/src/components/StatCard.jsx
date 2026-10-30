import React from 'react';
import { Link } from 'react-router-dom';

const StatCard = ({ title, value, icon: Icon, trend, color = 'cyan', linkTo }) => {
  const colorMap = {
    cyan: { bg: 'rgba(34, 168, 102, 0.12)', border: 'rgba(110, 231, 168, 0.25)', text: '#6ee7a8' },
    green: { bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.25)', text: '#34d399' },
    amber: { bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.25)', text: '#fbbf24' },
    red: { bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.25)', text: '#f87171' },
    purple: { bg: 'rgba(168, 85, 247, 0.12)', border: 'rgba(168, 85, 247, 0.25)', text: '#c084fc' },
  };

  const scheme = colorMap[color] || colorMap.cyan;

  const content = (
    <div
      className="glass-panel glass-panel-interactive"
      style={{
        padding: '22px 24px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        height: '100%',
        cursor: linkTo ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--text-muted)' }}>
          {title}
        </span>
        <div
          style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: scheme.bg,
            border: `1px solid ${scheme.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: scheme.text,
          }}
        >
          {Icon && <Icon size={20} />}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div style={{ fontSize: '2.1rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.03em', lineHeight: 1 }}>
          {value !== undefined ? value : 0}
        </div>
        {trend && (
          <span style={{ fontSize: '0.78rem', color: scheme.text, fontWeight: 600 }}>
            {trend}
          </span>
        )}
      </div>
    </div>
  );

  return linkTo ? (
    <Link to={linkTo} style={{ textDecoration: 'none', color: 'inherit' }}>
      {content}
    </Link>
  ) : (
    content
  );
};

export default StatCard;
