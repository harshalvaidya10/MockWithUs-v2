"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { LongRunningLoader } from "@/components/ui/LongRunningLoader";
import { useCodingSession } from "@/hooks/useCodingSession";
import type { CodingLanguage, TestCase, TestResult } from "@/types";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const LANGUAGE_OPTIONS: Array<{ value: CodingLanguage; label: string; monacoLanguage: string }> = [
  { value: "python", label: "Python 3", monacoLanguage: "python" },
  { value: "javascript", label: "JavaScript", monacoLanguage: "javascript" },
  { value: "java", label: "Java", monacoLanguage: "java" },
  { value: "cpp", label: "C++", monacoLanguage: "cpp" },
];

function formatElapsedTime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function difficultyBadgeClass(difficulty: string): string {
  if (difficulty.toLowerCase() === "hard") {
    return "border border-danger bg-danger-subtle text-danger";
  }
  return "border border-warning bg-warning-subtle text-warning";
}

function statusClass(result: TestResult | undefined): string {
  if (!result) return "border-border bg-surface-hover";
  if (result.passed) return "border-success bg-success-subtle";
  return "border-danger bg-danger-subtle";
}

function safeCodeBlock(value: string | null | undefined): string {
  if (value === null || value === undefined || value.length === 0) return "∅";
  return value;
}

function tryParseJson(value: string): { ok: true; value: unknown } | { ok: false } {
  try {
    return { ok: true, value: JSON.parse(value) };
  } catch {
    return { ok: false };
  }
}

function formatStructuredValue(value: string | null | undefined): string {
  const rawValue = safeCodeBlock(value);
  if (rawValue === "∅") return rawValue;

  const parsed = tryParseJson(rawValue.trim());
  if (!parsed.ok) return rawValue;
  if (typeof parsed.value === "string") return parsed.value;
  return JSON.stringify(parsed.value, null, 2);
}

function buildOutputLog(results: TestResult[] | null): string {
  if (!results || results.length === 0) {
    return "Run tests to view stdout and stderr output.";
  }
  return results
    .map((result, index) => {
      const stdout = formatStructuredValue(result.actual_output);
      const stderr = formatStructuredValue(result.error_output);
      return [`Test ${index + 1} (${result.status})`, `stdout: ${stdout}`, `stderr: ${stderr}`].join("\n");
    })
    .join("\n\n");
}

function formatFunctionSignature(
  signature: { name?: string; params?: string; return_type?: string } | undefined,
): string {
  if (!signature) return "solve(...)";
  const name = signature.name?.trim() || "solve";
  const params = signature.params?.trim() || "";
  const returnType = signature.return_type?.trim() || "";
  if (!returnType) {
    return `${name}(${params})`;
  }
  return `${name}(${params}) -> ${returnType}`;
}

