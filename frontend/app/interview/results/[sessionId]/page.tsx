"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ApiError, apiRequest } from "@/lib/api";

interface ResultsPageProps {
  params: {
    sessionId: string;
  };
}

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

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

function formatScore(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "N/A";
  }
  return `${value.toFixed(1)} / 10`;
}

export default function ResultsPage({ params }: ResultsPageProps): JSX.Element {
  const [data, setData] = useState<SessionResultsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function loadResults(): Promise<void> {
      setIsLoading(true);
      setErrorMessage(null);
      setWarningMessage(null);

      try {
        const savedResults = await apiRequest<SessionResultsResponse>(`/results/${params.sessionId}`);
        if (isCancelled) return;
        setData(savedResults);
        return;
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 400) {
          if (isCancelled) return;
          setErrorMessage(getApiErrorMessage(error, "Could not load interview results."));
          return;
        }
      }

      let evaluateFailureMessage: string | null = null;
      try {
        const evaluatedResults = await apiRequest<SessionResultsResponse>(`/evaluate/${params.sessionId}`, {
          method: "POST",
        });
        if (isCancelled) return;
        setData(evaluatedResults);
      } catch (error) {
        evaluateFailureMessage = getApiErrorMessage(
          error,
          "Could not run evaluation right now. Attempting to load saved results.",
        );
      }

      if (evaluateFailureMessage) {
        try {
          const savedResults = await apiRequest<SessionResultsResponse>(`/results/${params.sessionId}`);
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
  }, [params.sessionId]);

  const evaluationCount = useMemo(() => data?.evaluations.length ?? 0, [data]);

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
          <h1 className="text-3xl font-semibold text-white">Interview Results</h1>
          <p className="mt-2 text-sm text-slate-300">
            Session <span className="font-mono">{params.sessionId}</span>
          </p>

          {isLoading ? (
            <p className="mt-4 text-sm text-slate-300">Evaluating answers and loading results...</p>
          ) : null}

          {errorMessage ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {errorMessage}
            </div>
          ) : null}

          {warningMessage ? (
            <div className="mt-4 rounded-xl border border-amber-900 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
              {warningMessage}
            </div>
          ) : null}

          {!isLoading && data ? (
            <div className="mt-5 rounded-xl border border-emerald-800 bg-emerald-950/25 px-5 py-4">
              <p className="text-sm text-emerald-200">Overall Session Score</p>
              <p className="mt-1 text-3xl font-semibold text-white">{formatScore(data.overall_score)}</p>
              <p className="mt-1 text-xs text-emerald-100">{evaluationCount} evaluated answers</p>
            </div>
          ) : null}

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
            >
              Back to Dashboard
            </Link>
            <Link
              href={`/interview/${params.sessionId}`}
              className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              Review Questions
            </Link>
          </div>
        </section>

        {!isLoading && data?.evaluations.length ? (
          <section className="space-y-4">
            {data.evaluations.map((item, index) => (
              <article
                key={item.id}
                className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl"
              >
                <p className="text-xs text-slate-400">Question {index + 1}</p>
                <p className="mt-2 text-base font-medium text-white">{item.question_text}</p>

                <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <p className="text-xs text-slate-400">Transcribed answer</p>
                  <p className="mt-2 text-sm text-slate-200">{item.answer_text || "No answer text available."}</p>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-400">Relevance</p>
                    <p className="mt-1 text-sm text-white">{formatScore(item.relevance_score)}</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-400">Clarity</p>
                    <p className="mt-1 text-sm text-white">{formatScore(item.clarity_score)}</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-400">Depth</p>
                    <p className="mt-1 text-sm text-white">{formatScore(item.depth_score)}</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-400">Structure</p>
                    <p className="mt-1 text-sm text-white">{formatScore(item.structure_score)}</p>
                  </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <p className="text-xs text-slate-400">Feedback</p>
                  <p className="mt-2 text-sm text-slate-200">
                    {item.feedback_text || "No feedback available for this answer."}
                  </p>

                  {item.strengths.length > 0 ? (
                    <div className="mt-3">
                      <p className="text-xs text-emerald-300">Strengths</p>
                      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-200">
                        {item.strengths.map((strength) => (
                          <li key={strength}>{strength}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {item.improvements.length > 0 ? (
                    <div className="mt-3">
                      <p className="text-xs text-amber-300">Improvements</p>
                      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-200">
                        {item.improvements.map((improvement) => (
                          <li key={improvement}>{improvement}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </section>
        ) : null}
      </div>
    </main>
  );
}
