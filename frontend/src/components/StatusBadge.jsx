import React from 'react';
import { CheckCircle2, Clock, AlertTriangle, XCircle, Search, HelpCircle } from 'lucide-react';

const StatusBadge = ({ status }) => {
  const norm = (status || '').toLowerCase();
  const labels = {
    'awaiting evidence': 'Waiting for information',
    'under review': 'Being reviewed',
    'additional evidence required': 'More information needed',
    verified: 'Confirmed by reviewer',
    'submitted': 'Claim submitted',
    'under evaluation': 'Being reviewed',
    'information requested': 'More information requested',
    'provisional calculation ready': 'Early estimate prepared',
    'recommendation recorded': 'Reviewer recommendation saved',
    'decision recorded': 'Decision recorded',
  };
  const label = labels[norm] || status || 'Unknown';

  if (norm.includes('verified') || norm.includes('approved') || norm.includes('completed')) {
    return (
      <span className="badge badge-green">
        <CheckCircle2 size={12} />
        {label}
      </span>
    );
  }

  if (norm.includes('review') || norm.includes('under review')) {
    return (
      <span className="badge badge-amber">
        <Clock size={12} />
        {label}
      </span>
    );
  }

  if (norm.includes('awaiting') || norm.includes('evidence')) {
    return (
      <span className="badge badge-cyan">
        <Search size={12} />
        {label}
      </span>
    );
  }

  if (norm.includes('not confirmed') || norm.includes('rejected') || norm.includes('high')) {
    return (
      <span className="badge badge-red">
        <XCircle size={12} />
        {label}
      </span>
    );
  }

  if (norm.includes('new')) {
    return (
      <span className="badge badge-cyan">
        <AlertTriangle size={12} />
        {label}
      </span>
    );
  }

  return (
    <span className="badge badge-gray">
      <HelpCircle size={12} />
      {label}
    </span>
  );
};

export default StatusBadge;
