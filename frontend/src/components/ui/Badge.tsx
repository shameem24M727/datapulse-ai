import React from 'react';

type BadgeVariant =
  | 'healthy'
  | 'warning'
  | 'critical'
  | 'processing'
  | 'info'
  | 'low'
  | 'medium'
  | 'high'
  | 'success'
  | 'failed'
  | 'running'
  | 'paused'
  | 'open'
  | 'investigating'
  | 'resolved';

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  size?: 'sm' | 'md';
}

const variantMap: Record<BadgeVariant, string> = {
  healthy:      'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  success:      'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  low:          'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  resolved:     'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  warning:      'bg-amber-500/10 text-amber-400 border-amber-500/20',
  medium:       'bg-amber-500/10 text-amber-400 border-amber-500/20',
  investigating:'bg-amber-500/10 text-amber-400 border-amber-500/20',
  critical:     'bg-red-500/10 text-red-400 border-red-500/20',
  failed:       'bg-red-500/10 text-red-400 border-red-500/20',
  high:         'bg-red-500/10 text-red-400 border-red-500/20',
  processing:   'bg-blue-500/10 text-blue-400 border-blue-500/20',
  running:      'bg-blue-500/10 text-blue-400 border-blue-500/20',
  info:         'bg-blue-500/10 text-blue-400 border-blue-500/20',
  paused:       'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  open:         'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
};

const sizeMap = {
  sm: 'text-xs px-2 py-0.5',
  md: 'text-xs px-2.5 py-1',
};

export default function Badge({ variant, children, size = 'sm' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center font-medium border rounded-full ${variantMap[variant]} ${sizeMap[size]}`}
    >
      {children}
    </span>
  );
}
