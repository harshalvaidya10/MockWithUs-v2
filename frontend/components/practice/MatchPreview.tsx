import type { MatchResult } from "@/types";
import { LongRunningLoader } from "@/components/ui/LongRunningLoader";

interface MatchPreviewProps {
  isLoading: boolean;
  matchResult: MatchResult | null;
  errorMessage: string | null;
}

function scoreText(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function MatchPreview({ isLoading, matchResult, errorMessage }: MatchPreviewProps): JSX.Element {
  if (isLoading) {
    return (
      <LongRunningLoader
        title="Analyzing match..."
        phrases={["Comparing skills...", "Identifying gaps...", "Calculating relevance..."]}
      />
    );
  }

  if (errorMessage) {
    return (
      <div className="rounded-xl border border-danger bg-danger-subtle p-4">
        <p className="text-sm text-danger">{errorMessage}</p>
      </div>
    );
  }

  if (!matchResult) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4">
        <p className="text-sm text-foreground-muted">Select both resume and JD to generate match preview.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-primary bg-primary-subtle p-4">
      <p className="text-xs uppercase tracking-wide text-primary">Match Preview</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground tabular-nums">
        {scoreText(matchResult.match_score)}
      </p>
      <p className="mt-2 text-sm text-foreground-muted">{matchResult.match_summary}</p>
    </div>
  );
}
