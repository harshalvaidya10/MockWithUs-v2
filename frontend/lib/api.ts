import { getAccessToken, clearAccessToken } from "@/lib/auth";
import type {
  CodeRunResponse,
  CodeSubmitResponse,
  CodingDifficulty,
  CodingLanguage,
  CodingProblemResponse,
  CodingSessionResponse,
  InterviewHistoryResponse,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function buildRequestHeaders(init?: RequestInit): Headers {
  const token = getAccessToken();
  const headers = new Headers(init?.headers);

  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return headers;
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = buildRequestHeaders(init);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;

    try {
      const errorData = (await response.json()) as { detail?: string };
      if (errorData?.detail) {
        message = errorData.detail;
      }
    } catch {
      // Ignore JSON parse errors and keep fallback message.
    }

    if (response.status === 401) {
      clearAccessToken();
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const rawBody = await response.text();
  if (!rawBody.trim()) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const mediaType = contentType.split(";")[0].trim().toLowerCase();
  const isJsonResponse = mediaType === "application/json" || mediaType.endsWith("+json");

  if (!isJsonResponse) {
    return rawBody as T;
  }

  try {
    return JSON.parse(rawBody) as T;
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new ApiError(
        `Failed to parse JSON response (status ${response.status}). Raw body: ${rawBody}`,
        response.status,
      );
    }
    throw error;
  }
}

export interface ApiBlobResponse {
  blob: Blob;
  contentType: string;
  contentDisposition: string;
}

export async function apiRequestBlob(path: string, init?: RequestInit): Promise<ApiBlobResponse> {
  const headers = buildRequestHeaders(init);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;

    try {
      const errorData = (await response.json()) as { detail?: string };
      if (errorData?.detail) {
        message = errorData.detail;
      }
    } catch {
      // Ignore JSON parse errors and keep fallback message.
    }

    if (response.status === 401) {
      clearAccessToken();
    }

    throw new ApiError(message, response.status);
  }

  return {
    blob: await response.blob(),
    contentType: response.headers.get("content-type") ?? "",
    contentDisposition: response.headers.get("content-disposition") ?? "",
  };
}

export async function getInterviewHistory(): Promise<InterviewHistoryResponse> {
  return apiRequest<InterviewHistoryResponse>("/interviews");
}

export async function deleteInterviewSession(sessionId: string): Promise<void> {
  return apiRequest<void>(`/interviews/${sessionId}`, {
    method: "DELETE",
  });
}

export async function startCodingSession(
  resumeId: string,
  jobId: string,
  difficulty: CodingDifficulty,
  signal?: AbortSignal,
): Promise<CodingSessionResponse> {
  return apiRequest<CodingSessionResponse>("/coding/start", {
    method: "POST",
    signal,
    body: JSON.stringify({
      resume_id: resumeId,
      job_id: jobId,
      difficulty,
    }),
  });
}

export async function getCodingProblem(sessionId: string): Promise<CodingProblemResponse> {
  return apiRequest<CodingProblemResponse>(`/coding/${sessionId}/problem`);
}

export async function runCode(
  sessionId: string,
  problemId: string,
  language: CodingLanguage,
  sourceCode: string,
): Promise<CodeRunResponse> {
  return apiRequest<CodeRunResponse>("/coding/run", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      problem_id: problemId,
      language,
      source_code: sourceCode,
    }),
  });
}

export async function submitCode(
  sessionId: string,
  problemId: string,
  language: CodingLanguage,
  sourceCode: string,
): Promise<CodeSubmitResponse> {
  return apiRequest<CodeSubmitResponse>("/coding/submit", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      problem_id: problemId,
      language,
      source_code: sourceCode,
    }),
  });
}

export async function getCodingResults(sessionId: string): Promise<CodeSubmitResponse> {
  return apiRequest<CodeSubmitResponse>(`/coding/${sessionId}/results`);
}
