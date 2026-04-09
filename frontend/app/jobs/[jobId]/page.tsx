"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { apiRequest, ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { JobDetailOut, ResumeUploadResponse, MatchResult } from "@/types";

function scoreColor(score: number): string {
  if (score >= 0.8) return "text-emerald-400";
  if (score >= 0.6) return "text-green-400";
  if (score >= 0.4) return "text-amber-400";
  return "text-red-400";
}

function scoreBorderColor(score: number): string {
  if (score >= 0.8) return "border-emerald-800 bg-emerald-950/30";
  if (score >= 0.6) return "border-green-800 bg-green-950/30";
  if (score >= 0.4) return "border-amber-800 bg-amber-950/30";
  return "border-red-800 bg-red-950/30";
}

function getApiErrorMessage(error: unknown, fallbackMessage: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallbackMessage;
}

function isResumeLike(resume: ResumeUploadResponse): boolean {
  // Backward-compatible default for older API payloads that omit this field.
  return resume.is_resume_like !== false;
}

export default function JobDetailPage(): JSX.Element {
  const routeParams = useParams<{ jobId?: string | string[] }>();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const jobIdParam = routeParams?.jobId;
  const jobId = Array.isArray(jobIdParam) ? jobIdParam[0] : jobIdParam;

  const [job, setJob] = useState<JobDetailOut | null>(null);
  const [isFetching, setIsFetching] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Resume picker
  const [resumes, setResumes] = useState<ResumeUploadResponse[]>([]);
  const [isResumesLoading, setIsResumesLoading] = useState(false);
  const [resumeLoadError, setResumeLoadError] = useState<string | null>(null);
  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [isMatchLoading, setIsMatchLoading] = useState(false);
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const [matchError, setMatchError] = useState<string | null>(null);
  const selectableResumes = resumes.filter(isResumeLike);

  const fetchResumes = useCallback(async (): Promise<void> => {
    setIsResumesLoading(true);
    setResumeLoadError(null);

    try {
      const data = await apiRequest<ResumeUploadResponse[]>("/resumes/");
      setResumes(data);
      const eligibleResumes = data.filter(isResumeLike);
      setSelectedResumeId((current) => {
        if (eligibleResumes.length === 0) return "";
        if (current && eligibleResumes.some((resume) => resume.id === current)) return current;
        return eligibleResumes[0].id;
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setResumeLoadError(
          "Could not load resumes from the API. Your backend may be running an older build. Restart backend and try again."
        );
      } else {
        setResumeLoadError(getApiErrorMessage(error, "Could not load resumes. Please try again."));
      }
      setResumes([]);
      setSelectedResumeId("");
    } finally {
      setIsResumesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!jobId) {
      setErrorMessage("Job description not found.");
      setIsFetching(false);
      return;
    }

    async function fetchJob(): Promise<void> {
      try {
        const data = await apiRequest<JobDetailOut>(`/jobs/${jobId}`);
        setJob(data);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          setErrorMessage("Job description not found.");
        } else {
          setErrorMessage(getApiErrorMessage(error, "Could not load job description. Please try again."));
        }
      } finally {
        setIsFetching(false);
      }
    }

    void fetchJob();
    void fetchResumes();
  }, [isAuthenticated, authLoading, router, jobId, fetchResumes]);

  async function handleRunMatch(): Promise<void> {
    if (!selectedResumeId || !jobId) return;
    setMatchError(null);
    setMatchResult(null);
    setIsMatchLoading(true);
    try {
      const query = new URLSearchParams({ resume_id: selectedResumeId });
      const data = await apiRequest<MatchResult>(
        `/jobs/${jobId}/match?${query.toString()}`
      );
      setMatchResult(data);
    } catch (error) {
      setMatchError(getApiErrorMessage(error, "Could not run match. Please try again."));
    } finally {
      setIsMatchLoading(false);
    }
  }

  if (authLoading || isFetching) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
          <p className="text-sm text-slate-300">Loading...</p>
        </div>
      </main>
    );
  }

  if (errorMessage || !job) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl space-y-4">
          <Link href="/jobs" className="text-xs text-slate-400 transition hover:text-slate-200">
            ← Job Descriptions
          </Link>
          <div className="rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {errorMessage ?? "Job description not found."}
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">

        {/* Breadcrumb + header */}
        <div>
          <Link href="/jobs" className="text-xs text-slate-400 transition hover:text-slate-200">
            ← Job Descriptions
          </Link>
          <h1 className="mt-1 text-3xl font-semibold text-white">
            {job.title ?? "Untitled Position"}
          </h1>
          {job.company ? (
            <p className="mt-1 text-sm text-slate-400">{job.company}</p>
          ) : null}
          <p className="mt-1 text-xs text-slate-500">
            Added {new Date(job.created_at).toLocaleString()}
          </p>
        </div>

        {/* Match with Resume */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <h2 className="text-lg font-semibold text-white">Match with Resume</h2>
          <p className="mt-1 text-sm text-slate-400">
            Select a resume to see how well it matches this job description.
          </p>

          {isResumesLoading ? (
            <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-sm text-slate-400">
              Loading resumes...
            </div>
          ) : resumeLoadError ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              <p>{resumeLoadError}</p>
              <button
                type="button"
                onClick={() => {
                  void fetchResumes();
                }}
                className="mt-3 rounded-lg border border-red-800 px-3 py-1.5 text-xs font-medium text-red-200 transition hover:bg-red-900/40"
              >
                Retry Resume Load
              </button>
            </div>
          ) : resumes.length === 0 ? (
            <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-sm text-slate-400">
              No resumes uploaded yet.{" "}
              <Link href="/interview/new" className="text-white underline underline-offset-2 hover:text-slate-300">
                Upload one first
              </Link>
              .
            </div>
          ) : (
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-48">
                <label htmlFor="resume-select" className="mb-1.5 block text-xs font-medium text-slate-400">
                  Resume
                </label>
                <select
                  id="resume-select"
                  value={selectedResumeId}
                  onChange={(e) => {
                    setSelectedResumeId(e.target.value);
                    setMatchResult(null);
                    setMatchError(null);
                  }}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white outline-none transition focus:border-slate-500"
                >
                  {selectableResumes.length === 0 ? (
                    <option value="" disabled>
                      No resume-like uploads available for matching
                    </option>
                  ) : null}
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id} disabled={!isResumeLike(r)}>
                      {r.filename} — {new Date(r.created_at).toLocaleDateString()}
                      {!isResumeLike(r) ? " (Not resume-like)" : ""}
                    </option>
                  ))}
                </select>
                {resumes.some((resume) => !isResumeLike(resume)) ? (
                  <p className="mt-1.5 text-xs text-amber-300">
                    Non-resume-like uploads are shown for visibility but are disabled for matching.
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={handleRunMatch}
                disabled={isMatchLoading || !selectedResumeId}
                className="rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isMatchLoading ? "Matching..." : "Run Match"}
              </button>
              <button
                type="button"
                onClick={() => {
                  void fetchResumes();
                }}
                className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                Refresh Resumes
              </button>
            </div>
          )}

          {matchError ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {matchError}
            </div>
          ) : null}

          {matchResult ? (
            <div className={`mt-5 rounded-xl border p-5 ${scoreBorderColor(matchResult.match_score)}`}>
              {/* Score */}
              <div className="flex items-baseline gap-2">
                <span className={`text-4xl font-bold ${scoreColor(matchResult.match_score)}`}>
                  {Math.round(matchResult.match_score * 100)}%
                </span>
                <span className="text-sm text-slate-400">match score</span>
              </div>

              {/* Summary */}
              <p className="mt-2 text-sm text-slate-200">{matchResult.match_summary}</p>

              {/* Skill gap columns */}
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {/* Matched */}
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-emerald-400">
                    Matched skills ({matchResult.skill_gaps.matched.length})
                  </p>
                  {matchResult.skill_gaps.matched.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {matchResult.skill_gaps.matched.map((s) => (
                        <span
                          key={s}
                          className="rounded-full border border-emerald-800 bg-emerald-900/50 px-2.5 py-0.5 text-xs text-emerald-100"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-500">None matched.</p>
                  )}
                </div>

                {/* Missing */}
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-red-400">
                    Missing skills ({matchResult.skill_gaps.missing.length})
                  </p>
                  {matchResult.skill_gaps.missing.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {matchResult.skill_gaps.missing.map((s) => (
                        <span
                          key={s}
                          className="rounded-full border border-red-800 bg-red-900/50 px-2.5 py-0.5 text-xs text-red-200"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-500">No gaps — great fit!</p>
                  )}
                </div>
              </div>

              {/* Coverage bar */}
              <div className="mt-5">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs text-slate-400">Skill coverage</p>
                  <p className="text-xs text-slate-400">
                    {Math.round(matchResult.skill_gaps.coverage * 100)}%
                  </p>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-emerald-500 transition-all"
                    style={{ width: `${Math.round(matchResult.skill_gaps.coverage * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Required skills */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <p className="text-xs uppercase tracking-wide text-slate-400">
            Required skills
            {job.required_skills.length > 0
              ? ` — ${job.required_skills.length} detected`
              : ""}
          </p>

          {job.required_skills.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {job.required_skills.map((skill) => (
                <span
                  key={skill}
                  className="rounded-full border border-emerald-800 bg-emerald-900/50 px-3 py-1 text-xs text-emerald-100"
                >
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-400">
              No technical skills detected — may be a non-technical role.
            </p>
          )}
        </div>

        {/* Keywords */}
        {job.keywords.length > 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
            <p className="text-xs uppercase tracking-wide text-slate-400">Top keywords</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {job.keywords.map((kw) => (
                <span
                  key={kw}
                  className="rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 text-xs text-slate-300"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {/* Full content */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <p className="text-xs uppercase tracking-wide text-slate-400">Full description</p>
          <pre className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-200 font-sans">
            {job.content}
          </pre>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-3 pb-8">
          <Link
            href="/jobs/new"
            className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            Add another job description
          </Link>
          <Link
            href="/jobs"
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            All job descriptions
          </Link>
        </div>

      </div>
    </main>
  );
}
