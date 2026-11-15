import React from 'react';

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-14 h-14 rounded-2xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-500 dark:text-zinc-400 mb-4 border border-zinc-200 dark:border-zinc-700/60">
        {icon}
      </div>
      <h3 className="text-zinc-900 dark:text-zinc-100 font-semibold text-base mb-2">{title}</h3>
      <p className="text-zinc-500 dark:text-zinc-400 text-sm max-w-sm leading-relaxed">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
