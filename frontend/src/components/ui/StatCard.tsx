import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  icon: React.ReactNode;
  iconColor?: string;
  subtitle?: string;
}

const changeConfig = {
  positive: {
    textColor: 'text-emerald-400',
    Icon: TrendingUp,
  },
  negative: {
    textColor: 'text-red-400',
    Icon: TrendingDown,
  },
  neutral: {
    textColor: 'text-zinc-400',
    Icon: Minus,
  },
};

export default function StatCard({
  title,
  value,
  change,
  changeType = 'neutral',
  icon,
  iconColor = 'bg-indigo-500/10 text-indigo-400',
  subtitle,
}: StatCardProps) {
  const { textColor, Icon: ChangeIcon } = changeConfig[changeType];

  return (
    <div className="bg-zinc-900 dark:bg-zinc-900 border border-zinc-800 dark:border-zinc-800 rounded-xl p-5 shadow-sm shadow-black/20">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-zinc-400 text-sm font-medium truncate">{title}</p>
          <p className="text-zinc-100 dark:text-zinc-100 text-2xl font-bold mt-1 leading-tight">
            {value}
          </p>
          {subtitle && (
            <p className="text-zinc-500 text-xs mt-1 truncate">{subtitle}</p>
          )}
          {change && (
            <div className={`flex items-center gap-1 mt-2 ${textColor}`}>
              <ChangeIcon size={13} />
              <span className="text-xs font-medium">{change}</span>
            </div>
          )}
        </div>
        <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${iconColor}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
