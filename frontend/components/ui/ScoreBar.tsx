function barColor(score: number): string {
  if (score >= 8) return "bg-success";
  if (score >= 6) return "bg-primary";
  if (score >= 4) return "bg-warning";
  return "bg-danger";
}

interface ScoreBarProps {
  label: string;
  score: number;
  suffix?: string;
}

export function ScoreBar({ label, score, suffix = "/ 10" }: ScoreBarProps): JSX.Element {
  const bounded = Math.max(0, Math.min(10, score));

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between text-sm">
        <p className="text-foreground-muted">{label}</p>
        <p className="font-semibold tabular-nums text-foreground">
          {bounded.toFixed(1)} {suffix}
        </p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-hover">
        <div className={`h-full ${barColor(bounded)}`} style={{ width: `${bounded * 10}%` }} />
      </div>
    </div>
  );
}
