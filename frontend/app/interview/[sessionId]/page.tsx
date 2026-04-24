"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { QuestionPlayer } from "@/components/interview/QuestionPlayer";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { LongRunningLoader } from "@/components/ui/LongRunningLoader";
import { ApiError, apiRequest } from "@/lib/api";
import { useInterview } from "@/hooks/useInterview";
import type {
  AudioAnswerSubmissionResponse,
  InterviewStartResponse,
  SessionAnswerListResponse,
} from "@/types";

const START_RESULT_STORAGE_PREFIX = "mockwithus:interview:start:";
const RECORDING_MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
];

function formatCategory(category: string): string {
  return category.replaceAll("_", " ");
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

function pickSupportedRecorderMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") {
    return undefined;
  }

  return RECORDING_MIME_CANDIDATES.find((candidate) => MediaRecorder.isTypeSupported(candidate));
}

function extensionForMimeType(mimeType: string): string {
  const normalized = mimeType.toLowerCase();
  if (normalized.includes("webm")) return ".webm";
  if (normalized.includes("ogg")) return ".ogg";
  if (normalized.includes("wav")) return ".wav";
  if (normalized.includes("mpeg") || normalized.includes("mp3")) return ".mp3";
  if (normalized.includes("mp4") || normalized.includes("m4a")) return ".m4a";
  return ".webm";
}

