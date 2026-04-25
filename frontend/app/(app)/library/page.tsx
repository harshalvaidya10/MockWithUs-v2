"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { JDInput } from "@/components/practice/JDInput";
import { ResumeUploadDropzone } from "@/components/practice/ResumeUploadDropzone";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, apiRequest, apiRequestBlob } from "@/lib/api";
import type { JobDetailOut, JobOut, ResumeUploadResponse } from "@/types";

type LibraryTab = "resumes" | "jobs";

const ACTIVE_RESUME_KEY = "mockwithus:active-resume";

function apiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}

export default function LibraryPage(): JSX.Element {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") === "jobs" ? "jobs" : "resumes";

  const [tab, setTab] = useState<LibraryTab>(initialTab);
  const [resumes, setResumes] = useState<ResumeUploadResponse[]>([]);
  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [activeResumeId, setActiveResumeId] = useState<string>("");
  const [previewResume, setPreviewResume] = useState<ResumeUploadResponse | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewContentType, setPreviewContentType] = useState("");
  const [previewErrorMessage, setPreviewErrorMessage] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewJobSummary, setPreviewJobSummary] = useState<JobOut | null>(null);
  const [previewJobDetail, setPreviewJobDetail] = useState<JobDetailOut | null>(null);
  const [jobPreviewErrorMessage, setJobPreviewErrorMessage] = useState<string | null>(null);
  const [isJobPreviewLoading, setIsJobPreviewLoading] = useState(false);

  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [isSavingJob, setIsSavingJob] = useState(false);
  const [pendingDeleteResumeId, setPendingDeleteResumeId] = useState<string | null>(null);
  const [pendingDeleteJobId, setPendingDeleteJobId] = useState<string | null>(null);
  const [isDeletingResume, setIsDeletingResume] = useState(false);
  const [isDeletingJob, setIsDeletingJob] = useState(false);

  const fetchAll = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const [resumeData, jobData] = await Promise.all([
        apiRequest<ResumeUploadResponse[]>("/resumes/"),
        apiRequest<JobOut[]>("/jobs/"),
      ]);
      setResumes(resumeData);
      setJobs(jobData);
    } catch (error) {
      setErrorMessage(apiError(error, "Could not load library data."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(ACTIVE_RESUME_KEY);
    if (stored) {
      setActiveResumeId(stored);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const sortedResumes = useMemo(
    () => resumes.slice().sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [resumes],
  );

  const sortedJobs = useMemo(
    () => jobs.slice().sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [jobs],
  );

  async function handleUploadResume(file: File): Promise<void> {
    setIsUploadingResume(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiRequest<ResumeUploadResponse>("/resumes/upload", {
        method: "POST",
        body: formData,
      });

      setResumes((current) => [response, ...current]);
      setActiveResume(response.id);
      toast.success(`Uploaded ${response.filename}`);
    } catch (error) {
      const message = apiError(error, "Could not upload resume.");
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setIsUploadingResume(false);
    }
  }

  function setActiveResume(id: string): void {
    setActiveResumeId(id);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACTIVE_RESUME_KEY, id);
    }
  }

  async function handleDeleteResume(resumeId: string): Promise<void> {
    setPendingDeleteResumeId(resumeId);
  }

  async function confirmDeleteResume(): Promise<void> {
    const resumeId = pendingDeleteResumeId;
    if (!resumeId) return;
    setPendingDeleteResumeId(null);
    setIsDeletingResume(true);
    const previousResumes = resumes;
    setResumes((current) => current.filter((resume) => resume.id !== resumeId));
    const toastId = toast.loading("Deleting resume...");
    try {
      await apiRequest<void>(`/resumes/${resumeId}`, { method: "DELETE" });
      if (activeResumeId === resumeId) {
        setActiveResumeId("");
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(ACTIVE_RESUME_KEY);
        }
      }
      toast.success("Resume deleted.", { id: toastId });
    } catch (error) {
      setResumes(previousResumes);
      const message = apiError(error, "Could not delete resume.");
      setErrorMessage(message);
      toast.error(message, { id: toastId });
    } finally {
      setIsDeletingResume(false);
    }
  }

  async function handleOpenResumePreview(resume: ResumeUploadResponse): Promise<void> {
    setPreviewResume(resume);
    setPreviewErrorMessage(null);
    setIsPreviewLoading(true);

    try {
      const response = await apiRequestBlob(`/resumes/${resume.id}/file`);
      const nextPreviewUrl = URL.createObjectURL(response.blob);

      setPreviewContentType(response.contentType.toLowerCase());
      setPreviewUrl((current) => {
        if (current) {
          URL.revokeObjectURL(current);
        }
        return nextPreviewUrl;
      });
    } catch (error) {
      setPreviewErrorMessage(apiError(error, "Could not load resume preview."));
      setPreviewUrl((current) => {
        if (current) {
          URL.revokeObjectURL(current);
        }
        return null;
      });
    } finally {
      setIsPreviewLoading(false);
    }
  }

  function handleCloseResumePreview(): void {
    setPreviewResume(null);
    setPreviewErrorMessage(null);
    setPreviewContentType("");
    setIsPreviewLoading(false);
    setPreviewUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });
  }

  async function handleCreateJob(value: {
    title: string;
    company: string;
    content: string;
  }): Promise<void> {
    const normalizedContent = value.content.trim();
    if (normalizedContent.length < 50) {
      setErrorMessage("Job description must be at least 50 characters before it can be saved.");
      return;
    }

    setIsSavingJob(true);

    try {
      const response = await apiRequest<JobOut>("/jobs/", {
        method: "POST",
        body: JSON.stringify({
          title: value.title.trim() || null,
          company: value.company.trim() || null,
          content: normalizedContent,
        }),
      });

      setJobs((current) => {
        if (current.some((item) => item.id === response.id)) {
          return current;
        }
        return [response, ...current];
      });
      toast.success("Job description saved.");
    } catch (error) {
      const message = apiError(error, "Could not save job description.");
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setIsSavingJob(false);
    }
  }

  async function handleDeleteJob(jobId: string): Promise<void> {
    setPendingDeleteJobId(jobId);
  }

  async function confirmDeleteJob(): Promise<void> {
    const jobId = pendingDeleteJobId;
    if (!jobId) return;
    setPendingDeleteJobId(null);
    setIsDeletingJob(true);
    const previousJobs = jobs;
    setJobs((current) => current.filter((job) => job.id !== jobId));
    const toastId = toast.loading("Deleting job description...");

    try {
      await apiRequest<void>(`/jobs/${jobId}`, { method: "DELETE" });
      toast.success("Job description deleted.", { id: toastId });
    } catch (error) {
      setJobs(previousJobs);
      const message = apiError(error, "Could not delete job description.");
      setErrorMessage(message);
      toast.error(message, { id: toastId });
    } finally {
      setIsDeletingJob(false);
    }
  }

  async function handleOpenJobPreview(job: JobOut): Promise<void> {
    setPreviewJobSummary(job);
    setPreviewJobDetail(null);
    setJobPreviewErrorMessage(null);
    setIsJobPreviewLoading(true);

    try {
      const detail = await apiRequest<JobDetailOut>(`/jobs/${job.id}`);
      setPreviewJobDetail(detail);
    } catch (error) {
      setJobPreviewErrorMessage(apiError(error, "Could not load job description preview."));
    } finally {
      setIsJobPreviewLoading(false);
    }
  }

  function handleCloseJobPreview(): void {
    setPreviewJobSummary(null);
    setPreviewJobDetail(null);
    setJobPreviewErrorMessage(null);
    setIsJobPreviewLoading(false);
  }

  const canRenderInlinePdf =
    !!previewResume &&
    !!previewUrl &&
    (previewContentType.includes("application/pdf") || previewResume.filename.toLowerCase().endsWith(".pdf"));

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="app-card">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Library</h2>
        <p className="mt-2 text-sm text-foreground-muted">
          Manage your saved resumes and job descriptions in one place.
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setTab("resumes")}
            className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors duration-150 ${
              tab === "resumes"
                ? "border-primary bg-primary-subtle text-primary"
                : "border-border text-foreground-muted hover:bg-surface-hover hover:text-foreground"
            }`}
          >
            Resumes
          </button>
          <button
            type="button"
            onClick={() => setTab("jobs")}
            className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors duration-150 ${
              tab === "jobs"
                ? "border-primary bg-primary-subtle text-primary"
                : "border-border text-foreground-muted hover:bg-surface-hover hover:text-foreground"
            }`}
          >
            Job Descriptions
          </button>
        </div>
      </section>

      {errorMessage ? (
        <div className="rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
          {errorMessage}
        </div>
      ) : null}

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}

      {!isLoading && tab === "resumes" ? (
        <section className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <p className="text-sm font-semibold text-foreground">Upload resume</p>
            <div className="mt-3">
              <ResumeUploadDropzone onFileSelect={handleUploadResume} disabled={isUploadingResume} />
            </div>
          </div>

          {sortedResumes.length === 0 ? (
            <EmptyState
              title="No resumes in your library"
              description="Upload a resume to use it in practice setup."
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {sortedResumes.map((resume) => (
                <article
                  key={resume.id}
                  className="rounded-xl border border-border bg-surface p-4 transition-all duration-200 ease-out hover:border-border-strong hover:bg-surface-hover"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold text-foreground">{resume.filename}</p>
                    {activeResumeId === resume.id ? (
                      <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] text-primary-foreground">
                        Active
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-foreground-muted">{new Date(resume.created_at).toLocaleString()}</p>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        void handleOpenResumePreview(resume);
                      }}
                      className="app-btn-secondary h-8 px-3 text-xs"
                    >
                      View
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveResume(resume.id)}
                      className="app-btn-secondary h-8 px-3 text-xs"
                    >
                      Set Active
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDeleteResume(resume.id);
                      }}
                      className="inline-flex h-8 items-center justify-center gap-1 rounded-lg border border-danger px-3 text-xs font-medium text-danger transition-colors duration-150 hover:bg-danger-subtle"
                    >
                      {isDeletingResume && pendingDeleteResumeId === resume.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {!isLoading && tab === "jobs" ? (
        <section className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <p className="text-sm font-semibold text-foreground">Create job description</p>
            <p className="mt-1 text-xs text-foreground-muted">
              Paste a new JD and it will auto-save when you pause typing.
            </p>
            <div className="mt-3">
              <JDInput isSaving={isSavingJob} onSubmit={handleCreateJob} />
            </div>
          </div>

          {sortedJobs.length === 0 ? (
            <EmptyState
              title="No job descriptions in your library"
              description="Add a job description to use it during practice setup."
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {sortedJobs.map((job) => (
                <article
                  key={job.id}
                  className="rounded-xl border border-border bg-surface p-4 transition-all duration-200 ease-out hover:border-border-strong hover:bg-surface-hover"
                >
                  <p className="truncate text-sm font-semibold text-foreground">{job.title ?? "Untitled position"}</p>
                  <p className="mt-1 text-xs text-foreground-muted">{job.company ?? "Company not specified"}</p>
                  <p className="mt-1 text-xs text-foreground-subtle">{new Date(job.created_at).toLocaleString()}</p>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        void handleOpenJobPreview(job);
                      }}
                      className="app-btn-secondary h-8 px-3 text-xs"
                    >
                      View
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDeleteJob(job.id);
                      }}
                      className="inline-flex h-8 items-center justify-center gap-1 rounded-lg border border-danger px-3 text-xs font-medium text-danger transition-colors duration-150 hover:bg-danger-subtle"
                    >
                      {isDeletingJob && pendingDeleteJobId === job.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {previewJobSummary ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 p-4">
          <div className="max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_4px_12px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">
                  {previewJobSummary.title ?? "Untitled position"}
                </p>
                <p className="mt-1 text-xs text-foreground-muted">{previewJobSummary.company ?? "Company not specified"}</p>
              </div>
              <button
                type="button"
                onClick={handleCloseJobPreview}
                className="app-btn-secondary h-8 px-3 text-xs"
              >
                Close
              </button>
            </div>

            <div className="space-y-4 overflow-y-auto p-5">
              {isJobPreviewLoading ? <Skeleton className="h-[60vh] w-full" /> : null}

              {!isJobPreviewLoading && jobPreviewErrorMessage ? (
                <div className="rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
                  {jobPreviewErrorMessage}
                </div>
              ) : null}

              {!isJobPreviewLoading && !jobPreviewErrorMessage && previewJobDetail ? (
                <>
                  <div className="rounded-xl border border-border bg-surface-hover p-4">
                    <div className="grid gap-3 text-sm text-foreground md:grid-cols-2">
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Company</p>
                        <p className="mt-1">{previewJobDetail.company ?? "Company not specified"}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Position title</p>
                        <p className="mt-1">{previewJobDetail.title ?? "Untitled position"}</p>
                      </div>
                    </div>
                    <p className="mt-3 text-xs text-foreground-muted">
                      Added on {new Date(previewJobDetail.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div className="rounded-xl border border-border bg-surface-hover p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Full job description</p>
                    <div className="mt-2 max-h-[45vh] overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-surface p-3 text-sm leading-6 text-foreground">
                      {previewJobDetail.content}
                    </div>
                  </div>

                  <div className="rounded-xl border border-border bg-surface-hover p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Required skills</p>
                    {previewJobDetail.required_skills.length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {previewJobDetail.required_skills.map((skill) => (
                          <span
                            key={`${previewJobDetail.id}-required-${skill}`}
                            className="rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-foreground-muted"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-xs text-foreground-muted">No extracted required skills available.</p>
                    )}
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {previewResume ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 p-4">
          <div className="max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_4px_12px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{previewResume.filename}</p>
                <p className="mt-1 text-xs text-foreground-muted">
                  Uploaded {new Date(previewResume.created_at).toLocaleString()}
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseResumePreview}
                className="app-btn-secondary h-8 px-3 text-xs"
              >
                Close
              </button>
            </div>

            <div className="space-y-4 overflow-y-auto p-5">
              {isPreviewLoading ? (
                <Skeleton className="h-[60vh] w-full" />
              ) : null}

              {!isPreviewLoading && previewErrorMessage ? (
                <div className="rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
                  {previewErrorMessage}
                </div>
              ) : null}

              {!isPreviewLoading && !previewErrorMessage && canRenderInlinePdf && previewUrl ? (
                <iframe
                  src={previewUrl}
                  title={`Preview of ${previewResume.filename}`}
                  className="h-[60vh] w-full rounded-xl border border-border bg-white"
                />
              ) : null}

              {!isPreviewLoading && !previewErrorMessage && !canRenderInlinePdf ? (
                <div className="rounded-xl border border-border bg-surface-hover p-4">
                  <p className="text-sm text-foreground">
                    Inline preview is available for PDF resumes. This file type can be downloaded/opened instead.
                  </p>
                  {previewUrl ? (
                    <a
                      href={previewUrl}
                      download={previewResume.filename}
                      className="app-btn-secondary mt-3 h-8 px-3 text-xs"
                    >
                      Download resume
                    </a>
                  ) : null}
                </div>
              ) : null}

              <div className="rounded-xl border border-border bg-surface-hover p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Extracted skills</p>
                {previewResume.skills.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {previewResume.skills.map((skill) => (
                      <span
                        key={`${previewResume.id}-${skill}`}
                        className="rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-foreground-muted"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-foreground-muted">No extracted skills available.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingDeleteResumeId)}
        title="Delete this resume?"
        description="This resume will be permanently removed from your library and cannot be restored."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onCancel={() => setPendingDeleteResumeId(null)}
        onConfirm={() => {
          void confirmDeleteResume();
        }}
        icon={<Trash2 className="h-4 w-4" />}
        isConfirming={isDeletingResume}
      />

      <ConfirmDialog
        open={Boolean(pendingDeleteJobId)}
        title="Delete this job description?"
        description="This job description will be permanently removed from your library."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onCancel={() => setPendingDeleteJobId(null)}
        onConfirm={() => {
          void confirmDeleteJob();
        }}
        icon={<Trash2 className="h-4 w-4" />}
        isConfirming={isDeletingJob}
      />
    </div>
  );
}
