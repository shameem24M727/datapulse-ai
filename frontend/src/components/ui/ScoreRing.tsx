interface ScoreRingProps {
  score: number; // 0-100
  size?: number;
  strokeWidth?: number;
  color?: string;
  label?: string;
}

export default function ScoreRing({
  score,
  size = 80,
  strokeWidth = 8,
  color,
  label,
}: ScoreRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const center = size / 2;

  // Auto-color based on score if not provided
  const arcColor = color
    ? color
    : score >= 80
    ? '#10b981' // emerald
    : score >= 60
    ? '#f59e0b' // amber
    : '#ef4444'; // red

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          {/* Background track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-zinc-200 dark:text-zinc-800"
          />
          {/* Score arc */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={arcColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-zinc-900 dark:text-zinc-100 font-bold" style={{ fontSize: size * 0.22 }}>
            {score}
          </span>
        </div>
      </div>
      {label && (
        <span className="text-zinc-400 text-xs font-medium">{label}</span>
      )}
    </div>
  );
}
