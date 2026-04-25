import Link from "next/link";
import { Loader2, Trash2 } from "lucide-react";

import type { InterviewHistoryItem } from "@/types";

interface SessionCardProps {
  session: InterviewHistoryItem;
  onDelete: (sessionId: string) => Promise<void>;
  isDeleting: boolean;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleString();
}

function scoreText(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return `${value.toFixed(1)} / 10`;
}

export function SessionCard({ session, onDelete, isDeleting }: SessionCardProps): JSX.Element {
  const isCoding = session.session_type === "coding";
  const isComplete = session.is_complete;

  const destination = isCoding
    ? isComplete
      ? `/coding/${session.session_id}/results`
      : `/coding/${session.session_id}`
    : isComplete
      ? `/interview/${session.session_id}/results`
      : `/interview/${session.session_id}`;

  const typeBadgeClass = isCoding
    ? "border border-border bg-surface-hover text-foreground"
    : "border border-primary-subtle bg-primary-subtle text-primary";

  const statusBadgeClass = isComplete
    ? "border border-success bg-success-subtle text-success"
    : "border border-warning bg-warning-subtle text-warning";

  const title = isCoding
    ? session.problem_title || "Coding session"
    : session.match_summary || "Interview session";

  return (
    <article className="rounded-xl border border-border bg-surface p-4 transition-all duration-200 ease-out hover:border-border-strong hover:bg-surface-hover">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[11px] ${typeBadgeClass}`}>
              {isCoding ? "Coding" : "Interview"}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] ${statusBadgeClass}`}>
              {isComplete ? "Completed" : "In Progress"}
            </span>
          </div>
          <p className="mt-2 truncate text-sm font-semibold text-foreground">{title}</p>
          <p className="mt-1 text-xs text-foreground-muted">{formatDate(session.created_at)}</p>
          <p className="mt-1 text-xs text-foreground-muted">Score: {scoreText(session.overall_score)}</p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href={destination}
            className="app-btn-secondary h-8 px-3 text-xs"
          >
            {isComplete ? "View Results" : "Resume"}
          </Link>
          <button
            type="button"
            onClick={() => {
              void onDelete(session.session_id);
            }}
            disabled={isDeleting}
            className="inline-flex h-8 items-center justify-center gap-1 rounded-lg border border-danger px-3 text-xs font-medium text-danger transition-colors duration-150 hover:bg-danger-subtle disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isDeleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            {isDeleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </article>
  );
}
