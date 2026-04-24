"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest, ApiError } from "@/lib/api";
import { setAccessToken } from "@/lib/auth";

interface SignupResponse {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
}

export default function SignupPage(): JSX.Element {
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await apiRequest<SignupResponse>("/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName.trim() || null,
          email,
          password,
        }),
      });

      const loginResponse = await apiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
        }),
      });

      setAccessToken(loginResponse.access_token);
      router.push("/home");
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
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sign Up</h1>
        <p className="mt-2 text-sm text-foreground-muted">
          Create your account to start mock interview practice.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="fullName" className="mb-1.5 block text-sm font-medium text-foreground">
              Full Name
            </label>
            <input
              id="fullName"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="app-input"
              placeholder="Harshal Vaidya"
            />
          </div>

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
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="app-input"
              placeholder="Minimum 8 characters"
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
            {isSubmitting ? "Creating account..." : "Create Account"}
          </button>
        </form>

        <p className="mt-6 text-sm text-foreground-muted">
          Already have an account?{" "}
          <a href="/login" className="font-medium text-foreground underline underline-offset-4">
            Login
          </a>
        </p>
      </div>
    </main>
  );
}
