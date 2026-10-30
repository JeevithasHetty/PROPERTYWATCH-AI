import React from 'react';
import { Calendar, User, Shield, CheckCircle2, AlertTriangle, Eye, ArrowRight } from 'lucide-react';

const AuditTimeline = ({ events = [] }) => {
  if (!events || events.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '36px', color: 'var(--text-dim)' }}>
        No chronological history records logged yet.
      </div>
    );
  }

  const getEventIcon = (type) => {
    switch (type) {
      case 'REGISTRATION':
        return <Shield size={16} color="#6ee7a8" />;
      case 'SNAPSHOT':
        return <Eye size={16} color="#2dd4bf" />;
      case 'ALERT':
        return <AlertTriangle size={16} color="#f59e0b" />;
      case 'VERIFICATION':
        return <CheckCircle2 size={16} color="#34d399" />;
      default:
        return <Calendar size={16} color="#94a3b8" />;
    }
  };

  return (
    <div style={{ position: 'relative', paddingLeft: '24px', display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Vertical Spine Line */}
      <div
        style={{
          position: 'absolute',
          top: '12px',
          bottom: '12px',
          left: '11px',
          width: '2px',
          background: 'rgba(51, 65, 85, 0.4)',
        }}
      />

      {events.map((ev, idx) => (
        <div key={idx} style={{ position: 'relative', display: 'flex', gap: '16px' }}>
          {/* Node Dot */}
          <div
            style={{
              position: 'absolute',
              left: '-24px',
              top: '4px',
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              background: '#0f172a',
              border: '2px solid #6ee7a8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 10px rgba(110, 231, 168, 0.4)',
            }}
          >
            {getEventIcon(ev.event_type)}
          </div>

          {/* Event Content Box */}
          <div
            className="glass-panel"
            style={{
              flex: 1,
              padding: '16px 20px',
              background: 'rgba(15, 23, 42, 0.55)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginBottom: '6px' }}>
              <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                {ev.title}
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Calendar size={13} />
                <span>{new Date(ev.timestamp).toLocaleString()}</span>
              </div>
            </div>

            <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginBottom: '8px', lineHeight: 1.45 }}>
              {ev.description}
            </p>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <User size={13} />
                <span>Logged by: <b style={{ color: 'var(--text-muted)' }}>{ev.actor}</b></span>
              </div>
              {ev.image_url && (
                <a
                  href={ev.image_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: '#6ee7a8', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <span>View Snapshot</span>
                  <ArrowRight size={12} />
                </a>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default AuditTimeline;
