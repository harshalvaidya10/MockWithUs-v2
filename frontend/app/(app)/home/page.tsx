"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Lightbulb, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { SessionCard } from "@/components/dashboard/SessionCard";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatCard } from "@/components/ui/StatCard";
import { ApiError, deleteInterviewSession, getInterviewHistory } from "@/lib/api";
import type { InterviewHistoryItem } from "@/types";

function apiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}

function averageScore(sessions: InterviewHistoryItem[]): number | null {
  const scored = sessions
    .map((item) => item.overall_score)
    .filter((value): value is number => value !== null && value !== undefined && !Number.isNaN(value));
  if (scored.length === 0) return null;
  return scored.reduce((sum, value) => sum + value, 0) / scored.length;
}

function bestCategory(sessions: InterviewHistoryItem[]): string {
  const scored = sessions.filter(
    (session) => session.overall_score !== null && session.overall_score !== undefined,
  );
  if (scored.length === 0) return "N/A";

  const coding = scored.filter((item) => item.session_type === "coding");
  const interview = scored.filter((item) => item.session_type === "interview");

  const codingAvg = averageScore(coding) ?? -1;
  const interviewAvg = averageScore(interview) ?? -1;

  if (codingAvg === -1 && interviewAvg === -1) return "N/A";
  if (codingAvg >= interviewAvg) return "Coding";
  return "Interview";
}

function sessionsThisWeek(sessions: InterviewHistoryItem[]): number {
  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  return sessions.filter((session) => {
    const createdAt = new Date(session.created_at).getTime();
    return !Number.isNaN(createdAt) && createdAt >= weekAgo;
  }).length;
}

export default function HomePage(): JSX.Element {
  const [sessions, setSessions] = useState<InterviewHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showAllSessions, setShowAllSessions] = useState(false);
  const [deletingMap, setDeletingMap] = useState<Record<string, boolean>>({});
  const [pendingDeleteSessionId, setPendingDeleteSessionId] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    void getInterviewHistory()
      .then((response) => {
        if (isCancelled) return;
        const ordered = response.sessions
          .slice()
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setSessions(ordered);
      })
      .catch((error: unknown) => {
        if (isCancelled) return;
        setErrorMessage(apiError(error, "Could not load session history."));
      })
      .finally(() => {
        if (isCancelled) return;
        setIsLoading(false);
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  const inProgressSession = useMemo(
    () => sessions.find((item) => !item.is_complete) ?? null,
    [sessions],
  );

  const recentSessions = useMemo(
    () => (showAllSessions ? sessions : sessions.slice(0, 5)),
    [sessions, showAllSessions],
  );

  const completedSessions = useMemo(
    () => sessions.filter((item) => item.is_complete),
    [sessions],
  );

  const avgScore = useMemo(() => averageScore(completedSessions), [completedSessions]);

  const recommendation = useMemo(() => {
    if (completedSessions.length === 0) return null;
    const latest = completedSessions[0];

    if (latest.session_type === "coding") {
      return {
        text: "Practice behavioral communication next to balance your interview prep.",
        href: "/practice?focus=behavioral",
      };
    }
    return {
      text: "Try a coding mock next to sharpen problem-solving under time pressure.",
      href: "/practice?mode=coding",
    };
  }, [completedSessions]);

  async function handleDeleteSession(sessionId: string): Promise<void> {
    setPendingDeleteSessionId(sessionId);
  }

  async function confirmDeleteSession(): Promise<void> {
    const sessionId = pendingDeleteSessionId;
    if (!sessionId) return;

    const previousSessions = sessions;
    setDeletingMap((currentValue) => ({ ...currentValue, [sessionId]: true }));
    setPendingDeleteSessionId(null);
    setSessions((currentValue) => currentValue.filter((item) => item.session_id !== sessionId));

    const toastId = toast.loading("Deleting session...");
    try {
      await deleteInterviewSession(sessionId);
      toast.success("Session deleted.", { id: toastId });
    } catch (error) {
      setSessions(previousSessions);
      toast.error(apiError(error, "Could not delete this session."), { id: toastId });
    } finally {
      setDeletingMap((currentValue) => ({ ...currentValue, [sessionId]: false }));
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="app-card">
        <p className="text-xs uppercase tracking-wide text-foreground-subtle">Welcome back</p>
        <h2 className="mt-2 text-4xl font-semibold tracking-tight text-foreground">Practice your next interview</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground-muted">
          Move from setup to practice quickly. Start a new session or continue where you left off.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link
            href="/practice"
            className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground transition-colors duration-150 hover:bg-primary-hover"
          >
            Start Practice
          </Link>
          {inProgressSession ? (
            <Link
              href={
                inProgressSession.session_type === "coding"
                  ? `/coding/${inProgressSession.session_id}`
                  : `/interview/${inProgressSession.session_id}`
              }
              className="app-btn-secondary h-10 px-6"
            >
              Resume session
            </Link>
          ) : null}
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total sessions" value={String(sessions.length)} />
        <StatCard
          label="Avg overall score"
          value={avgScore === null ? "N/A" : `${avgScore.toFixed(1)} / 10`}
        />
        <StatCard label="Best category" value={bestCategory(completedSessions)} />
        <StatCard label="Sessions this week" value={String(sessionsThisWeek(sessions))} />
      </section>

      {recommendation ? (
        <section className="rounded-xl border border-primary bg-primary-subtle p-6">
          <div className="flex items-start gap-3">
            <Lightbulb className="mt-0.5 h-5 w-5 text-primary" />
            <div>
              <p className="text-sm font-semibold text-primary">Recommended next step</p>
              <p className="mt-2 text-sm text-foreground-muted">{recommendation.text}</p>
            </div>
          </div>
          <Link
            href={recommendation.href}
            className="app-btn-secondary mt-4"
          >
            Continue
          </Link>
        </section>
      ) : null}

      <section className="app-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold tracking-tight text-foreground">Recent sessions</h3>
            <p className="mt-1 text-sm text-foreground-muted">Your latest interview and coding attempts.</p>
          </div>
          {sessions.length > 5 ? (
            <button
              type="button"
              onClick={() => setShowAllSessions((value) => !value)}
              className="app-btn-secondary"
            >
              {showAllSessions ? "Show fewer" : "View all sessions"}
            </button>
          ) : null}
        </div>

        {isLoading ? (
          <div className="mt-4 space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : null}

        {errorMessage ? <p className="mt-4 text-sm text-danger">{errorMessage}</p> : null}

        {!isLoading && !errorMessage && recentSessions.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="No sessions yet"
              description="Start your first practice session to see your history and score trends here."
              ctaLabel="Start Practice"
              ctaHref="/practice"
            />
          </div>
        ) : null}

        {!isLoading && !errorMessage && recentSessions.length > 0 ? (
          <div className="mt-4 space-y-3">
            {recentSessions.map((session) => (
              <SessionCard
                key={session.session_id}
                session={session}
                onDelete={handleDeleteSession}
                isDeleting={Boolean(deletingMap[session.session_id])}
              />
            ))}
          </div>
        ) : null}
      </section>

      <ConfirmDialog
        open={Boolean(pendingDeleteSessionId)}
        title="Delete this session?"
        description="This will permanently remove answers and feedback for this session. This action cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onCancel={() => setPendingDeleteSessionId(null)}
        onConfirm={() => {
          void confirmDeleteSession();
        }}
        icon={deletingMap[pendingDeleteSessionId ?? ""] ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
        isConfirming={Boolean(pendingDeleteSessionId && deletingMap[pendingDeleteSessionId])}
      />
    </div>
  );
}