export default function CodingSessionPage(): JSX.Element {
  const router = useRouter();
  const params = useParams<{ sessionId?: string | string[] }>();
  const sessionIdParam = params?.sessionId;
  const sessionId = Array.isArray(sessionIdParam) ? sessionIdParam[0] : sessionIdParam;

  const { state, actions } = useCodingSession(sessionId);
  const [activeTab, setActiveTab] = useState<"tests" | "output">("tests");
  const [confirmState, setConfirmState] = useState<
    | null
    | { type: "switch-language"; nextLanguage: CodingLanguage }
    | { type: "submit" }
    | { type: "exit" }
  >(null);

  const selectedLanguageOption =
    LANGUAGE_OPTIONS.find((option) => option.value === state.language) ?? LANGUAGE_OPTIONS[0];
  const selectedLanguageSignature = state.problem?.function_signature?.[state.language] as
    | { name?: string; params?: string; return_type?: string }
    | undefined;

  const resultByTestCaseId = useMemo(() => {
    const index: Record<string, TestResult> = {};
    for (const result of state.runResults ?? []) {
      index[result.test_case_id] = result;
    }
    return index;
  }, [state.runResults]);

  const outputLog = useMemo(() => buildOutputLog(state.runResults), [state.runResults]);

  function handleLanguageChange(nextLanguage: CodingLanguage): void {
    if (!state.problem || nextLanguage === state.language) {
      actions.setLanguage(nextLanguage);
      return;
    }

    const currentStarterCode = String(state.problem.starter_code[state.language] ?? "");
    const currentCode = state.code[state.language] ?? "";
    const isUntouched = currentCode.trim() === currentStarterCode.trim();

    if (!isUntouched) {
      setConfirmState({ type: "switch-language", nextLanguage });
      return;
    }

    actions.setLanguage(nextLanguage);
    actions.resetRunResults();
  }

  async function handleRunTests(): Promise<void> {
    setActiveTab("tests");
    try {
      await actions.runTests();
    } catch {
      // Error surfaces in state.errorMessage.
    }
  }

  async function submitSolutionNow(): Promise<void> {
    try {
      await actions.submitSolution();
      router.push(`/coding/${sessionId}/results`);
    } catch {
      toast.error("Could not submit solution.");
    }
  }

  function handleExitRound(): void {
    router.push("/home");
  }

  if (state.isLoading) {
    return (
      <main className="min-h-screen bg-background px-6 py-12">
        <div className="mx-auto max-w-6xl rounded-2xl border border-border bg-surface p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Coding round</h1>
          <p className="mt-2 text-sm text-foreground-muted">Loading coding session...</p>
        </div>
      </main>
    );
  }

  if (state.errorMessage || !state.problem || !sessionId) {
    return (
      <main className="min-h-screen bg-background px-6 py-12">
        <div className="mx-auto max-w-6xl rounded-2xl border border-border bg-surface p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Coding round</h1>
          <p className="mt-3 text-sm text-danger">{state.errorMessage ?? "Session data is unavailable."}</p>
          <div className="mt-4">
            <Link href="/practice" className="app-btn-secondary">
              Back to Practice
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background px-4 py-6 md:px-6">
      <div className="mx-auto max-w-[1400px] space-y-4">
        <header className="rounded-2xl border border-border bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Image
                src="/brand/logo-wordmark.svg"
                alt="MockWithUs"
                width={170}
                height={44}
                className="h-6 w-auto"
                priority
              />
              <span className="rounded-full border border-border px-2 py-1 text-xs text-foreground-muted">
                Coding round
              </span>
              <span className={`rounded-full px-2 py-1 text-xs ${difficultyBadgeClass(state.problem.difficulty)}`}>
                {state.problem.difficulty}
              </span>
              {state.problem.category ? (
                <span className="rounded-full border border-primary bg-primary-subtle px-2 py-1 text-xs text-primary">
                  {state.problem.category}
                </span>
              ) : null}
            </div>
            <div className="flex items-center gap-3">
              <p className="font-mono text-sm text-foreground">Timer: {formatElapsedTime(state.elapsedSeconds)}</p>
              <button
                type="button"
                onClick={() => setConfirmState({ type: "exit" })}
                className="inline-flex h-8 items-center justify-center rounded-lg border border-danger px-3 text-xs font-medium text-danger transition-colors duration-150 hover:bg-danger-subtle"
              >
                Exit
              </button>
            </div>
          </div>
        </header>

        {state.errorMessage ? (
          <div className="rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
            {state.errorMessage}
          </div>
        ) : null}

        <section className="grid gap-4 xl:grid-cols-2">
          <article className="min-h-[520px] rounded-2xl border border-border bg-surface p-5">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">{state.problem.title}</h1>
            <p className="mt-2 text-sm text-foreground-muted">Based on your selected role and job description context.</p>

            <div className="mt-5 space-y-5 overflow-y-auto pr-1 xl:max-h-[620px]">
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-foreground-muted">Problem</h2>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">{state.problem.description}</p>
              </section>

              {state.problem.constraints ? (
                <section>
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-foreground-muted">Constraints</h2>
                  <pre className="mt-2 whitespace-pre-wrap rounded-xl border border-border bg-surface-hover p-3 text-xs text-foreground">
                    {state.problem.constraints}
                  </pre>
                </section>
              ) : null}

              <section>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-foreground-muted">Function signature</h2>
                <pre className="mt-2 overflow-x-auto rounded-xl border border-border bg-surface-hover p-3 text-xs text-foreground">
                  {formatFunctionSignature(selectedLanguageSignature)}
                </pre>
              </section>

              {state.sampleTestCases.length > 0 ? (
                <section className="space-y-3">
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-foreground-muted">Examples</h2>
                  {state.sampleTestCases.map((testCase, index) => (
                    <div key={testCase.id} className="rounded-xl border border-border bg-surface-hover p-3">
                      <p className="text-xs font-medium text-foreground-muted">Example {index + 1}</p>
                      <p className="mt-2 text-xs uppercase tracking-wide text-foreground-subtle">Input</p>
                      <pre className="mt-1 rounded-lg bg-surface p-2 text-xs text-foreground whitespace-pre-wrap break-words">
                        {formatStructuredValue(testCase.input_data)}
                      </pre>
                      <p className="mt-2 text-xs uppercase tracking-wide text-foreground-subtle">Output</p>
                      <pre className="mt-1 rounded-lg bg-surface p-2 text-xs text-foreground whitespace-pre-wrap break-words">
                        {formatStructuredValue(testCase.expected_output)}
                      </pre>
                    </div>
                  ))}
                </section>
              ) : null}
            </div>
          </article>

          <article className="flex min-h-[520px] flex-col rounded-2xl border border-border bg-surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label htmlFor="language-select" className="text-xs font-medium uppercase tracking-wide text-foreground-muted">
                Language
              </label>
              <select
                id="language-select"
                value={state.language}
                onChange={(event) => handleLanguageChange(event.target.value as CodingLanguage)}
                className="app-input max-w-[180px]"
              >
                {LANGUAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-4 flex-1 overflow-hidden rounded-xl border border-border">
              <MonacoEditor
                height="100%"
                language={selectedLanguageOption.monacoLanguage}
                theme="vs"
                value={state.code[state.language]}
                onChange={(value) => {
                  actions.setCodeForLanguage(state.language, value ?? "");
                }}
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  automaticLayout: true,
                  wordWrap: "on",
                }}
              />
            </div>
          </article>
        </section>

        <section className="rounded-2xl border border-border bg-surface p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setActiveTab("tests")}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                  activeTab === "tests"
                    ? "border-primary bg-primary-subtle text-primary"
                    : "border-border text-foreground-muted hover:bg-surface-hover"
                }`}
              >
                Test cases
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("output")}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                  activeTab === "output"
                    ? "border-primary bg-primary-subtle text-primary"
                    : "border-border text-foreground-muted hover:bg-surface-hover"
                }`}
              >
                Output
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  void handleRunTests();
                }}
                disabled={state.isRunning || state.isSubmitting}
                className="app-btn-secondary"
              >
                {state.isRunning ? "Running..." : "Run tests"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmState({ type: "submit" });
                }}
                disabled={state.isRunning || state.isSubmitting}
                className="app-btn-primary"
              >
                {state.isSubmitting ? "Submitting..." : "Submit solution"}
              </button>
            </div>
          </div>

          {activeTab === "tests" ? (
            <div className="mt-4 space-y-3">
              {state.sampleTestCases.map((testCase: TestCase, index) => {
                const result = resultByTestCaseId[testCase.id];
                return (
                  <article key={testCase.id} className={`rounded-xl border p-3 ${statusClass(result)}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium text-foreground">
                        TC {index + 1} {result ? (result.passed ? "✓" : "✗") : ""}
                      </p>
                      {result?.runtime_ms !== null && result?.runtime_ms !== undefined ? (
                        <p className="text-xs text-foreground-muted">{result.runtime_ms} ms</p>
                      ) : null}
                    </div>

                    <div className="mt-2 grid gap-2 md:grid-cols-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Input</p>
                        <pre className="mt-1 rounded-lg bg-surface p-2 text-xs text-foreground whitespace-pre-wrap break-words">
                          {formatStructuredValue(testCase.input_data)}
                        </pre>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Expected</p>
                        <pre className="mt-1 rounded-lg bg-surface p-2 text-xs text-foreground whitespace-pre-wrap break-words">
                          {formatStructuredValue(testCase.expected_output)}
                        </pre>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Actual</p>
                        <pre className="mt-1 rounded-lg bg-surface p-2 text-xs text-foreground whitespace-pre-wrap break-words">
                          {formatStructuredValue(result?.actual_output)}
                        </pre>
                      </div>
                    </div>

                    {result?.error_output ? <p className="mt-2 text-xs text-danger">Error: {result.error_output}</p> : null}
                  </article>
                );
              })}
            </div>
          ) : (
            <pre className="mt-4 max-h-[320px] overflow-auto rounded-xl border border-border bg-surface-hover p-3 text-xs text-foreground">
              {outputLog}
            </pre>
          )}
        </section>
      </div>

      {state.isSubmitting ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 px-6">
          <LongRunningLoader
            title="Evaluating your submission..."
            phrases={["Running hidden test cases...", "Scoring correctness...", "Generating AI feedback..."]}
            className="w-full max-w-md"
          />
        </div>
      ) : null}

      <ConfirmDialog
        open={Boolean(confirmState)}
        title={
          confirmState?.type === "switch-language"
            ? "Switch language?"
            : confirmState?.type === "submit"
              ? "Submit this solution?"
              : "Exit coding round?"
        }
        description={
          confirmState?.type === "switch-language"
            ? "Switching language may replace your in-progress code."
            : confirmState?.type === "submit"
              ? "This will run your solution against all test cases."
              : "Your current code is saved locally for this session."
        }
        confirmLabel={
          confirmState?.type === "switch-language"
            ? "Switch"
            : confirmState?.type === "submit"
              ? "Submit"
              : "Exit"
        }
        cancelLabel="Cancel"
        onCancel={() => setConfirmState(null)}
        onConfirm={() => {
          const current = confirmState;
          setConfirmState(null);
          if (!current) return;
          if (current.type === "switch-language") {
            actions.setLanguage(current.nextLanguage);
            actions.resetRunResults();
            return;
          }
          if (current.type === "submit") {
            void submitSolutionNow();
            return;
          }
          handleExitRound();
        }}
      />
    </main>
  );
}
