import React from 'react';
import { getStatusBadgeInfo } from '../labels';

export default function StatusBadge({ suggestion }) {
  const badgeInfo = getStatusBadgeInfo(suggestion);
  if (!badgeInfo) return null;

  return (
    <div 
      className={`status-badge status-badge-${badgeInfo.type}`}
      style={{
        backgroundColor: badgeInfo.bgColor,
        color: badgeInfo.textColor,
        borderColor: badgeInfo.borderColor,
      }}
    >
      {badgeInfo.label}
    </div>
  );
}
