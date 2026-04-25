interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps): JSX.Element {
  return <div className={`animate-pulse rounded-lg bg-surface-hover ${className}`.trim()} />;
}
