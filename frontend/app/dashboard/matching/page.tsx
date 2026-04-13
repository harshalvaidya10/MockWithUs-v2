"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, apiRequest } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { InterviewStartResponse, JobOut, MatchResult, ResumeUploadResponse } from "@/types";

const START_RESULT_STORAGE_PREFIX = "mockwithus:interview:start:";
const START_INTERVIEW_TIMEOUT_MS = 75_000;

function isResumeLike(resume: ResumeUploadResponse): boolean {
  return resume.is_resume_like !== false;
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

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

export default function DashboardMatchingPage(): JSX.Element {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [resumes, setResumes] = useState<ResumeUploadResponse[]>([]);
  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [isFetching, setIsFetching] = useState(true);
  const [setupErrorMessage, setSetupErrorMessage] = useState<string | null>(null);

  const [isMatchLoading, setIsMatchLoading] = useState(false);
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const [matchError, setMatchError] = useState<string | null>(null);

  const [isStartingInterview, setIsStartingInterview] = useState(false);
  const [startInterviewError, setStartInterviewError] = useState<string | null>(null);

  const selectableResumes = resumes.filter(isResumeLike);
  const canRunMatch = selectedResumeId.length > 0 && selectedJobId.length > 0;

  const fetchSetupData = useCallback(async (): Promise<void> => {
    try {
      const [resumeData, jobData] = await Promise.all([
        apiRequest<ResumeUploadResponse[]>("/resumes/"),
        apiRequest<JobOut[]>("/jobs/"),
      ]);

      setResumes(resumeData);
      setJobs(jobData);
      setSetupErrorMessage(null);

      const eligibleResumes = resumeData.filter(isResumeLike);
      setSelectedResumeId((currentValue) => {
        if (eligibleResumes.length === 0) return "";
        if (currentValue && eligibleResumes.some((resume) => resume.id === currentValue)) {
          return currentValue;
        }
        return eligibleResumes[0].id;
      });

      setSelectedJobId((currentValue) => {
        if (jobData.length === 0) return "";
        if (currentValue && jobData.some((job) => job.id === currentValue)) {
          return currentValue;
        }
        return jobData[0].id;
      });
    } catch (error) {
      setSetupErrorMessage(
        getApiErrorMessage(error, "Unable to load resumes and job descriptions right now."),
      );
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
    void fetchSetupData();
  }, [authLoading, fetchSetupData, isAuthenticated, router]);

  async function handleRunMatch(): Promise<void> {
    if (!canRunMatch) return;

    setMatchError(null);
    setStartInterviewError(null);
    setMatchResult(null);
    setIsMatchLoading(true);

    try {
      const query = new URLSearchParams({ resume_id: selectedResumeId });
      const response = await apiRequest<MatchResult>(`/jobs/${selectedJobId}/match?${query.toString()}`);
      setMatchResult(response);
    } catch (error) {
      setMatchError(getApiErrorMessage(error, "Could not run matching. Please try again."));
    } finally {
      setIsMatchLoading(false);
    }
  }

async function handleStartInterview(): Promise<void> {
    if (!canRunMatch) return;

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
          resume_id: selectedResumeId,
          job_id: selectedJobId,
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
        getApiErrorMessage(error, "Could not start interview session. Please try again."),
      );
    } finally {
      window.clearTimeout(timeoutId);
      setIsStartingInterview(false);
    }
  }

  if (authLoading || isFetching) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
          <h1 className="text-3xl font-semibold text-white">Resume–JD Matching</h1>
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
          <h1 className="mt-1 text-3xl font-semibold text-white">Resume–JD Matching</h1>
          <p className="mt-2 text-sm text-slate-300">
            Select a resume and a job description, run matching, then start your interview session.
          </p>
        </div>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1">
              <label htmlFor="resume-select" className="mb-1.5 block text-xs font-medium text-slate-400">
                Resume
              </label>
              <select
                id="resume-select"
                value={selectedResumeId}
                onChange={(event) => {
                  setSelectedResumeId(event.target.value);
                  setMatchError(null);
                  setMatchResult(null);
                  setStartInterviewError(null);
                }}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white outline-none transition focus:border-slate-500"
              >
                {selectableResumes.length === 0 ? (
                  <option value="" disabled>
                    No resume-like uploads available
                  </option>
                ) : null}
                {resumes.map((resume) => (
                  <option key={resume.id} value={resume.id} disabled={!isResumeLike(resume)}>
                    {resume.filename}
                    {!isResumeLike(resume) ? " (Not resume-like)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="min-w-56 flex-1">
              <label htmlFor="job-select" className="mb-1.5 block text-xs font-medium text-slate-400">
                Job Description
              </label>
              <select
                id="job-select"
                value={selectedJobId}
                onChange={(event) => {
                  setSelectedJobId(event.target.value);
                  setMatchError(null);
                  setMatchResult(null);
                  setStartInterviewError(null);
                }}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white outline-none transition focus:border-slate-500"
              >
                {jobs.length === 0 ? (
                  <option value="" disabled>
                    No saved job descriptions available
                  </option>
                ) : null}
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title ?? "Untitled Position"} {job.company ? `— ${job.company}` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                void handleRunMatch();
              }}
              disabled={isMatchLoading || !canRunMatch}
              className="rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isMatchLoading ? "Running Match..." : "Run Matching"}
            </button>

            <button
              type="button"
              onClick={() => {
                setIsFetching(true);
                void fetchSetupData();
              }}
              className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              Refresh Data
            </button>
          </div>

          {setupErrorMessage ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {setupErrorMessage}
            </div>
          ) : null}

          {selectableResumes.length === 0 || jobs.length === 0 ? (
            <div className="mt-4 rounded-xl border border-amber-900 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
              {selectableResumes.length === 0 ? (
                <span>
                  No resume-like uploads found.{" "}
                  <Link href="/dashboard/resumes" className="underline underline-offset-2">
                    Go to Resume page
                  </Link>
                  .
                </span>
              ) : null}
              {selectableResumes.length === 0 && jobs.length === 0 ? <span> </span> : null}
              {jobs.length === 0 ? (
                <span>
                  No job descriptions found.{" "}
                  <Link href="/dashboard/jobs" className="underline underline-offset-2">
                    Go to Job Description page
                  </Link>
                  .
                </span>
              ) : null}
            </div>
          ) : null}

          {matchError ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {matchError}
            </div>
          ) : null}

          {matchResult ? (
            <div className={`mt-5 rounded-xl border p-5 ${scoreBorderColor(matchResult.match_score)}`}>
              <div className="flex items-baseline gap-2">
                <span className={`text-4xl font-bold ${scoreColor(matchResult.match_score)}`}>
                  {Math.round(matchResult.match_score * 100)}%
                </span>
                <span className="text-sm text-slate-400">match score</span>
              </div>

              <p className="mt-2 text-sm text-slate-200">{matchResult.match_summary}</p>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => {
                    void handleStartInterview();
                  }}
                  disabled={isStartingInterview}
                  className="rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isStartingInterview ? "Generating Questions..." : "Start Interview"}
                </button>
                {isStartingInterview ? (
                  <p className="mt-2 text-xs text-slate-400">
                    This can take up to a minute depending on model response time.
                  </p>
                ) : null}
              </div>

              {startInterviewError ? (
                <div className="mt-3 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                  {startInterviewError}
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