export default function InterviewSessionPage(): JSX.Element {
  const router = useRouter();
  const routeParams = useParams<{ sessionId?: string | string[] }>();
  const sessionIdParam = routeParams?.sessionId;
  const sessionId = Array.isArray(sessionIdParam) ? sessionIdParam[0] : sessionIdParam;

  const [sessionData, setSessionData] = useState<InterviewStartResponse | null>(null);
  const [answeredQuestionIds, setAnsweredQuestionIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [progressWarning, setProgressWarning] = useState<string | null>(null);

  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordedMimeType, setRecordedMimeType] = useState<string>("");
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  const [isUploading, setIsUploading] = useState(false);
  const [isQuitting, setIsQuitting] = useState(false);
  const [showQuitConfirm, setShowQuitConfirm] = useState(false);
  const [isFinishingFlow, setIsFinishingFlow] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastTranscript, setLastTranscript] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordingChunksRef = useRef<BlobPart[]>([]);
  const recordingIntervalRef = useRef<number | null>(null);

  const orderedQuestions = useMemo(() => {
    if (!sessionData) return [];
    return sessionData.questions.slice().sort((a, b) => a.order_index - b.order_index);
  }, [sessionData]);

  const {
    state: interviewState,
    setCurrentIndex,
  } = useInterview(orderedQuestions.length);

  const currentQuestion = orderedQuestions[interviewState.currentIndex] ?? null;
  const recordingPreviewUrl = useMemo(
    () => (recordedBlob ? URL.createObjectURL(recordedBlob) : null),
    [recordedBlob],
  );

  const clearRecordingTimer = useCallback((): void => {
    if (recordingIntervalRef.current !== null) {
      window.clearInterval(recordingIntervalRef.current);
      recordingIntervalRef.current = null;
    }
  }, []);

  const releaseMicrophone = useCallback((): void => {
    const activeStream = mediaStreamRef.current;
    if (activeStream) {
      activeStream.getTracks().forEach((track) => {
        track.stop();
      });
      mediaStreamRef.current = null;
    }
  }, []);

  const stopSpeaking = useCallback((): void => {
    if (typeof window === "undefined") return;
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  const stopRecording = useCallback((): void => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  }, []);

  const loadSessionData = useCallback(async (): Promise<void> => {
    if (!sessionId || typeof window === "undefined") {
      setSessionData(null);
      setAnsweredQuestionIds(new Set());
      setIsLoading(false);
      setErrorMessage("Invalid interview session URL.");
      setProgressWarning(null);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setProgressWarning(null);

    const raw = sessionStorage.getItem(`${START_RESULT_STORAGE_PREFIX}${sessionId}`);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as InterviewStartResponse;
        if (parsed.session_id === sessionId) {
          setSessionData(parsed);
        }
      } catch {
        // Ignore invalid cache entries.
      }
    }

    try {
      const sessionResponse = await apiRequest<InterviewStartResponse>(`/interviews/${sessionId}`);

      setSessionData(sessionResponse);
      sessionStorage.setItem(`${START_RESULT_STORAGE_PREFIX}${sessionId}`, JSON.stringify(sessionResponse));

      let answeredSet = new Set<string>();
      try {
        const answersResponse = await apiRequest<SessionAnswerListResponse>(`/answers/session/${sessionId}`);
        answeredSet = new Set(answersResponse.answers.map((answer) => answer.question_id));
      } catch (error) {
        setProgressWarning(
          getApiErrorMessage(error, "Could not load saved answer progress. Starting from question 1."),
        );
      }

      setAnsweredQuestionIds(answeredSet);
      const sortedQuestions = sessionResponse.questions
        .slice()
        .sort((left, right) => left.order_index - right.order_index);
      const firstUnansweredIndex = sortedQuestions.findIndex((question) => !answeredSet.has(question.id));
      setCurrentIndex(firstUnansweredIndex === -1 ? sortedQuestions.length : firstUnansweredIndex);
    } catch (error) {
      setSessionData(null);
      setAnsweredQuestionIds(new Set());
      setErrorMessage(getApiErrorMessage(error, "Could not load this interview session. Please try again."));
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, setCurrentIndex]);

  useEffect(() => {
    void loadSessionData();
  }, [loadSessionData]);

  useEffect(() => {
    return () => {
      stopSpeaking();
      stopRecording();
      clearRecordingTimer();
      releaseMicrophone();
    };
  }, [clearRecordingTimer, releaseMicrophone, stopRecording, stopSpeaking]);

  useEffect(() => {
    return () => {
      if (recordingPreviewUrl) {
        URL.revokeObjectURL(recordingPreviewUrl);
      }
    };
  }, [recordingPreviewUrl]);

  useEffect(() => {
    stopSpeaking();
    setSpeechError(null);
    setRecordingError(null);
    setSubmitError(null);
    setLastTranscript(null);
    setRecordedBlob(null);
    setRecordedMimeType("");
    setRecordingSeconds(0);
  }, [currentQuestion?.id, stopSpeaking]);

  async function handlePlayQuestion(): Promise<void> {
    if (!currentQuestion) return;
    if (typeof window === "undefined" || !window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") {
      setSpeechError("Speech playback is not supported in this browser.");
      return;
    }

    setSpeechError(null);
    stopSpeaking();

    const utterance = new SpeechSynthesisUtterance(currentQuestion.question_text);
    utterance.lang = "en-US";
    utterance.onend = () => {
      setIsSpeaking(false);
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      setSpeechError("Question playback failed. You can still read the question text.");
    };

    window.speechSynthesis.speak(utterance);
    setIsSpeaking(true);
  }

  async function handleStartRecording(): Promise<void> {
    if (!currentQuestion) return;
    if (isRecording || isQuitting) return;

    setRecordingError(null);
    setSubmitError(null);
    setLastTranscript(null);
    setRecordedBlob(null);
    setRecordedMimeType("");
    setRecordingSeconds(0);
    stopSpeaking();

    if (typeof window === "undefined" || !navigator.mediaDevices || typeof MediaRecorder === "undefined") {
      setRecordingError("Audio recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const mimeType = pickSupportedRecorderMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      recordingChunksRef.current = [];

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          recordingChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const finalMimeType = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(recordingChunksRef.current, { type: finalMimeType });
        setRecordedBlob(blob.size > 0 ? blob : null);
        setRecordedMimeType(finalMimeType);
        setIsRecording(false);
        clearRecordingTimer();
        releaseMicrophone();
      };

      recorder.onerror = () => {
        setRecordingError("Recording failed. Please try again.");
        setIsRecording(false);
        clearRecordingTimer();
        releaseMicrophone();
      };

      recorder.start();
      setIsRecording(true);
      recordingIntervalRef.current = window.setInterval(() => {
        setRecordingSeconds((current) => current + 1);
      }, 1000);
    } catch (error) {
      clearRecordingTimer();
      releaseMicrophone();

      if (error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "SecurityError")) {
        setRecordingError("Microphone permission denied. Allow microphone access and try again.");
        return;
      }
      setRecordingError("Could not start recording. Please check your microphone and try again.");
    }
  }

  function handleStopRecording(): void {
    stopRecording();
  }

  function handleDiscardRecording(): void {
    if (isRecording) {
      stopRecording();
    }
    setRecordedBlob(null);
    setRecordedMimeType("");
    setRecordingSeconds(0);
    setSubmitError(null);
    setLastTranscript(null);
  }

  async function handleSubmitAnswer(): Promise<void> {
    if (!sessionId || !currentQuestion) return;
    if (!recordedBlob || isRecording || isUploading || isQuitting) return;

    setIsUploading(true);
    setSubmitError(null);
    setLastTranscript(null);

    try {
      const effectiveMimeType = recordedMimeType || recordedBlob.type || "audio/webm";
      const audioFile = new File(
        [recordedBlob],
        `answer-${currentQuestion.id}${extensionForMimeType(effectiveMimeType)}`,
        { type: effectiveMimeType },
      );

      const payload = new FormData();
      payload.append("session_id", sessionId);
      payload.append("question_id", currentQuestion.id);
      payload.append("audio", audioFile);

      const response = await apiRequest<AudioAnswerSubmissionResponse>("/answers/audio", {
        method: "POST",
        body: payload,
      });

      const updatedAnswered = new Set(answeredQuestionIds);
      updatedAnswered.add(currentQuestion.id);
      setAnsweredQuestionIds(updatedAnswered);
      setLastTranscript(response.transcript_text);
      setRecordedBlob(null);
      setRecordedMimeType("");
      setRecordingSeconds(0);

      const nextIndex = orderedQuestions.findIndex((question) => !updatedAnswered.has(question.id));
      if (nextIndex === -1) {
        setIsFinishingFlow(true);
        setCurrentIndex(orderedQuestions.length);
        window.setTimeout(() => {
          router.push(`/interview/${sessionId}/results`);
        }, 250);
        return;
      }
      setCurrentIndex(nextIndex);
    } catch (error) {
      setSubmitError(getApiErrorMessage(error, "Could not submit spoken answer. Please try again."));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleQuitInterview(): Promise<void> {
    if (!sessionId || isQuitting || isUploading) return;

    setIsQuitting(true);
    setSubmitError(null);
    stopSpeaking();
    if (isRecording) {
      stopRecording();
    }
    clearRecordingTimer();
    releaseMicrophone();
    setRecordedBlob(null);
    setRecordedMimeType("");
    setRecordingSeconds(0);

    try {
      await apiRequest<void>(`/interviews/${sessionId}/complete`, {
        method: "POST",
      });
    } catch (error) {
      setSubmitError(getApiErrorMessage(error, "Could not mark interview as completed. Showing results anyway."));
    } finally {
      router.push(`/interview/${sessionId}/results`);
    }
  }

  const answeredCount = answeredQuestionIds.size;
  const totalQuestions = orderedQuestions.length;

  if (isLoading) {
    return (
      <main className="min-h-screen bg-background px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-border bg-surface p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Interview session</h1>
          <p className="mt-2 text-sm text-foreground-muted">Loading interview session...</p>
        </div>
      </main>
    );
  }

  if (errorMessage || !sessionData) {
    return (
      <main className="min-h-screen bg-background px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-border bg-surface p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Interview session</h1>
          <p className="mt-4 text-sm text-danger">{errorMessage ?? "Interview session data is unavailable."}</p>
          <div className="mt-5 flex gap-3">
            <Link
              href="/practice"
              className="app-btn-secondary"
            >
              Back to Practice
            </Link>
            <button
              type="button"
              onClick={() => {
                void loadSessionData();
              }}
              className="app-btn-primary"
            >
              Retry
            </button>
          </div>
        </div>
      </main>
    );
  }

  if (interviewState.isComplete || !currentQuestion) {
    return (
      <main className="min-h-screen bg-background px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-success bg-success-subtle p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Interview complete</h1>
          <p className="mt-3 text-sm text-success">
            You have submitted spoken answers for all {totalQuestions} questions.
          </p>
          <div className="mt-5">
            <Link
              href={`/interview/${sessionId}/results`}
              className="app-btn-primary"
            >
              Continue to Results
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-xl border border-border bg-surface p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">
                Question {interviewState.currentIndex + 1} of {totalQuestions}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-primary bg-primary-subtle px-2 py-0.5 text-xs font-medium text-primary">
                  {formatCategory(currentQuestion.category)}
                </span>
                <span className="text-xs text-foreground-muted">{answeredCount} answered</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                setShowQuitConfirm(true);
              }}
              disabled={isUploading || isQuitting}
              className="inline-flex h-8 items-center justify-center rounded-lg border border-danger px-3 text-xs font-medium text-danger transition-colors duration-150 hover:bg-danger-subtle disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isQuitting ? "Ending..." : "Exit"}
            </button>
          </div>

          <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-hover">
            <div
              className="h-full bg-primary"
              style={{
                width: `${Math.max(
                  4,
                  Math.min(100, ((Math.min(interviewState.currentIndex + 1, totalQuestions)) / Math.max(1, totalQuestions)) * 100),
                )}%`,
              }}
            />
          </div>
          <p className="mt-2 text-xs text-foreground-muted">
            {Math.round((answeredCount / Math.max(1, totalQuestions)) * 100)}% answered
          </p>
        </header>

        {progressWarning ? (
          <div className="rounded-xl border border-warning bg-warning-subtle px-4 py-3 text-sm text-warning">
            {progressWarning}
          </div>
        ) : null}

        <QuestionPlayer
          category={formatCategory(currentQuestion.category)}
          questionText={currentQuestion.question_text}
          rationale={currentQuestion.rationale}
          isSpeaking={isSpeaking}
          onToggleSpeech={() => {
            if (isSpeaking) {
              stopSpeaking();
            } else {
              void handlePlayQuestion();
            }
          }}
          speechError={speechError}
          isRecording={isRecording}
          recordingSeconds={recordingSeconds}
          isUploading={isUploading}
          isQuitting={isQuitting}
          hasRecording={Boolean(recordedBlob)}
          recordingPreviewUrl={recordingPreviewUrl}
          recordingError={recordingError}
          submitError={submitError}
          lastTranscript={lastTranscript}
          onStartRecording={() => {
            void handleStartRecording();
          }}
          onStopRecording={handleStopRecording}
          onDiscardRecording={handleDiscardRecording}
          onSubmitAnswer={() => {
            void handleSubmitAnswer();
          }}
        />
      </div>

      {isFinishingFlow ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/20 px-6">
          <LongRunningLoader
            title="Evaluating your answers..."
            phrases={["Reviewing your answers...", "Scoring relevance and depth...", "Generating feedback..."]}
            className="w-full max-w-lg"
          />
        </div>
      ) : null}

      <ConfirmDialog
        open={showQuitConfirm}
        title="End this interview?"
        description="Submitted answers will be evaluated. Unsaved recording for this question will be discarded."
        confirmLabel="End Interview"
        cancelLabel="Cancel"
        onCancel={() => setShowQuitConfirm(false)}
        onConfirm={() => {
          setShowQuitConfirm(false);
          void handleQuitInterview();
        }}
        isConfirming={isQuitting}
      />
    </main>
  );
}
