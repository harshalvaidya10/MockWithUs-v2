"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, apiRequest } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { ResumeUploadResponse } from "@/types";

const ACCEPTED_FILE_TYPES = ".pdf,.docx";
const NON_RESUME_ERROR_FRAGMENT = "does not appear to be a resume";
const SUSPICIOUS_FILENAME_PATTERN = /(plan|roadmap|proposal|strategy|requirements|spec)/i;

function isResumeLike(resume: ResumeUploadResponse): boolean {
  return resume.is_resume_like !== false;
}

function formatResumeUploadError(message: string): string {
  if (message.toLowerCase().includes(NON_RESUME_ERROR_FRAGMENT)) {
    return "This file looks like a non-resume document (for example, a project plan). Please upload your resume/CV in PDF or DOCX format.";
  }
  return message;
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

export default function DashboardResumesPage(): JSX.Element {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadErrorMessage, setUploadErrorMessage] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<ResumeUploadResponse | null>(null);

  const [resumes, setResumes] = useState<ResumeUploadResponse[]>([]);
  const [isFetching, setIsFetching] = useState(true);
  const [listErrorMessage, setListErrorMessage] = useState<string | null>(null);
  const [isDeletingResumeId, setIsDeletingResumeId] = useState<string | null>(null);

  const selectedFileLooksSuspicious =
    selectedFile !== null && SUSPICIOUS_FILENAME_PATTERN.test(selectedFile.name);

  const fetchResumes = useCallback(async (): Promise<void> => {
    try {
      const data = await apiRequest<ResumeUploadResponse[]>("/resumes/");
      setResumes(data);
      setListErrorMessage(null);
    } catch (error) {
      setListErrorMessage(getApiErrorMessage(error, "Could not load resumes. Please try again."));
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
  }, [authLoading, fetchResumes, isAuthenticated, router]);

  async function handleUpload(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setUploadErrorMessage(null);
    setUploadResult(null);

    if (!isAuthenticated) {
      setUploadErrorMessage("You need to log in before uploading a resume.");
      return;
    }

    if (!selectedFile) {
      setUploadErrorMessage("Please choose a PDF or DOCX file.");
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await apiRequest<ResumeUploadResponse>("/resumes/upload", {
        method: "POST",
        body: formData,
      });

      setUploadResult(response);
      setSelectedFile(null);
      await fetchResumes();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUploadErrorMessage("You need to log in before uploading a resume.");
      } else if (error instanceof ApiError) {
        setUploadErrorMessage(formatResumeUploadError(error.message));
      } else {
        setUploadErrorMessage("Unable to upload resume right now. Please try again.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDeleteResume(resume: ResumeUploadResponse): Promise<void> {
    const confirmed = window.confirm(`Delete "${resume.filename}"? This action cannot be undone.`);
    if (!confirmed) return;

    setListErrorMessage(null);
    setIsDeletingResumeId(resume.id);
    try {
      await apiRequest<void>(`/resumes/${resume.id}`, { method: "DELETE" });
      await fetchResumes();
    } catch (error) {
      setListErrorMessage(getApiErrorMessage(error, "Could not delete resume. Please try again."));
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
        <div>
          <Link href="/dashboard" className="text-xs text-slate-400 transition hover:text-slate-200">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-3xl font-semibold text-white">Resume</h1>
          <p className="mt-2 text-sm text-slate-300">
            Upload your resume and review previously uploaded files.
          </p>
        </div>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <h2 className="text-lg font-semibold text-white">Upload Resume</h2>
          <form onSubmit={handleUpload} className="mt-4 space-y-4">
            <div>
              <label htmlFor="resume" className="mb-2 block text-sm font-medium text-slate-200">
                Resume (PDF or DOCX)
              </label>
              <p className="mb-2 text-xs text-slate-400">
                Include sections like summary, experience, education, skills, and contact details.
              </p>
              <input
                id="resume"
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                onChange={(event) => {
                  setSelectedFile(event.target.files?.[0] ?? null);
                  setUploadErrorMessage(null);
                  setUploadResult(null);
                }}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-900 hover:file:bg-white"
              />
            </div>

            {selectedFile ? (
              <p className="text-sm text-slate-300">Selected file: {selectedFile.name}</p>
            ) : null}

            {selectedFileLooksSuspicious ? (
              <div className="rounded-xl border border-amber-900 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
                This filename looks like a plan/spec document. Upload may be rejected if it is not resume-like.
              </div>
            ) : null}

            {uploadErrorMessage ? (
              <div className="rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                {uploadErrorMessage}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isUploading}
              className="rounded-xl bg-white px-5 py-3 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUploading ? "Uploading..." : "Upload Resume"}
            </button>
          </form>

          {uploadResult ? (
            <div className="mt-4 rounded-xl border border-emerald-900 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100">
              Uploaded <span className="font-medium">{uploadResult.filename}</span> successfully.
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-white">Uploaded Resumes</h2>
            <button
              type="button"
              onClick={() => {
                setIsFetching(true);
                void fetchResumes();
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

          {resumes.length === 0 ? (
            <p className="mt-4 text-sm text-slate-400">No resumes uploaded yet.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {resumes.map((resume) => {
                const isDeleting = isDeletingResumeId === resume.id;
                return (
                  <li
                    key={resume.id}
                    className="rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-medium text-white">{resume.filename}</p>
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
                        <p className="mt-1 text-xs text-slate-500">
                          Uploaded {new Date(resume.created_at).toLocaleString()}
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
          )}
        </section>

        <div className="pt-2">
          <Link
            href="/dashboard/jobs"
            className="inline-block rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            Continue to Job Description →
          </Link>
        </div>
      </div>
    </main>
  );
}
