"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { FeedbackAccordion } from "@/components/ui/FeedbackAccordion";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, apiRequest, getInterviewHistory } from "@/lib/api";
import type { InterviewHistoryItem } from "@/types";

interface EvaluationItem {
  id: string;
  answer_id: string;
  session_id: string;
  question_id: string;
  question_text: string;
  answer_text: string;
  relevance_score: number | null;
  clarity_score: number | null;
  depth_score: number | null;
  structure_score: number | null;
  overall_score: number | null;
  feedback_text: string | null;
  strengths: string[];
  improvements: string[];
  created_at: string;
}

interface SessionResultsResponse {
  session_id: string;
  overall_score: number | null;
  evaluations: EvaluationItem[];
}

function apiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${value.toFixed(1)} / 10`;
}

function average(values: Array<number | null | undefined>): number {
  const valid = values.filter((item): item is number => item !== null && item !== undefined && !Number.isNaN(item));
  if (valid.length === 0) return 0;
  return valid.reduce((sum, item) => sum + item, 0) / valid.length;
}

function durationText(session: InterviewHistoryItem | null): string {
  if (!session?.created_at || !session?.completed_at) return "N/A";
  const start = new Date(session.created_at).getTime();
  const end = new Date(session.completed_at).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return "N/A";
  const totalSeconds = Math.floor((end - start) / 1000);
  const mins = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (totalSeconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

export default function InterviewResultsPage(): JSX.Element {
  const params = useParams<{ sessionId?: string | string[] }>();
  const sessionIdParam = params?.sessionId;
  const sessionId = Array.isArray(sessionIdParam) ? sessionIdParam[0] : sessionIdParam;

  const [data, setData] = useState<SessionResultsResponse | null>(null);
  const [historyItem, setHistoryItem] = useState<InterviewHistoryItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setErrorMessage("Invalid session URL.");
      setIsLoading(false);
      return;
    }

    let isCancelled = false;

    async function loadResults(): Promise<void> {
      setIsLoading(true);
      setErrorMessage(null);
      setWarningMessage(null);

      try {
        const history = await getInterviewHistory();
        if (!isCancelled) {
          const matched = history.sessions.find((item) => item.session_id === sessionId) ?? null;
          setHistoryItem(matched);
        }
      } catch {
        // non-blocking
      }

      try {
        const savedResults = await apiRequest<SessionResultsResponse>(`/results/${sessionId}`);
        if (isCancelled) return;
        setData(savedResults);
        return;
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 400) {
          if (isCancelled) return;
          setErrorMessage(apiError(error, "Could not load interview results."));
          return;
        }
      }

      let evaluateFailureMessage: string | null = null;
      try {
        const evaluatedResults = await apiRequest<SessionResultsResponse>(`/evaluate/${sessionId}`, {
          method: "POST",
        });
        if (isCancelled) return;
        setData(evaluatedResults);
      } catch (error) {
        evaluateFailureMessage = apiError(
          error,
          "Could not run evaluation right now. Attempting to load saved results.",
        );
      }

      if (evaluateFailureMessage) {
        try {
          const savedResults = await apiRequest<SessionResultsResponse>(`/results/${sessionId}`);
          if (isCancelled) return;
          setData(savedResults);
          setWarningMessage(evaluateFailureMessage);
        } catch {
          if (isCancelled) return;
          setErrorMessage(evaluateFailureMessage);
        }
      }
    }

    void loadResults().finally(() => {
      if (!isCancelled) {
        setIsLoading(false);
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [sessionId]);

  const breakdown = useMemo(() => {
    if (!data) {
      return { relevance: 0, clarity: 0, depth: 0, structure: 0 };
    }

    return {
      relevance: average(data.evaluations.map((item) => item.relevance_score)),
      clarity: average(data.evaluations.map((item) => item.clarity_score)),
      depth: average(data.evaluations.map((item) => item.depth_score)),
      structure: average(data.evaluations.map((item) => item.structure_score)),
    };
  }, [data]);

  const practiceAgainHref = useMemo(() => {
    const resume = historyItem?.resume_id;
    const job = historyItem?.job_id;
    if (resume && job) {
      return `/practice?resume=${encodeURIComponent(resume)}&job=${encodeURIComponent(job)}`;
    }
    return "/practice";
  }, [historyItem]);

  const tryCodingHref = useMemo(() => {
    const resume = historyItem?.resume_id;
    const job = historyItem?.job_id;
    if (resume && job) {
      return `/practice?resume=${encodeURIComponent(resume)}&job=${encodeURIComponent(job)}&mode=coding`;
    }
    return "/practice?mode=coding";
  }, [historyItem]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-4">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="rounded-xl border border-border bg-surface p-6">
        <p className="text-xs uppercase tracking-wide text-foreground-subtle">Interview Results</p>
        <h2 className="mt-2 text-4xl font-semibold tracking-tight text-foreground">{formatScore(data?.overall_score)}</h2>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-border bg-surface-hover p-3">
            <p className="text-xs text-foreground-subtle">Match score</p>
            <p className="mt-1 text-sm font-semibold text-foreground tabular-nums">
              {historyItem?.match_score !== null && historyItem?.match_score !== undefined
                ? `${Math.round(historyItem.match_score * 100)}%`
                : "N/A"}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-surface-hover p-3">
            <p className="text-xs text-foreground-subtle">Session type</p>
            <p className="mt-1 text-sm font-semibold text-foreground">Interview</p>
          </div>
          <div className="rounded-xl border border-border bg-surface-hover p-3">
            <p className="text-xs text-foreground-subtle">Date</p>
            <p className="mt-1 text-sm font-semibold text-foreground">
              {historyItem?.created_at ? new Date(historyItem.created_at).toLocaleString() : "N/A"}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-surface-hover p-3">
            <p className="text-xs text-foreground-subtle">Duration</p>
            <p className="mt-1 text-sm font-semibold text-foreground">{durationText(historyItem)}</p>
          </div>
        </div>

        {errorMessage ? <p className="mt-4 text-sm text-danger">{errorMessage}</p> : null}
        {warningMessage ? <p className="mt-4 text-sm text-warning">{warningMessage}</p> : null}
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <ScoreBar label="Relevance" score={breakdown.relevance} />
        <ScoreBar label="Clarity" score={breakdown.clarity} />
        <ScoreBar label="Depth" score={breakdown.depth} />
        <ScoreBar label="Structure" score={breakdown.structure} />
      </section>

      {data?.evaluations?.length ? (
        <section className="space-y-3">
          {data.evaluations.map((item, index) => (
            <FeedbackAccordion
              key={item.id}
              title={`Question ${index + 1}`}
              subtitle={item.question_text}
            >
              <div className="space-y-3 text-sm text-foreground">
                <div className="rounded-lg border border-border bg-surface-hover p-3">
                  <p className="text-xs uppercase tracking-wide text-foreground-subtle">Answer transcript</p>
                  <p className="mt-2 text-sm text-foreground">{item.answer_text || "No transcript available."}</p>
                </div>

                <div className="rounded-lg border border-border bg-surface-hover p-3">
                  <p className="text-xs uppercase tracking-wide text-foreground-subtle">Audio</p>
                  <p className="mt-2 text-xs text-foreground-muted">Audio playback unavailable in current results payload.</p>
                </div>

                <div className="grid gap-2 md:grid-cols-2">
                  <p className="text-xs text-foreground-muted">Relevance: {formatScore(item.relevance_score)}</p>
                  <p className="text-xs text-foreground-muted">Clarity: {formatScore(item.clarity_score)}</p>
                  <p className="text-xs text-foreground-muted">Depth: {formatScore(item.depth_score)}</p>
                  <p className="text-xs text-foreground-muted">Structure: {formatScore(item.structure_score)}</p>
                </div>

                <div>
                  <p className="text-xs uppercase tracking-wide text-foreground-subtle">Feedback</p>
                  <p className="mt-1 text-sm text-foreground">
                    {item.feedback_text || "No feedback available for this answer."}
                  </p>
                </div>

                {item.strengths.length > 0 ? (
                  <div>
                    <p className="text-xs uppercase tracking-wide text-success">Strengths</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-foreground">
                      {item.strengths.map((strength) => (
                        <li key={strength}>{strength}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {item.improvements.length > 0 ? (
                  <div>
                    <p className="text-xs uppercase tracking-wide text-warning">Improvements</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-foreground">
                      {item.improvements.map((improvement) => (
                        <li key={improvement}>{improvement}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </FeedbackAccordion>
          ))}
        </section>
      ) : null}

      <section className="flex flex-wrap gap-3 pb-4">
        <Link
          href={practiceAgainHref}
          className="app-btn-primary"
        >
          Practice Again
        </Link>
        <Link
          href={tryCodingHref}
          className="app-btn-secondary"
        >
          Try Coding Mock
        </Link>
        <Link
          href="/home"
          className="app-btn-ghost"
        >
          Back to Home
        </Link>
      </section>
    </div>
  );
}
