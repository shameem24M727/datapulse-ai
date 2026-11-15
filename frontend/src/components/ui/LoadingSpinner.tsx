interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeMap = {
  sm: 'w-4 h-4 border-2',
  md: 'w-7 h-7 border-2',
  lg: 'w-10 h-10 border-[3px]',
};

export default function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
  return (
    <div
      className={`rounded-full border-zinc-700 border-t-indigo-500 animate-spin ${sizeMap[size]} ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}
