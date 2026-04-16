"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

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
  return category.replace("_", " ");
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

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
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
    if (isRecording) return;

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
    if (!recordedBlob || isRecording || isUploading) return;

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
        setCurrentIndex(orderedQuestions.length);
        router.push(`/interview/results/${sessionId}`);
        return;
      }
      setCurrentIndex(nextIndex);
    } catch (error) {
      setSubmitError(getApiErrorMessage(error, "Could not submit spoken answer. Please try again."));
    } finally {
      setIsUploading(false);
    }
  }

  const answeredCount = answeredQuestionIds.size;
  const totalQuestions = orderedQuestions.length;

  if (isLoading) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
          <h1 className="text-3xl font-semibold text-white">Interview session</h1>
          <p className="mt-2 text-sm text-slate-300">Loading interview session...</p>
        </div>
      </main>
    );
  }

  if (errorMessage || !sessionData) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
          <h1 className="text-3xl font-semibold text-white">Interview session</h1>
          <p className="mt-4 text-sm text-red-300">{errorMessage ?? "Interview session data is unavailable."}</p>
          <div className="mt-5 flex gap-3">
            <Link
              href="/dashboard/matching"
              className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              Back to Matching
            </Link>
            <button
              type="button"
              onClick={() => {
                void loadSessionData();
              }}
              className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
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
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-emerald-800 bg-emerald-950/20 p-8">
          <h1 className="text-3xl font-semibold text-white">Interview complete</h1>
          <p className="mt-3 text-sm text-emerald-100">
            You have submitted spoken answers for all {totalQuestions} questions.
          </p>
          <div className="mt-5">
            <Link
              href={`/interview/results/${sessionId}`}
              className="rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
            >
              Continue to Results
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Link href="/dashboard/matching" className="text-xs text-slate-400 transition hover:text-slate-200">
              ← Back to Matching
            </Link>
            <h1 className="mt-1 text-3xl font-semibold text-white">Audio Interview Session</h1>
            <p className="mt-2 text-sm text-slate-300">
              Session ID: <span className="font-mono">{sessionId}</span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-slate-300">
              Question {interviewState.currentIndex + 1} of {totalQuestions}
            </p>
            <p className="text-xs text-slate-400">{answeredCount} answered</p>
          </div>
        </div>

        {progressWarning ? (
          <div className="rounded-xl border border-amber-900 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
            {progressWarning}
          </div>
        ) : null}

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <p className="text-xs uppercase tracking-wide text-slate-400">
            {formatCategory(currentQuestion.category)}
          </p>
          <p className="mt-2 text-xl font-medium text-white">{currentQuestion.question_text}</p>
          <p className="mt-3 text-sm text-slate-400">{currentQuestion.rationale}</p>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                if (isSpeaking) {
                  stopSpeaking();
                } else {
                  void handlePlayQuestion();
                }
              }}
              className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              {isSpeaking ? "Stop Question Audio" : "Play Question Audio"}
            </button>
          </div>
          {speechError ? (
            <div className="mt-3 rounded-xl border border-amber-900 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
              {speechError}
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <h2 className="text-lg font-semibold text-white">Record Spoken Answer</h2>
          <p className="mt-2 text-sm text-slate-300">
            Record your response using the microphone, then submit it for transcription.
          </p>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                void handleStartRecording();
              }}
              disabled={isRecording || isUploading}
              className="rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isRecording ? "Recording..." : recordedBlob ? "Re-record" : "Start Recording"}
            </button>
            <button
              type="button"
              onClick={handleStopRecording}
              disabled={!isRecording}
              className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Stop Recording
            </button>
            <button
              type="button"
              onClick={handleDiscardRecording}
              disabled={isRecording || (!recordedBlob && !lastTranscript)}
              className="rounded-xl border border-red-800 px-4 py-2.5 text-sm font-medium text-red-200 transition hover:bg-red-950/40 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Discard
            </button>
          </div>

          {isRecording ? (
            <p className="mt-3 text-sm text-amber-300">
              Recording in progress: <span className="font-mono">{formatDuration(recordingSeconds)}</span>
            </p>
          ) : null}

          {recordingPreviewUrl ? (
            <div className="mt-4">
              <p className="mb-2 text-sm text-slate-300">Recorded preview</p>
              <audio controls src={recordingPreviewUrl} className="w-full" />
            </div>
          ) : null}

          {recordingError ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {recordingError}
            </div>
          ) : null}

          {submitError ? (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {submitError}
            </div>
          ) : null}

          {lastTranscript ? (
            <div className="mt-4 rounded-xl border border-emerald-900 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100">
              <p className="font-medium">Answer saved and transcribed.</p>
              <p className="mt-1 text-emerald-200">{lastTranscript}</p>
            </div>
          ) : null}

          <div className="mt-5">
            <button
              type="button"
              onClick={() => {
                void handleSubmitAnswer();
              }}
              disabled={!recordedBlob || isRecording || isUploading}
              className="rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUploading ? "Uploading & Transcribing..." : "Submit Spoken Answer"}
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
