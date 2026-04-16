"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, getInterviewHistory } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { InterviewHistoryItem } from "@/types";

function formatDate(isoTimestamp: string): string {
  const value = new Date(isoTimestamp);
  if (Number.isNaN(value.getTime())) {
    return "Unknown date";
  }
  return value.toLocaleString();
}

export default function DashboardPage(): JSX.Element {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [history, setHistory] = useState<InterviewHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (isLoading || !isAuthenticated) {
      return;
    }

    let isCancelled = false;
    setHistoryLoading(true);
    setHistoryError(null);

    void getInterviewHistory()
      .then((response) => {
        if (isCancelled) return;
        setHistory(response.sessions);
      })
      .catch((error: unknown) => {
        if (isCancelled) return;
        if (error instanceof ApiError) {
          setHistoryError(error.message);
        } else {
          setHistoryError("Could not load previous interviews.");
        }
      })
      .finally(() => {
        if (isCancelled) return;
        setHistoryLoading(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [isAuthenticated, isLoading]);

  function handleLogout(): void {
    logout();
    router.push("/login");
  }

  if (isLoading) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
          <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
          <p className="mt-2 text-sm text-slate-300">Loading your account...</p>
        </div>
      </main>
    );
  }

  if (!isAuthenticated || !user) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
          <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
          <p className="mt-2 text-sm text-slate-300">Redirecting to login...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
            <p className="mt-2 text-sm text-slate-300">
              Welcome back{user.full_name ? `, ${user.full_name}` : ""}.
            </p>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            Logout
          </button>
        </div>

        <p className="mt-8 text-sm text-slate-300">
          Follow this flow to start an interview: Resume → Job Description → Resume–JD Matching.
        </p>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <Link
            href="/dashboard/resumes"
            className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5 transition hover:border-slate-600 hover:bg-slate-900"
          >
            <h2 className="text-lg font-semibold text-white">Resume</h2>
            <p className="mt-2 text-sm text-slate-300">
              Upload your resume and review previously uploaded files.
            </p>
          </Link>

          <Link
            href="/dashboard/jobs"
            className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5 transition hover:border-slate-600 hover:bg-slate-900"
          >
            <h2 className="text-lg font-semibold text-white">Job Description</h2>
            <p className="mt-2 text-sm text-slate-300">
              Save your target job description and review detected skills.
            </p>
          </Link>

          <Link
            href="/dashboard/matching"
            className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5 transition hover:border-slate-600 hover:bg-slate-900"
          >
            <h2 className="text-lg font-semibold text-white">Resume–JD Matching</h2>
            <p className="mt-2 text-sm text-slate-300">
              Run matching, review fit score, and start the interview session.
            </p>
          </Link>
        </div>

        <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-950/40 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Previous Interviews</h2>
              <p className="mt-1 text-sm text-slate-300">
                Review completed sessions or resume interviews still in progress.
              </p>
            </div>
          </div>

          {historyLoading ? (
            <p className="mt-4 text-sm text-slate-300">Loading interview history...</p>
          ) : null}

          {historyError ? (
            <p className="mt-4 text-sm text-red-300">{historyError}</p>
          ) : null}

          {!historyLoading && !historyError && history.length === 0 ? (
            <p className="mt-4 text-sm text-slate-300">
              No interview sessions yet. Start from Resume–JD Matching.
            </p>
          ) : null}

          {!historyLoading && !historyError && history.length > 0 ? (
            <div className="mt-4 space-y-3">
              {history.map((item) => {
                const statusLabel = item.is_complete ? "Completed" : "In Progress";
                const statusClasses = item.is_complete
                  ? "border-emerald-800 bg-emerald-950/30 text-emerald-200"
                  : "border-amber-800 bg-amber-950/30 text-amber-200";
                const destination = item.is_complete
                  ? `/interview/results/${item.session_id}`
                  : `/interview/${item.session_id}`;

                return (
                  <article
                    key={item.session_id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-4"
                  >
                    <div className="space-y-1">
                      <p className="text-sm text-slate-200">
                        Session <span className="font-mono text-xs">{item.session_id}</span>
                      </p>
                      <p className="text-xs text-slate-400">Created: {formatDate(item.created_at)}</p>
                      <p className="text-xs text-slate-400">
                        Progress: {item.answered_count} / {item.question_count} answers saved
                      </p>
                      {item.match_summary ? (
                        <p className="text-xs text-slate-400">Summary: {item.match_summary}</p>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`rounded-full border px-2.5 py-1 text-xs ${statusClasses}`}>
                        {statusLabel}
                      </span>
                      <Link
                        href={destination}
                        className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800"
                      >
                        {item.is_complete ? "View Results" : "Resume Interview"}
                      </Link>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
