"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import { ApiError, apiRequest } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { ResumeUploadResponse } from "@/types";


const ACCEPTED_FILE_TYPES = ".pdf,.docx";

export default function NewInterviewPage(): JSX.Element {
  const { isAuthenticated, isLoading } = useAuth();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<ResumeUploadResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  async function handleUpload(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setUploadResult(null);

    if (!isAuthenticated) {
      setErrorMessage("You need to log in before uploading a resume.");
      return;
    }

    if (!selectedFile) {
      setErrorMessage("Please choose a PDF or DOCX file.");
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await apiRequest<ResumeUploadResponse>("/resumes/upload", {
        method: "POST",
        body: formData,
      });

      setUploadResult(response);
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401) {
          setErrorMessage("You need to log in before uploading a resume.");
        } else {
          setErrorMessage(error.message);
        }
      } else {
        setErrorMessage("Unable to upload resume right now. Please try again.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  if (isLoading) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
          <h1 className="text-3xl font-semibold text-white">Start a new interview</h1>
          <p className="mt-2 text-sm text-slate-300">Checking your session...</p>
        </div>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-5xl rounded-2xl border border-red-900/70 bg-red-950/30 p-8 shadow-xl">
          <h1 className="text-3xl font-semibold text-white">Start a new interview</h1>
          <p className="mt-4 rounded-xl border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-200">
            Resume upload is not allowed without login.
          </p>
          <Link
            href="/login"
            className="mt-5 inline-block rounded-xl bg-white px-5 py-3 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            Go to Login
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
        <h1 className="text-3xl font-semibold text-white">Start a new interview</h1>
        <p className="mt-2 text-sm text-slate-300">
          Upload your resume first. Job description setup will be added in the next phase.
        </p>

        <form onSubmit={handleUpload} className="mt-6 space-y-4">
          <div>
            <label htmlFor="resume" className="mb-2 block text-sm font-medium text-slate-200">
              Resume (PDF or DOCX)
            </label>
            <input
              id="resume"
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              onChange={(event) => {
                setSelectedFile(event.target.files?.[0] ?? null);
                setErrorMessage(null);
                setUploadResult(null);
              }}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-900 hover:file:bg-white"
            />
          </div>

          {selectedFile ? (
            <p className="text-sm text-slate-300">Selected file: {selectedFile.name}</p>
          ) : null}

          {errorMessage ? (
            <div className="rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {errorMessage}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isUploading}
            className="rounded-xl bg-white px-5 py-3 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isUploading ? "Uploading..." : "Upload Resume"}
          </button>
        </form>

        {uploadResult ? (
          <section className="mt-8 rounded-2xl border border-emerald-900/70 bg-emerald-950/30 p-5">
            <h2 className="text-lg font-semibold text-emerald-200">Resume uploaded</h2>
            <p className="mt-2 text-sm text-emerald-100">
              Filename: <span className="font-medium">{uploadResult.filename}</span>
            </p>
            <p className="mt-1 text-sm text-emerald-100">
              Uploaded at: {new Date(uploadResult.created_at).toLocaleString()}
            </p>

            <div className="mt-4">
              <p className="text-sm font-medium text-emerald-100">Extracted skills</p>
              {uploadResult.skills.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {uploadResult.skills.map((skill) => (
                    <span
                      key={skill}
                      className="rounded-full border border-emerald-800 bg-emerald-900/50 px-3 py-1 text-xs text-emerald-100"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-emerald-100">No skills were detected.</p>
              )}
            </div>
          </section>
        ) : null}

        <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-950/40 p-5">
          <h2 className="text-lg font-semibold text-white">Job Description (Coming Next)</h2>
          <p className="mt-2 text-sm text-slate-300">
            This section is intentionally left as a placeholder for the upcoming interview setup steps.
          </p>
        </section>
      </div>
    </main>
  );
}
