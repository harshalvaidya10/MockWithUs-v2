"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { ApiError, apiRequest, getCodingResults, getInterviewHistory } from "@/lib/api";
import type {
  CodeSubmitResponse,
  InterviewHistoryItem,
  InterviewStartResponse,
  TestResult,
} from "@/types";

const START_RESULT_STORAGE_PREFIX = "mockwithus:interview:start:";
const START_INTERVIEW_TIMEOUT_MS = 75_000;

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

function scoreColorClass(score: number): string {
  if (score >= 8) return "text-success";
  if (score >= 6) return "text-warning";
  return "text-danger";
}

function scoreBarClass(score: number): string {
  if (score >= 8) return "bg-success";
  if (score >= 6) return "bg-warning";
  return "bg-danger";
}

function statusBadgeClass(status: string): string {
  if (status === "accepted") return "border border-success bg-success-subtle text-success";
  if (status === "time_limit") return "border border-warning bg-warning-subtle text-warning";
  return "border border-danger bg-danger-subtle text-danger";
}

function formatStatus(status: string): string {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatMinutes(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const remainderSeconds = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${remainderSeconds}`;
}

function estimateTimeSpent(session: InterviewHistoryItem | null, fallbackSeconds: number): string {
  if (session?.created_at && session?.completed_at) {
    const created = new Date(session.created_at).getTime();
    const completed = new Date(session.completed_at).getTime();
    if (!Number.isNaN(created) && !Number.isNaN(completed) && completed > created) {
      return formatMinutes((completed - created) / 1000);
    }
  }
  return formatMinutes(fallbackSeconds);
}

function safeValue(value: string | null | undefined): string {
  if (!value || value.length === 0) return "∅";
  return value;
}

function tryParseJson(value: string): { ok: true; value: unknown } | { ok: false } {
  try {
    return { ok: true, value: JSON.parse(value) };
  } catch {
    return { ok: false };
  }
}

function formatStructuredValue(value: string | null | undefined): string {
  const rawValue = safeValue(value);
  if (rawValue === "∅") return rawValue;

  const parsed = tryParseJson(rawValue.trim());
  if (!parsed.ok) return rawValue;
  if (typeof parsed.value === "string") return parsed.value;
  return JSON.stringify(parsed.value, null, 2);
}

function sortedResults(results: TestResult[]): TestResult[] {
  const failed = results.filter((result) => !result.passed);
  const passed = results.filter((result) => result.passed);
  return [...failed, ...passed];
}

export default function CodingResultsPage(): JSX.Element {
  const router = useRouter();
  const params = useParams<{ sessionId?: string | string[] }>();
  const sessionIdParam = params?.sessionId;
  const sessionId = Array.isArray(sessionIdParam) ? sessionIdParam[0] : sessionIdParam;

  const [data, setData] = useState<CodeSubmitResponse | null>(null);
  const [sessionItem, setSessionItem] = useState<InterviewHistoryItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isStartingInterview, setIsStartingInterview] = useState(false);
  const [startInterviewError, setStartInterviewError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setErrorMessage("Invalid coding session URL.");
      setIsLoading(false);
      return;
    }

    let isCancelled = false;
    setIsLoading(true);
    setErrorMessage(null);
    setStartInterviewError(null);

    void Promise.all([getCodingResults(sessionId), getInterviewHistory()])
      .then(([resultsResponse, historyResponse]) => {
        if (isCancelled) return;
        setData(resultsResponse);
        const matchedSession =
          historyResponse.sessions.find((session) => session.session_id === sessionId) ?? null;
        setSessionItem(matchedSession);
      })
      .catch((error: unknown) => {
        if (isCancelled) return;
        setErrorMessage(getApiErrorMessage(error, "Could not load coding results."));
      })
      .finally(() => {
        if (isCancelled) return;
        setIsLoading(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [sessionId]);

  async function handleStartMockInterview(): Promise<void> {
    const resumeId = sessionItem?.resume_id;
    const jobId = sessionItem?.job_id;
    if (!resumeId || !jobId) {
      setStartInterviewError(
        "This coding session is missing resume/job context. Please start interview from Practice.",
      );
      return;
    }

    setStartInterviewError(null);
    setIsStartingInterview(true);
    const abortController = new AbortController();
    const timeoutId = window.setTimeout(() => {
      abortController.abort();
    }, START_INTERVIEW_TIMEOUT_MS);

    try {
      const response = await apiRequest<InterviewStartResponse>("/interviews/start", {
        method: "POST",
        body: JSON.stringify({
          resume_id: resumeId,
          job_id: jobId,
        }),
        signal: abortController.signal,
      });

      if (typeof window !== "undefined") {
        sessionStorage.setItem(
          `${START_RESULT_STORAGE_PREFIX}${response.session_id}`,
          JSON.stringify(response),
        );
      }

      router.push(`/interview/${response.session_id}`);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setStartInterviewError(
          "Interview generation is taking too long. Please try again in a few seconds.",
        );
        return;
      }
      setStartInterviewError(
        getApiErrorMessage(error, "Could not start mock interview. Please try again."),
      );
    } finally {
      window.clearTimeout(timeoutId);
      setIsStartingInterview(false);
    }
  }

  const evaluation = data?.evaluation ?? null;
  const orderedResults = useMemo(() => sortedResults(data?.results ?? []), [data?.results]);

  const fallbackTimeSeconds = useMemo(() => {
    if (!data) return 0;
    return data.results.reduce((total, result) => total + (result.runtime_ms ?? 0) / 1000, 0);
  }, [data]);

  if (isLoading) {
    return (
      <main className="min-h-screen bg-background px-2 py-2">
        <div className="mx-auto max-w-6xl rounded-xl border border-border bg-surface p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Coding Results</h1>
          <p className="mt-2 text-sm text-foreground-muted">Loading your coding evaluation...</p>
        </div>
      </main>
    );
  }

  if (errorMessage || !data || !evaluation || !sessionId) {
    return (
      <main className="min-h-screen bg-background px-2 py-2">
        <div className="mx-auto max-w-6xl rounded-xl border border-border bg-surface p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Coding Results</h1>
          <p className="mt-3 text-sm text-danger">{errorMessage ?? "Results are unavailable."}</p>
          <div className="mt-4">
            <Link
              href="/home"
              className="app-btn-secondary"
            >
              Back to Home
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const passRatePercent = Math.round(evaluation.pass_rate * 100);
  const timeSpent = estimateTimeSpent(sessionItem, fallbackTimeSeconds);

  return (
    <main className="min-h-screen bg-background px-2 py-2">
      <div className="mx-auto max-w-6xl space-y-6">
        <section className="rounded-xl border border-border bg-surface p-6">
          <p className="text-xs uppercase tracking-wide text-foreground-subtle">Coding round results</p>
          <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-4xl font-bold tabular-nums text-foreground">{evaluation.overall_score.toFixed(1)} / 10</p>
              <p className="mt-1 text-sm text-foreground-muted">
                {evaluation.tests_passed}/{evaluation.tests_total} test cases passed
              </p>
            </div>
            <p className="font-mono text-sm text-foreground-muted">Time spent: {timeSpent}</p>
          </div>

          <div className="mt-4 h-3 overflow-hidden rounded-full bg-surface-hover">
            <div className="h-full bg-success" style={{ width: `${passRatePercent}%` }} />
          </div>
          <p className="mt-1 text-xs text-foreground-muted">Pass rate: {passRatePercent}%</p>
        </section>

        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">Score Breakdown</h2>
          <div className="mt-4 space-y-3">
            {[
              { label: "Correctness", score: evaluation.correctness_score, weight: "40%" },
              { label: "Efficiency", score: evaluation.efficiency_score, weight: "20%" },
              { label: "Code quality", score: evaluation.code_quality_score, weight: "15%" },
              { label: "Problem solving", score: evaluation.problem_solving_score, weight: "25%" },
            ].map((item) => (
              <div key={item.label} className="rounded-xl border border-border bg-surface-hover p-3">
                <div className="flex items-center justify-between text-sm">
                  <p className="text-foreground-muted">{item.label}</p>
                  <p className={`font-semibold ${scoreColorClass(item.score)}`}>{item.score.toFixed(1)}</p>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface">
                  <div
                    className={`h-full ${scoreBarClass(item.score)}`}
                    style={{ width: `${Math.max(0, Math.min(100, item.score * 10))}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-foreground-muted">Weight: {item.weight}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">Feedback</h2>
          <p className="mt-3 rounded-xl border border-border bg-surface-hover p-4 text-sm text-foreground">
            {evaluation.feedback_text}
          </p>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-border bg-surface-hover p-4">
              <p className="text-sm font-medium text-success">Strengths</p>
              <ul className="mt-2 space-y-1 text-sm text-foreground">
                {evaluation.strengths.map((item) => (
                  <li key={item}>✓ {item}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-border bg-surface-hover p-4">
              <p className="text-sm font-medium text-warning">Improvements</p>
              <ul className="mt-2 space-y-1 text-sm text-foreground">
                {evaluation.improvements.map((item) => (
                  <li key={item}>→ {item}</li>
                ))}
              </ul>
            </div>
          </div>

          <p className="mt-4 rounded-xl border border-border bg-surface-hover p-3 font-mono text-xs text-foreground">
            {evaluation.complexity_analysis}
          </p>
        </section>

        <section className="rounded-xl border border-border bg-surface p-6">
          <details open>
            <summary className="cursor-pointer text-lg font-semibold text-foreground">
              Test case details ({evaluation.tests_passed}/{evaluation.tests_total} passed)
            </summary>
            <div className="mt-4 space-y-3">
              {orderedResults.map((result, index) => (
                <article key={`${result.test_case_id}-${index}`} className="rounded-xl border border-border bg-surface-hover p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className={`rounded-full px-2 py-1 text-xs ${statusBadgeClass(result.status)}`}>
                      {formatStatus(result.status)}
                    </span>
                    <span className="text-xs text-foreground-muted">{result.runtime_ms ?? 0} ms</span>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Expected</p>
                      <pre className="mt-1 rounded-lg bg-surface p-2 text-xs text-foreground whitespace-pre-wrap break-words">
                        {formatStructuredValue(result.expected_output)}
                      </pre>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Actual</p>
                      <pre
                        className={`mt-1 rounded-lg p-2 text-xs whitespace-pre-wrap break-words ${
                          result.passed ? "bg-surface text-foreground" : "bg-danger-subtle text-danger"
                        }`}
                      >
                        {formatStructuredValue(result.actual_output)}
                      </pre>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Error</p>
                      <pre className="mt-1 rounded-lg bg-surface p-2 text-xs text-foreground whitespace-pre-wrap break-words">
                        {formatStructuredValue(result.error_output)}
                      </pre>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </details>
        </section>

        <section className="rounded-xl border border-border bg-surface p-6">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-foreground">Show expected solution</summary>
            <pre className="mt-3 overflow-x-auto rounded-xl border border-border bg-surface-hover p-4 text-xs text-foreground">
              {evaluation.expected_solution}
            </pre>
            <p className="mt-2 text-xs text-foreground-muted">
              This is one possible solution. There may be other valid approaches.
            </p>
          </details>
        </section>

        <section className="flex flex-wrap gap-3 pb-6">
          <Link
            href={`/coding/${sessionId}`}
            className="app-btn-primary"
          >
            Try Again
          </Link>
          <button
            type="button"
            onClick={() => {
              void handleStartMockInterview();
            }}
            disabled={isStartingInterview || !sessionItem?.resume_id || !sessionItem?.job_id}
            className="app-btn-secondary"
          >
            {isStartingInterview ? "Starting interview..." : "Try Audio Interview Next"}
          </button>
          <Link
            href="/home"
            className="app-btn-ghost"
          >
            Back to Home
          </Link>
          {startInterviewError ? (
            <p className="w-full text-sm text-danger">{startInterviewError}</p>
          ) : null}
        </section>
      </div>
    </main>
  );
}
