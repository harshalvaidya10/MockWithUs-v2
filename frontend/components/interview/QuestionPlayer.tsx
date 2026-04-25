interface QuestionPlayerProps {
  category: string;
  questionText: string;
  rationale: string;
  isSpeaking: boolean;
  onToggleSpeech: () => void;
  speechError: string | null;
  isRecording: boolean;
  recordingSeconds: number;
  isUploading: boolean;
  isQuitting: boolean;
  hasRecording: boolean;
  recordingPreviewUrl: string | null;
  recordingError: string | null;
  submitError: string | null;
  lastTranscript: string | null;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onDiscardRecording: () => void;
  onSubmitAnswer: () => void;
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

export function QuestionPlayer({
  category,
  questionText,
  rationale,
  isSpeaking,
  onToggleSpeech,
  speechError,
  isRecording,
  recordingSeconds,
  isUploading,
  isQuitting,
  hasRecording,
  recordingPreviewUrl,
  recordingError,
  submitError,
  lastTranscript,
  onStartRecording,
  onStopRecording,
  onDiscardRecording,
  onSubmitAnswer,
}: QuestionPlayerProps): JSX.Element {
  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border bg-surface p-5">
        <p className="text-xs uppercase tracking-wide text-primary">{category}</p>
        <p className="mt-2 text-xl font-medium tracking-tight text-foreground">{questionText}</p>
        <p className="mt-3 text-sm text-foreground-muted">{rationale}</p>

        <button
          type="button"
          onClick={onToggleSpeech}
          disabled={isQuitting}
          className="app-btn-secondary mt-4"
        >
          {isSpeaking ? "Stop question audio" : "Play question audio"}
        </button>

        {speechError ? (
          <div className="mt-3 rounded-xl border border-warning bg-warning-subtle px-4 py-3 text-sm text-warning">
            {speechError}
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">Record your answer</h2>
        <p className="mt-2 text-sm text-foreground-muted">Use your microphone, then submit for transcription.</p>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onStartRecording}
            disabled={isRecording || isUploading || isQuitting}
            className="app-btn-secondary"
          >
            {isRecording ? "Recording..." : hasRecording ? "Re-record" : "Record"}
          </button>
          <button
            type="button"
            onClick={onStopRecording}
            disabled={!isRecording || isQuitting}
            className="app-btn-secondary"
          >
            Stop
          </button>
          <button
            type="button"
            onClick={onDiscardRecording}
            disabled={isQuitting || isRecording || (!hasRecording && !lastTranscript)}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-danger px-4 text-sm font-medium text-danger transition-colors duration-150 hover:bg-danger-subtle disabled:cursor-not-allowed disabled:opacity-60"
          >
            Discard
          </button>
        </div>

        {isRecording ? (
          <p className="mt-3 text-sm text-warning">Recording in progress: {formatDuration(recordingSeconds)}</p>
        ) : null}

        {recordingPreviewUrl ? (
          <div className="mt-3">
            <audio controls src={recordingPreviewUrl} className="w-full" />
          </div>
        ) : null}

        {recordingError ? (
          <div className="mt-3 rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
            {recordingError}
          </div>
        ) : null}

        {submitError ? (
          <div className="mt-3 rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
            {submitError}
          </div>
        ) : null}

        {lastTranscript ? (
          <div className="mt-3 rounded-xl border border-success bg-success-subtle px-4 py-3 text-sm text-success">
            <p className="font-medium">Answer saved and transcribed.</p>
            <p className="mt-1 text-foreground">{lastTranscript}</p>
          </div>
        ) : null}

        <button
          type="button"
          onClick={onSubmitAnswer}
          disabled={!hasRecording || isRecording || isUploading || isQuitting}
          className="app-btn-primary mt-4 h-10 px-6"
        >
          {isUploading ? "Uploading..." : "Submit answer"}
        </button>
      </section>
    </div>
  );
}
