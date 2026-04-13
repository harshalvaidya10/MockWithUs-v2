"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ApiError, apiRequest } from "@/lib/api";
import type { InterviewStartResponse } from "@/types";

const START_RESULT_STORAGE_PREFIX = "mockwithus:interview:start:";

function formatCategory(category: string): string {
  return category.replace("_", " ");
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

export default function InterviewSessionPage(): JSX.Element {
  const routeParams = useParams<{ sessionId?: string | string[] }>();
  const sessionIdParam = routeParams?.sessionId;
  const sessionId = Array.isArray(sessionIdParam) ? sessionIdParam[0] : sessionIdParam;
  const [sessionData, setSessionData] = useState<InterviewStartResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId || typeof window === "undefined") {
      setIsLoading(false);
      setSessionData(null);
      setErrorMessage("Invalid interview session URL.");
      return;
    }

    let isCancelled = false;
    let hasCachedResult = false;

    const raw = sessionStorage.getItem(`${START_RESULT_STORAGE_PREFIX}${sessionId}`);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as InterviewStartResponse;
        if (parsed.session_id === sessionId) {
          hasCachedResult = true;
          setSessionData(parsed);
        }
      } catch {
        // Ignore invalid cache entries.
      }
    }

    setIsLoading(!hasCachedResult);
    setErrorMessage(null);

    async function fetchSession(): Promise<void> {
      try {
        const response = await apiRequest<InterviewStartResponse>(`/interviews/${sessionId}`);
        if (isCancelled) return;
        setSessionData(response);
        setErrorMessage(null);
        sessionStorage.setItem(`${START_RESULT_STORAGE_PREFIX}${sessionId}`, JSON.stringify(response));
      } catch (error) {
        if (isCancelled) return;
        if (!hasCachedResult) {
          setSessionData(null);
          setErrorMessage(
            getApiErrorMessage(error, "Could not load this interview session. Please try again."),
          );
        } else {
          setErrorMessage("Could not refresh interview data. Showing cached questions.");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchSession();

    return () => {
      isCancelled = true;
    };
  }, [sessionId]);

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-semibold text-white">Interview session</h1>
            <p className="mt-2 text-sm text-slate-300">
              Session ID: <span className="font-mono">{sessionId ?? "unknown"}</span>
            </p>
          </div>
          <Link
            href="/dashboard/matching"
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            Back to Matching
          </Link>
        </div>

        {errorMessage ? (
          <div className="mt-6 rounded-xl border border-amber-900 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
            {errorMessage}
          </div>
        ) : null}

        {isLoading && !sessionData ? (
          <p className="mt-6 text-sm text-slate-300">Loading interview session...</p>
        ) : null}

        {!isLoading && !sessionData ? (
          <p className="mt-6 text-sm text-slate-300">
            Interview session data is not available. Start an interview from{" "}
            <Link href="/dashboard/matching" className="underline underline-offset-2 hover:text-white">
              the matching page
            </Link>
            .
          </p>
        ) : null}

        {sessionData ? (
          <section className="mt-6 space-y-3">
            <p className="text-sm text-slate-200">
              Match score: {Math.round(sessionData.match_score * 100)}%
            </p>
            <p className="text-sm text-slate-300">{sessionData.match_summary}</p>
            <div className="space-y-3">
              {sessionData.questions
                .slice()
                .sort((a, b) => a.order_index - b.order_index)
                .map((question) => (
                  <div
                    key={question.id}
                    className="rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3"
                  >
                    <p className="text-xs uppercase tracking-wide text-slate-400">
                      Q{question.order_index} · {formatCategory(question.category)}
                    </p>
                    <p className="mt-1 text-sm text-white">{question.question_text}</p>
                    <p className="mt-2 text-xs text-slate-400">{question.rationale}</p>
                  </div>
                ))}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
