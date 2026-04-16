import { getAccessToken, clearAccessToken } from "@/lib/auth";
import type { InterviewHistoryResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();

  const headers = new Headers(init?.headers);

  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

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

export async function getInterviewHistory(): Promise<InterviewHistoryResponse> {
  return apiRequest<InterviewHistoryResponse>("/interviews");
}
