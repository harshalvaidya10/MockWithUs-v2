import Link from "next/link";

interface ResultsPageProps {
  params: {
    sessionId: string;
  };
}

export default function ResultsPage({ params }: ResultsPageProps): JSX.Element {
  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
        <h1 className="text-3xl font-semibold text-white">Interview Results</h1>
        <p className="mt-2 text-sm text-slate-300">
          Session <span className="font-mono">{params.sessionId}</span> has been saved.
        </p>
        <p className="mt-1 text-sm text-slate-300">
          You can find this interview under <strong>Previous Interviews</strong> on the dashboard.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/dashboard"
            className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            Back to Dashboard
          </Link>
          <Link
            href={`/interview/${params.sessionId}`}
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            Review Questions
          </Link>
        </div>
      </div>
    </main>
  );
}
