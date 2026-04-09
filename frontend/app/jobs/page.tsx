"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiRequest, ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { JobOut } from "@/types";

export default function JobsPage(): JSX.Element {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [isFetching, setIsFetching] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchJobs = useCallback(async (): Promise<void> => {
    try {
      const data = await apiRequest<JobOut[]>("/jobs/");
      setJobs(data);
      setErrorMessage(null);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Could not load job descriptions. Please try again.");
      }
    } finally {
      setIsFetching(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    void fetchJobs();
  }, [authLoading, fetchJobs, isAuthenticated, router]);

  if (authLoading || isFetching) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
          <h1 className="text-3xl font-semibold text-white">Job Descriptions</h1>
          <p className="mt-2 text-sm text-slate-300">Loading...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <Link
              href="/dashboard"
              className="text-xs text-slate-400 transition hover:text-slate-200"
            >
              ← Dashboard
            </Link>
            <h1 className="mt-1 text-3xl font-semibold text-white">Job Descriptions</h1>
            <p className="mt-1 text-sm text-slate-300">
              {jobs.length === 0
                ? "No job descriptions yet."
                : `${jobs.length} saved ${jobs.length === 1 ? "position" : "positions"}.`}
            </p>
          </div>
          <Link
            href="/jobs/new"
            className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            Add Job Description
          </Link>
        </div>

        {/* Error */}
        {errorMessage ? (
          <div className="rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {errorMessage}
          </div>
        ) : null}

        {/* Empty state */}
        {!errorMessage && jobs.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-10 text-center shadow-xl">
            <p className="text-sm text-slate-400">
              Paste in a job description to extract required skills and keywords.
            </p>
            <Link
              href="/jobs/new"
              className="mt-4 inline-block rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
            >
              Add your first job description
            </Link>
          </div>
        ) : null}

        {/* Job list */}
        {jobs.length > 0 ? (
          <ul className="space-y-3">
            {jobs.map((job) => (
              <li key={job.id}>
                <Link
                  href={`/jobs/${job.id}`}
                  className="block rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl transition hover:border-slate-600 hover:bg-slate-900"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-base font-medium text-white">
                        {job.title ?? "Untitled Position"}
                      </p>
                      <p className="mt-0.5 text-sm text-slate-400">
                        {job.company ?? "Company not specified"}
                      </p>
                    </div>
                    <p className="shrink-0 text-xs text-slate-500">
                      {new Date(job.created_at).toLocaleDateString()}
                    </p>
                  </div>

                  {job.required_skills.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {job.required_skills.slice(0, 8).map((skill) => (
                        <span
                          key={skill}
                          className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-0.5 text-xs text-slate-300"
                        >
                          {skill}
                        </span>
                      ))}
                      {job.required_skills.length > 8 ? (
                        <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-0.5 text-xs text-slate-500">
                          +{job.required_skills.length - 8} more
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </main>
  );
}
