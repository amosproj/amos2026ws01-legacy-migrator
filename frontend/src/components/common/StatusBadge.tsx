import React from 'react';
import { ComponentMigrationStatus } from '../../types/chat';

interface StatusBadgeProps {
  status: ComponentMigrationStatus;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const configs: Record<ComponentMigrationStatus, { label: string; bg: string; text: string; border: string; dot: string }> = {
    legacy: {
      label: 'Legacy Active',
      bg: 'bg-[#f5f5f5]',
      text: 'text-[#4d4d4d]',
      border: 'border-[#e5e5e5]',
      dot: 'bg-[#737373]'
    },
    migrated: {
      label: 'Migrated to Target',
      bg: 'bg-[#ecfdf5]',
      text: 'text-[#065f46]',
      border: 'border-[#a7f3d0]',
      dot: 'bg-[#059669]'
    },
    coupled: {
      label: 'Coupled Dependency',
      bg: 'bg-[#fffbeb]',
      text: 'text-[#92400e]',
      border: 'border-[#fde68a]',
      dot: 'bg-[#d97706]'
    },
    decommissioned: {
      label: 'Decommissioned',
      bg: 'bg-[#fef2f2]',
      text: 'text-[#991b1b]',
      border: 'border-[#fecaca]',
      dot: 'bg-[#dc2626]'
    },
    target_in_progress: {
      label: 'Target In Progress',
      bg: 'bg-[#eff6ff]',
      text: 'text-[#1e40af]',
      border: 'border-[#bfdbfe]',
      dot: 'bg-[#2563eb]'
    }
  };

  const config = configs[status] || configs.legacy;
  const padding = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-0.5 text-[11px]';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-full border ${config.bg} ${config.text} ${config.border} ${padding} uppercase tracking-wider select-none`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`}></span>
      {config.label}
    </span>
  );
};
