import type { CodingDifficulty } from "@/types";

export type PracticeMode = "interview" | "coding";

interface ModeSelectorProps {
  mode: PracticeMode;
  codingDifficulty: CodingDifficulty;
  showSettings: boolean;
  onModeChange: (mode: PracticeMode) => void;
  onDifficultyChange: (difficulty: CodingDifficulty) => void;
  onToggleSettings: () => void;
}

export function ModeSelector({
  mode,
  codingDifficulty,
  showSettings,
  onModeChange,
  onDifficultyChange,
  onToggleSettings,
}: ModeSelectorProps): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <button
          type="button"
          onClick={() => onModeChange("interview")}
          className={`rounded-xl border p-4 text-left transition-all duration-200 ease-out ${
            mode === "interview"
              ? "border-primary bg-primary-subtle"
              : "border-border bg-surface hover:border-border-strong hover:bg-surface-hover"
          }`}
        >
          <p className="text-base font-semibold text-foreground">Mock Interview</p>
          <p className="mt-1 text-sm text-foreground-muted">Audio Q&A with AI feedback.</p>
        </button>

        <button
          type="button"
          onClick={() => onModeChange("coding")}
          className={`rounded-xl border p-4 text-left transition-all duration-200 ease-out ${
            mode === "coding"
              ? "border-primary bg-primary-subtle"
              : "border-border bg-surface hover:border-border-strong hover:bg-surface-hover"
          }`}
        >
          <p className="text-base font-semibold text-foreground">Coding Mock</p>
          <p className="mt-1 text-sm text-foreground-muted">Monaco coding round with hidden tests.</p>
        </button>
      </div>

      <button
        type="button"
        onClick={onToggleSettings}
        className="app-btn-secondary"
      >
        {showSettings ? "Hide optional settings" : "Show optional settings"}
      </button>

      {showSettings ? (
        <div className="rounded-xl border border-border bg-surface p-4">
          {mode === "coding" ? (
            <div>
              <p className="text-sm font-medium text-foreground">Coding difficulty</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => onDifficultyChange("medium")}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                    codingDifficulty === "medium"
                      ? "border-warning bg-warning-subtle text-warning"
                      : "border-border text-foreground-muted hover:bg-surface-hover"
                  }`}
                >
                  Medium
                </button>
                <button
                  type="button"
                  onClick={() => onDifficultyChange("hard")}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                    codingDifficulty === "hard"
                      ? "border-danger bg-danger-subtle text-danger"
                      : "border-border text-foreground-muted hover:bg-surface-hover"
                  }`}
                >
                  Hard
                </button>
              </div>
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-foreground">Question count</p>
              <p className="mt-1 text-xs text-foreground-muted">
                Backend currently uses its default question count for interviews.
              </p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
