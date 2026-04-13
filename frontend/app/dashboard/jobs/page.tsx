"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, apiRequest } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { JobOut } from "@/types";

const MIN_CONTENT_LENGTH = 50;

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

export default function DashboardJobsPage(): JSX.Element {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formErrorMessage, setFormErrorMessage] = useState<string | null>(null);
  const [createdJob, setCreatedJob] = useState<JobOut | null>(null);

  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [isFetching, setIsFetching] = useState(true);
  const [listErrorMessage, setListErrorMessage] = useState<string | null>(null);

  const contentTooShort = content.trim().length > 0 && content.trim().length < MIN_CONTENT_LENGTH;

  const fetchJobs = useCallback(async (): Promise<void> => {
    try {
      const data = await apiRequest<JobOut[]>("/jobs/");
      setJobs(data);
      setListErrorMessage(null);
    } catch (error) {
      setListErrorMessage(getApiErrorMessage(error, "Could not load job descriptions. Please try again."));
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setFormErrorMessage(null);
    setCreatedJob(null);

    if (!isAuthenticated) {
      setFormErrorMessage("You need to be logged in to save a job description.");
      return;
    }

    if (content.trim().length < MIN_CONTENT_LENGTH) {
      setFormErrorMessage(`Job description must be at least ${MIN_CONTENT_LENGTH} characters.`);
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await apiRequest<JobOut>("/jobs/", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim() || null,
          company: company.trim() || null,
          content: content.trim(),
        }),
      });

      setCreatedJob(response);
      setTitle("");
      setCompany("");
      setContent("");
      await fetchJobs();
    } catch (error) {
      setFormErrorMessage(getApiErrorMessage(error, "Could not save job description. Please try again."));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (authLoading || isFetching) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
          <h1 className="text-3xl font-semibold text-white">Job Description</h1>
          <p className="mt-2 text-sm text-slate-300">Loading...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <Link href="/dashboard" className="text-xs text-slate-400 transition hover:text-slate-200">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-3xl font-semibold text-white">Job Description</h1>
          <p className="mt-2 text-sm text-slate-300">
            Add your target job description and review saved job posts.
          </p>
        </div>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <h2 className="text-lg font-semibold text-white">Add Job Description</h2>
          <form onSubmit={handleSubmit} className="mt-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="title" className="mb-2 block text-sm font-medium text-slate-200">
                  Job title <span className="text-slate-500">(optional)</span>
                </label>
                <input
                  id="title"
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-slate-500"
                  placeholder="e.g. Senior Backend Engineer"
                />
              </div>
              <div>
                <label htmlFor="company" className="mb-2 block text-sm font-medium text-slate-200">
                  Company <span className="text-slate-500">(optional)</span>
                </label>
                <input
                  id="company"
                  type="text"
                  value={company}
                  onChange={(event) => setCompany(event.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-slate-500"
                  placeholder="e.g. Acme Corp"
                />
              </div>
            </div>

            <div className="mt-4">
              <label htmlFor="content" className="mb-2 block text-sm font-medium text-slate-200">
                Job description
              </label>
              <textarea
                id="content"
                rows={10}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                required
                className="w-full resize-y rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-slate-500"
                placeholder="Paste the full job description here..."
              />
              <div className="mt-1 flex items-center justify-between">
                {contentTooShort ? (
                  <p className="text-xs text-amber-400">
                    Minimum {MIN_CONTENT_LENGTH} characters — {content.trim().length} so far.
                  </p>
                ) : (
                  <span />
                )}
                <p className="text-xs text-slate-500">{content.trim().length} chars</p>
              </div>
            </div>

            {formErrorMessage ? (
              <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                {formErrorMessage}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting || content.trim().length < MIN_CONTENT_LENGTH}
              className="mt-5 rounded-xl bg-white px-5 py-3 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Saving..." : "Save Job Description"}
            </button>
          </form>

          {createdJob ? (
            <div className="mt-4 rounded-xl border border-emerald-900 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100">
              Saved <span className="font-medium">{createdJob.title ?? "Untitled Position"}</span> successfully.
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-white">Saved Job Descriptions</h2>
            <button
              type="button"
              onClick={() => {
                setIsFetching(true);
                void fetchJobs();
              }}
              className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              Refresh
            </button>
          </div>

          {listErrorMessage ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {listErrorMessage}
            </div>
          ) : null}

          {jobs.length === 0 ? (
            <p className="mt-4 text-sm text-slate-400">No job descriptions saved yet.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {jobs.map((job) => (
                <li
                  key={job.id}
                  className="rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">
                        {job.title ?? "Untitled Position"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {job.company ?? "Company not specified"} ·{" "}
                        {new Date(job.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  {job.required_skills.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {job.required_skills.slice(0, 10).map((skill) => (
                        <span
                          key={skill}
                          className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-0.5 text-xs text-slate-300"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="pt-2">
          <Link
            href="/dashboard/matching"
            className="inline-block rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            Continue to Resume–JD Matching →
          </Link>
        </div>
      </div>
    </main>
  );
}
