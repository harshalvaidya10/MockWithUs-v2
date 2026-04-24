"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";

import { JDPicker } from "@/components/practice/JDPicker";
import { MatchPreview } from "@/components/practice/MatchPreview";
import { ModeSelector, type PracticeMode } from "@/components/practice/ModeSelector";
import { ResumePicker } from "@/components/practice/ResumePicker";
import { StepperWizard } from "@/components/practice/StepperWizard";
import { LongRunningLoader } from "@/components/ui/LongRunningLoader";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, apiRequest, startCodingSession } from "@/lib/api";
import type { CodingDifficulty, InterviewStartResponse, JobOut, MatchResult, ResumeUploadResponse } from "@/types";

const START_RESULT_STORAGE_PREFIX = "mockwithus:interview:start:";
const START_INTERVIEW_TIMEOUT_MS = 75_000;
const GENERATION_PHRASES = ["Reading your resume...", "Analyzing the job description...", "Crafting your questions..."];

const STEPS = ["Resume", "Job Description", "Mode & Start"];

function apiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}

function isResumeLike(resume: ResumeUploadResponse): boolean {
  return resume.is_resume_like !== false;
}

export default function PracticePage(): JSX.Element {
  const searchParams = useSearchParams();

  const [isLoading, setIsLoading] = useState(true);
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [isSavingJob, setIsSavingJob] = useState(false);
  const [isMatching, setIsMatching] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [startErrorMessage, setStartErrorMessage] = useState<string | null>(null);
  const [matchErrorMessage, setMatchErrorMessage] = useState<string | null>(null);

  const [resumes, setResumes] = useState<ResumeUploadResponse[]>([]);
  const [jobs, setJobs] = useState<JobOut[]>([]);

  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [selectedJobId, setSelectedJobId] = useState("");
  const [mode, setMode] = useState<PracticeMode>("interview");
  const [codingDifficulty, setCodingDifficulty] = useState<CodingDifficulty>("medium");
  const [showSettings, setShowSettings] = useState(false);

  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);

  const selectableResumes = useMemo(() => resumes.filter(isResumeLike), [resumes]);

  const activeStep = useMemo(() => {
    if (!selectedResumeId) return 0;
    if (!selectedJobId) return 1;
    return 2;
  }, [selectedJobId, selectedResumeId]);

  useEffect(() => {
    const requestedMode = searchParams.get("mode");
    if (requestedMode === "coding" || requestedMode === "interview") {
      setMode(requestedMode);
    }
  }, [searchParams]);

  useEffect(() => {
    let isCancelled = false;

    async function loadSetupData(): Promise<void> {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const [resumeData, jobData] = await Promise.all([
          apiRequest<ResumeUploadResponse[]>("/resumes/"),
          apiRequest<JobOut[]>("/jobs/"),
        ]);

        if (isCancelled) return;

        setResumes(resumeData);
        setJobs(jobData);

        const requestedResume = searchParams.get("resume") || "";
        const requestedJob = searchParams.get("job") || "";
        const eligibleResumes = resumeData.filter(isResumeLike);

        const validResumeIds = new Set(resumeData.map((item) => item.id));
        const validJobIds = new Set(jobData.map((item) => item.id));

        if (requestedResume && validResumeIds.has(requestedResume)) {
          setSelectedResumeId(requestedResume);
        } else if (eligibleResumes.length > 0) {
          setSelectedResumeId(eligibleResumes[0].id);
        }

        if (requestedJob && validJobIds.has(requestedJob)) {
          setSelectedJobId(requestedJob);
        } else if (jobData.length > 0) {
          setSelectedJobId(jobData[0].id);
        }
      } catch (error) {
        if (isCancelled) return;
        setErrorMessage(apiError(error, "Could not load practice setup data."));
      } finally {
        if (isCancelled) return;
        setIsLoading(false);
      }
    }

    void loadSetupData();

    return () => {
      isCancelled = true;
    };
  }, [searchParams]);

  useEffect(() => {
    if (!selectedResumeId || !selectedJobId) {
      setMatchResult(null);
      setMatchErrorMessage(null);
      return;
    }

    let isCancelled = false;
    const timeoutId = window.setTimeout(() => {
      setIsMatching(true);
      setMatchErrorMessage(null);
      const query = new URLSearchParams({ resume_id: selectedResumeId });
      void apiRequest<MatchResult>(`/jobs/${selectedJobId}/match?${query.toString()}`)
        .then((response) => {
          if (isCancelled) return;
          setMatchResult(response);
        })
        .catch((error: unknown) => {
          if (isCancelled) return;
          setMatchErrorMessage(apiError(error, "Could not run matching."));
          setMatchResult(null);
        })
        .finally(() => {
          if (isCancelled) return;
          setIsMatching(false);
        });
    }, 250);

    return () => {
      isCancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [selectedJobId, selectedResumeId]);

  async function handleUploadResume(file: File): Promise<void> {
    setIsUploadingResume(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiRequest<ResumeUploadResponse>("/resumes/upload", {
        method: "POST",
        body: formData,
      });

      setResumes((current) => [response, ...current]);
      setSelectedResumeId(response.id);
      toast.success("Resume uploaded.");
    } catch (error) {
      setErrorMessage(apiError(error, "Could not upload resume."));
      toast.error(apiError(error, "Could not upload resume."));
    } finally {
      setIsUploadingResume(false);
    }
  }

  async function handleCreateJob(value: { title: string; company: string; content: string }): Promise<void> {
    if (value.content.trim().length < 50) return;

    setIsSavingJob(true);
    setErrorMessage(null);

    try {
      const response = await apiRequest<JobOut>("/jobs/", {
        method: "POST",
        body: JSON.stringify({
          title: value.title.trim() || null,
          company: value.company.trim() || null,
          content: value.content.trim(),
        }),
      });

      setJobs((current) => {
        if (current.some((item) => item.id === response.id)) {
          return current;
        }
        return [response, ...current];
      });
      setSelectedJobId(response.id);
      toast.success("Job description saved.");
    } catch (error) {
      setErrorMessage(apiError(error, "Could not save job description."));
      toast.error(apiError(error, "Could not save job description."));
    } finally {
      setIsSavingJob(false);
    }
  }

  async function handleStart(): Promise<void> {
    if (!selectedResumeId || !selectedJobId) {
      setStartErrorMessage("Select a resume and job description first.");
      return;
    }

    setIsStarting(true);
    setStartErrorMessage(null);

    const abortController = new AbortController();
    const timeoutId = window.setTimeout(() => {
      abortController.abort();
    }, START_INTERVIEW_TIMEOUT_MS);

    try {
      if (mode === "coding") {
        const response = await startCodingSession(
          selectedResumeId,
          selectedJobId,
          codingDifficulty,
          abortController.signal,
        );
        window.location.href = `/coding/${response.session_id}`;
        return;
      }

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

      window.location.href = `/interview/${response.session_id}`;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setStartErrorMessage("Session generation timed out. Please try again.");
        toast.error("Session generation timed out. Please try again.");
      } else {
        const message = apiError(error, "Could not start session.");
        setStartErrorMessage(message);
        toast.error(message);
      }
    } finally {
      window.clearTimeout(timeoutId);
      setIsStarting(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="app-card">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Practice Setup</h2>
        <p className="mt-2 text-sm leading-relaxed text-foreground-muted">
          Configure once and start a mock session. Matching runs automatically when resume and JD are selected.
        </p>
      </section>

      <StepperWizard steps={STEPS} activeStep={activeStep} />

      {errorMessage ? (
        <div className="rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
          {errorMessage}
        </div>
      ) : null}

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : (
        <>
          <motion.section
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="rounded-xl border border-border bg-surface p-5"
          >
            <p className="text-sm font-semibold text-foreground">Step 1 — Resume</p>
            <p className="mt-1 text-xs text-foreground-muted">Pick an existing resume or upload a new one.</p>
            <div className="mt-4">
              <ResumePicker
                resumes={selectableResumes}
                selectedResumeId={selectedResumeId}
                isUploading={isUploadingResume}
                onSelectResume={setSelectedResumeId}
                onUploadResume={handleUploadResume}
              />
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25, ease: "easeOut", delay: 0.05 }}
            className="rounded-xl border border-border bg-surface p-5"
          >
            <p className="text-sm font-semibold text-foreground">Step 2 — Job Description</p>
            <p className="mt-1 text-xs text-foreground-muted">Select one or paste a new JD. New JD is auto-saved.</p>
            <div className="mt-4">
              <JDPicker
                jobs={jobs}
                selectedJobId={selectedJobId}
                isSaving={isSavingJob}
                onSelectJob={setSelectedJobId}
                onCreateJob={handleCreateJob}
              />
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25, ease: "easeOut", delay: 0.1 }}
            className="rounded-xl border border-border bg-surface p-5"
          >
            <p className="text-sm font-semibold text-foreground">Step 3 — Mode + Start</p>
            <div className="mt-4 space-y-4">
              <MatchPreview
                isLoading={isMatching}
                matchResult={matchResult}
                errorMessage={matchErrorMessage}
              />

              <ModeSelector
                mode={mode}
                codingDifficulty={codingDifficulty}
                showSettings={showSettings}
                onModeChange={setMode}
                onDifficultyChange={setCodingDifficulty}
                onToggleSettings={() => setShowSettings((value) => !value)}
              />

              {startErrorMessage ? (
                <div className="rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
                  {startErrorMessage}
                </div>
              ) : null}

              <button
                type="button"
                onClick={() => {
                  void handleStart();
                }}
                disabled={isStarting || !selectedResumeId || !selectedJobId}
                className="app-btn-primary h-10 px-6"
              >
                {isStarting ? "Starting..." : "Start"}
              </button>
            </div>
          </motion.section>
        </>
      )}

      <AnimatePresence>
        {isStarting ? (
          <motion.div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/20 px-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
          >
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-lg"
            >
              <LongRunningLoader
                title={mode === "coding" ? "Generating coding challenge..." : "Preparing your mock interview..."}
                phrases={GENERATION_PHRASES}
              />
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
