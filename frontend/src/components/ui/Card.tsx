import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const paddingMap = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-6',
};

export default function Card({ children, className = '', padding = 'md' }: CardProps) {
  return (
    <div
      className={`
        bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl
        shadow-sm text-zinc-900 dark:text-zinc-100
        ${paddingMap[padding]}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
