"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiRequest, ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { ResumeUploadResponse } from "@/types";

function isResumeLike(resume: ResumeUploadResponse): boolean {
  // Backward-compatible default for older API payloads that omit this field.
  return resume.is_resume_like !== false;
}

export default function ResumesPage(): JSX.Element {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [resumes, setResumes] = useState<ResumeUploadResponse[]>([]);
  const [isFetching, setIsFetching] = useState(true);
  const [isDeletingResumeId, setIsDeletingResumeId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchResumes = useCallback(async (): Promise<void> => {
    try {
      const data = await apiRequest<ResumeUploadResponse[]>("/resumes/");
      setResumes(data);
      setErrorMessage(null);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Could not load resumes. Please try again.");
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

    void fetchResumes();
  }, [authLoading, isAuthenticated, fetchResumes, router]);

  async function handleDeleteResume(resume: ResumeUploadResponse): Promise<void> {
    const confirmed = window.confirm(
      `Delete "${resume.filename}"? This action cannot be undone.`
    );
    if (!confirmed) return;

    setErrorMessage(null);
    setIsDeletingResumeId(resume.id);
    try {
      await apiRequest<void>(`/resumes/${resume.id}`, { method: "DELETE" });
      setResumes((prev) =>
        prev.filter((item) => String(item.id) !== String(resume.id))
      );
      await fetchResumes();
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        if (error.message === "Resume not found.") {
          // If already deleted on backend, remove stale UI row and continue.
          setResumes((prev) =>
            prev.filter((item) => String(item.id) !== String(resume.id))
          );
          await fetchResumes();
        } else {
          setErrorMessage(
            "Delete endpoint is unavailable. Restart backend to load latest API changes."
          );
        }
      } else if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Could not delete resume. Please try again.");
      }
    } finally {
      setIsDeletingResumeId(null);
    }
  }

  if (authLoading || isFetching) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
          <h1 className="text-3xl font-semibold text-white">Resumes</h1>
          <p className="mt-2 text-sm text-slate-300">Loading...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <Link href="/dashboard" className="text-xs text-slate-400 transition hover:text-slate-200">
              ← Dashboard
            </Link>
            <h1 className="mt-1 text-3xl font-semibold text-white">Resumes</h1>
            <p className="mt-1 text-sm text-slate-300">
              {resumes.length === 0
                ? "No resumes uploaded yet."
                : `${resumes.length} uploaded ${resumes.length === 1 ? "resume" : "resumes"}.`}
            </p>
          </div>
          <Link
            href="/interview/new"
            className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            Upload Resume
          </Link>
        </div>

        {errorMessage ? (
          <div className="rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {errorMessage}
          </div>
        ) : null}

        {!errorMessage && resumes.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-10 text-center shadow-xl">
            <p className="text-sm text-slate-400">
              Upload a resume to start matching against job descriptions.
            </p>
            <Link
              href="/interview/new"
              className="mt-4 inline-block rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
            >
              Upload your first resume
            </Link>
          </div>
        ) : null}

        {resumes.length > 0 ? (
          <ul className="space-y-3">
            {resumes.map((resume) => {
              const isDeleting = isDeletingResumeId === resume.id;

              return (
                <li
                  key={resume.id}
                  className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-base font-medium text-white">{resume.filename}</p>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                            isResumeLike(resume)
                              ? "border border-emerald-800 bg-emerald-950/50 text-emerald-200"
                              : "border border-amber-800 bg-amber-950/50 text-amber-200"
                          }`}
                        >
                          {isResumeLike(resume) ? "Resume-like" : "Non-resume"}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500">
                        Uploaded {new Date(resume.created_at).toLocaleString()}
                      </p>
                      <p className="mt-0.5 font-mono text-[11px] text-slate-600">
                        ID: {resume.id}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDeleteResume(resume);
                      }}
                      disabled={isDeleting}
                      className="rounded-xl border border-red-800 px-3 py-1.5 text-xs font-medium text-red-200 transition hover:bg-red-950/40 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isDeleting ? "Deleting..." : "Delete"}
                    </button>
                  </div>

                  {resume.skills.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {resume.skills.map((skill) => (
                        <span
                          key={`${resume.id}-${skill}`}
                          className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-0.5 text-xs text-slate-300"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-slate-500">No skills detected.</p>
                  )}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </main>
  );
}
