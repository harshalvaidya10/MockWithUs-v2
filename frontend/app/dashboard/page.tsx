"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";

export default function DashboardPage(): JSX.Element {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  function handleLogout(): void {
    logout();
    router.push("/login");
  }

  if (isLoading) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
          <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
          <p className="mt-2 text-sm text-slate-300">Loading your account...</p>
        </div>
      </main>
    );
  }

  if (!isAuthenticated || !user) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
          <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
          <p className="mt-2 text-sm text-slate-300">Redirecting to login...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
            <p className="mt-2 text-sm text-slate-300">
              Welcome back{user.full_name ? `, ${user.full_name}` : ""}.
            </p>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            Logout
          </button>
        </div>

        <p className="mt-8 text-sm text-slate-300">
          Follow this flow to start an interview: Resume → Job Description → Resume–JD Matching.
        </p>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <Link
            href="/dashboard/resumes"
            className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5 transition hover:border-slate-600 hover:bg-slate-900"
          >
            <h2 className="text-lg font-semibold text-white">Resume</h2>
            <p className="mt-2 text-sm text-slate-300">
              Upload your resume and review previously uploaded files.
            </p>
          </Link>

          <Link
            href="/dashboard/jobs"
            className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5 transition hover:border-slate-600 hover:bg-slate-900"
          >
            <h2 className="text-lg font-semibold text-white">Job Description</h2>
            <p className="mt-2 text-sm text-slate-300">
              Save your target job description and review detected skills.
            </p>
          </Link>

          <Link
            href="/dashboard/matching"
            className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5 transition hover:border-slate-600 hover:bg-slate-900"
          >
            <h2 className="text-lg font-semibold text-white">Resume–JD Matching</h2>
            <p className="mt-2 text-sm text-slate-300">
              Run matching, review fit score, and start the interview session.
            </p>
          </Link>
        </div>
      </div>
    </main>
  );
}
