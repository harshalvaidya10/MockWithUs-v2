"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest, ApiError } from "@/lib/api";
import { setAccessToken } from "@/lib/auth";

interface LoginResponse {
  access_token: string;
  token_type: string;
}

export default function LoginPage(): JSX.Element {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function getSafeRedirectPath(): string {
    if (typeof window === "undefined") {
      return "/home";
    }

    const nextPath = new URLSearchParams(window.location.search).get("next");
    if (!nextPath) {
      return "/home";
    }

    // Prevent external/open redirects; allow only app-internal absolute paths.
    if (!nextPath.startsWith("/") || nextPath.startsWith("//")) {
      return "/home";
    }

    return nextPath;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      const response = await apiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
        }),
      });

      setAccessToken(response.access_token);
      router.push(getSafeRedirectPath());
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Something went wrong. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface p-8 shadow-[0_4px_12px_rgba(0,0,0,0.04)]">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Login</h1>
        <p className="mt-2 text-sm text-foreground-muted">
          Sign in to continue your interview preparation.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-foreground">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="app-input"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-foreground">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="app-input"
              placeholder="Enter your password"
            />
          </div>

          {errorMessage ? (
            <div className="rounded-xl border border-danger bg-danger-subtle px-4 py-3 text-sm text-danger">
              {errorMessage}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex h-10 w-full items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors duration-150 hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="mt-6 text-sm text-foreground-muted">
          Don&apos;t have an account?{" "}
          <a href="/signup" className="font-medium text-foreground underline underline-offset-4">
            Sign up
          </a>
        </p>
      </div>
    </main>
  );
}
