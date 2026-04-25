"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, getCodingProblem, runCode, submitCode } from "@/lib/api";
import type {
  CodeSubmitResponse,
  CodingLanguage,
  CodingProblem,
  TestCase,
  TestResult,
} from "@/types";

const SUPPORTED_LANGUAGES: CodingLanguage[] = ["python", "javascript", "java", "cpp"];

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

function storageKey(sessionId: string, language: CodingLanguage): string {
  return `coding_${sessionId}_${language}`;
}

function clearSessionStorage(sessionId: string): void {
  if (typeof window === "undefined") return;
  for (const language of SUPPORTED_LANGUAGES) {
    window.localStorage.removeItem(storageKey(sessionId, language));
  }
}

function fallbackStarterCode(
  language: CodingLanguage,
  signature: { name?: string; params?: string } | undefined,
): string {
  const functionName = (signature?.name ?? "solve").trim() || "solve";
  const params = (signature?.params ?? "").trim();

  if (language === "python") {
    const signatureLine = params ? `def ${functionName}(${params}):` : `def ${functionName}():`;
    return `${signatureLine}\n    # Write your solution here\n    return None\n`;
  }
  if (language === "javascript") {
    const signatureLine = params ? `function ${functionName}(${params}) {` : `function ${functionName}() {`;
    return `${signatureLine}\n  // Write your solution here\n  return null;\n}\n`;
  }
  if (language === "java") {
    return (
      "import java.util.*;\n\n" +
      "public class Main {\n" +
      `    public static Object ${functionName}(${params}) {\n` +
      "        // Write your solution here\n" +
      "        return null;\n" +
      "    }\n" +
      "}\n"
    );
  }
  return (
    "#include <bits/stdc++.h>\n" +
    "using namespace std;\n\n" +
    `auto ${signature?.name ?? "solve"}(${params}) {\n` +
    "    // Write your solution here\n" +
    "    return 0;\n" +
    "}\n"
  );
}

export interface CodingSessionState {
  problem: CodingProblem | null;
  sampleTestCases: TestCase[];
  language: CodingLanguage;
  code: Record<CodingLanguage, string>;
  isLoading: boolean;
  isRunning: boolean;
  isSubmitting: boolean;
  runResults: TestResult[] | null;
  elapsedSeconds: number;
  errorMessage: string | null;
}

export interface CodingSessionActions {
  setLanguage: (language: CodingLanguage) => void;
  setCodeForLanguage: (language: CodingLanguage, value: string) => void;
  runTests: () => Promise<void>;
  submitSolution: () => Promise<CodeSubmitResponse>;
  resetRunResults: () => void;
}

export function useCodingSession(sessionId: string | undefined): {
  state: CodingSessionState;
  actions: CodingSessionActions;
} {
  const [problem, setProblem] = useState<CodingProblem | null>(null);
  const [sampleTestCases, setSampleTestCases] = useState<TestCase[]>([]);
  const [language, setLanguage] = useState<CodingLanguage>("python");
  const [code, setCode] = useState<Record<CodingLanguage, string>>({
    python: "",
    javascript: "",
    java: "",
    cpp: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [runResults, setRunResults] = useState<TestResult[] | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setIsLoading(false);
      setErrorMessage("Invalid coding session URL.");
      return;
    }

    let isCancelled = false;
    setIsLoading(true);
    setErrorMessage(null);
    setRunResults(null);
    setElapsedSeconds(0);

    void getCodingProblem(sessionId)
      .then((response) => {
        if (isCancelled) return;

        setProblem(response.problem);
        setSampleTestCases(response.sample_test_cases);

        const signatures = response.problem.function_signature as Record<
          string,
          { name?: string; params?: string }
        >;
        const nextCode: Record<CodingLanguage, string> = {
          python:
            String(response.problem.starter_code.python ?? "").trim() ||
            fallbackStarterCode("python", signatures.python),
          javascript:
            String(response.problem.starter_code.javascript ?? "").trim() ||
            fallbackStarterCode("javascript", signatures.javascript),
          java:
            String(response.problem.starter_code.java ?? "").trim() ||
            fallbackStarterCode("java", signatures.java),
          cpp:
            String(response.problem.starter_code.cpp ?? "").trim() ||
            fallbackStarterCode("cpp", signatures.cpp),
        };

        if (typeof window !== "undefined") {
          for (const supportedLanguage of SUPPORTED_LANGUAGES) {
            const savedCode = window.localStorage.getItem(storageKey(sessionId, supportedLanguage));
            if (savedCode !== null && savedCode.trim().length > 0) {
              nextCode[supportedLanguage] = savedCode;
            }
          }
        }

        setCode(nextCode);
      })
      .catch((error: unknown) => {
        if (isCancelled) return;
        setErrorMessage(getApiErrorMessage(error, "Could not load coding problem."));
      })
      .finally(() => {
        if (isCancelled) return;
        setIsLoading(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setElapsedSeconds((currentValue) => currentValue + 1);
    }, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    if (!sessionId || typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(storageKey(sessionId, language), code[language] ?? "");
  }, [code, language, sessionId]);

  const setCodeForLanguage = useCallback((targetLanguage: CodingLanguage, value: string): void => {
    setCode((currentCode) => ({
      ...currentCode,
      [targetLanguage]: value,
    }));
  }, []);

  const runTests = useCallback(async (): Promise<void> => {
    if (!sessionId || !problem) {
      throw new Error("Coding session is not initialized.");
    }

    setErrorMessage(null);
    setIsRunning(true);
    try {
      const response = await runCode(sessionId, problem.id, language, code[language] ?? "");
      setRunResults(response.results);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error, "Could not run tests."));
      throw error;
    } finally {
      setIsRunning(false);
    }
  }, [code, language, problem, sessionId]);

  const submitSolution = useCallback(async (): Promise<CodeSubmitResponse> => {
    if (!sessionId || !problem) {
      throw new Error("Coding session is not initialized.");
    }

    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      const response = await submitCode(sessionId, problem.id, language, code[language] ?? "");
      clearSessionStorage(sessionId);
      return response;
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error, "Could not submit solution."));
      throw error;
    } finally {
      setIsSubmitting(false);
    }
  }, [code, language, problem, sessionId]);

  const resetRunResults = useCallback((): void => {
    setRunResults(null);
  }, []);

  const state = useMemo<CodingSessionState>(
    () => ({
      problem,
      sampleTestCases,
      language,
      code,
      isLoading,
      isRunning,
      isSubmitting,
      runResults,
      elapsedSeconds,
      errorMessage,
    }),
    [
      code,
      elapsedSeconds,
      errorMessage,
      isLoading,
      isRunning,
      isSubmitting,
      language,
      problem,
      runResults,
      sampleTestCases,
    ],
  );

  const actions = useMemo<CodingSessionActions>(
    () => ({
      setLanguage,
      setCodeForLanguage,
      runTests,
      submitSolution,
      resetRunResults,
    }),
    [resetRunResults, runTests, setCodeForLanguage, submitSolution],
  );

  return { state, actions };
}
