"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import { apiRequest, ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { JobOut } from "@/types";

const MIN_CONTENT_LENGTH = 50;

export default function NewJobPage(): JSX.Element {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [content, setContent] = useState("");

  const [result, setResult] = useState<JobOut | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const contentTooShort = content.trim().length > 0 && content.trim().length < MIN_CONTENT_LENGTH;

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setResult(null);

    if (!isAuthenticated) {
      setErrorMessage("You need to be logged in to save a job description.");
      return;
    }

    if (content.trim().length < MIN_CONTENT_LENGTH) {
      setErrorMessage(`Job description must be at least ${MIN_CONTENT_LENGTH} characters.`);
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
      setResult(response);
      // Clear form after success
      setTitle("");
      setCompany("");
      setContent("");
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Something went wrong. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (authLoading) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
          <h1 className="text-3xl font-semibold text-white">Add Job Description</h1>
          <p className="mt-2 text-sm text-slate-300">Checking your session...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">

        {/* Header */}
        <div>
          <Link
            href="/jobs"
            className="text-xs text-slate-400 transition hover:text-slate-200"
          >
            ← Job Descriptions
          </Link>
          <h1 className="mt-1 text-3xl font-semibold text-white">Add Job Description</h1>
          <p className="mt-1 text-sm text-slate-300">
            Paste a job description to extract required skills and keywords.
          </p>
        </div>

        {/* Success result */}
        {result ? (
          <section className="rounded-2xl border border-emerald-900/70 bg-emerald-950/30 p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-emerald-200">Job description saved</h2>

            {(result.title ?? result.company) ? (
              <p className="mt-1 text-sm text-emerald-100">
                {[result.title, result.company].filter(Boolean).join(" — ")}
              </p>
            ) : null}

            {result.required_skills.length > 0 ? (
              <div className="mt-4">
                <p className="text-xs uppercase tracking-wide text-emerald-400">
                  Required skills ({result.required_skills.length} detected)
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {result.required_skills.map((skill) => (
                    <span
                      key={skill}
                      className="rounded-full border border-emerald-800 bg-emerald-900/50 px-3 py-1 text-xs text-emerald-100"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-emerald-300/70">
                No technical skills detected — this may be a non-technical role.
              </p>
            )}

            {result.keywords.length > 0 ? (
              <div className="mt-4">
                <p className="text-xs uppercase tracking-wide text-emerald-400">
                  Top keywords
                </p>
                <p className="mt-1 text-sm text-emerald-200/80">
                  {result.keywords.slice(0, 20).join(", ")}
                </p>
              </div>
            ) : null}

            <div className="mt-5 flex flex-wrap gap-3">
              <Link
                href={`/jobs/${result.id}`}
                className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
              >
                View full detail
              </Link>
              <Link
                href="/jobs"
                className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                All job descriptions
              </Link>
              <button
                type="button"
                onClick={() => setResult(null)}
                className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                Add another
              </button>
            </div>
          </section>
        ) : null}

        {/* Form — hidden after success until user clicks "Add another" */}
        {!result ? (
          <form
            onSubmit={handleSubmit}
            className="rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="title" className="mb-2 block text-sm font-medium text-slate-200">
                  Job title <span className="text-slate-500">(optional)</span>
                </label>
                <input
                  id="title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
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
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-slate-500"
                  placeholder="e.g. Acme Corp"
                />
              </div>
            </div>

            <div className="mt-4">
              <label htmlFor="content" className="mb-2 block text-sm font-medium text-slate-200">
                Job description{" "}
                <span className="text-slate-500">(paste the full text)</span>
              </label>
              <textarea
                id="content"
                rows={12}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                required
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-slate-500 resize-y"
                placeholder="Paste the full job description here — the more detail, the better the skill extraction..."
              />
              <div className="mt-1 flex items-center justify-between">
                {contentTooShort ? (
                  <p className="text-xs text-amber-400">
                    Minimum {MIN_CONTENT_LENGTH} characters — {content.trim().length} so far.
                  </p>
                ) : (
                  <span />
                )}
                <p className="text-xs text-slate-500 ml-auto">
                  {content.trim().length} chars
                </p>
              </div>
            </div>

            {errorMessage ? (
              <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                {errorMessage}
              </div>
            ) : null}

            <div className="mt-6 flex items-center gap-3">
              <button
                type="submit"
                disabled={isSubmitting || content.trim().length < MIN_CONTENT_LENGTH}
                className="rounded-xl bg-white px-5 py-3 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Extracting skills..." : "Save & Extract Skills"}
              </button>
              <Link
                href="/jobs"
                className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                Cancel
              </Link>
            </div>
          </form>
        ) : null}
      </div>
    </main>
  );
}
