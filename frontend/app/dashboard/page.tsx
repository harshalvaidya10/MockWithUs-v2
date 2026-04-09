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

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
            <p className="text-xs uppercase tracking-wide text-slate-400">Email</p>
            <p className="mt-2 text-sm text-white">{user.email}</p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
            <p className="text-xs uppercase tracking-wide text-slate-400">User ID</p>
            <p className="mt-2 break-all text-sm text-white">{user.id}</p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 md:col-span-2">
            <p className="text-xs uppercase tracking-wide text-slate-400">Account Created</p>
            <p className="mt-2 text-sm text-white">
              {new Date(user.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5">
            <h2 className="text-lg font-semibold text-white">Resume</h2>
            <p className="mt-2 text-sm text-slate-300">
              Upload a PDF or DOCX resume to extract your skills.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                href="/interview/new"
                className="inline-block rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
              >
                Upload Resume
              </Link>
              <Link
                href="/resumes"
                className="inline-block rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                View All
              </Link>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5">
            <h2 className="text-lg font-semibold text-white">Job Descriptions</h2>
            <p className="mt-2 text-sm text-slate-300">
              Paste a job description to extract required skills and keywords.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                href="/jobs/new"
                className="inline-block rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
              >
                Add Job Description
              </Link>
              <Link
                href="/jobs"
                className="inline-block rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                View All
              </Link>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
