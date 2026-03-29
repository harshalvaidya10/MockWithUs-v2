interface InterviewPageProps {
  params: {
    sessionId: string;
  };
}

export default function InterviewSessionPage({ params }: InterviewPageProps): JSX.Element {
  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
        <h1 className="text-3xl font-semibold">Interview session</h1>
        <p className="mt-2 text-sm text-slate-300">Placeholder route for session {params.sessionId}.</p>
      </div>
    </main>
  );
}
