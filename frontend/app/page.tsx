export default function HomePage(): JSX.Element {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900 px-6 py-16 text-white">
      <div className="mx-auto flex max-w-4xl flex-col gap-8">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-2xl">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-sky-400">MockWithUs</p>
          <h1 className="mt-4 text-4xl font-bold tracking-tight">AI Interview Copilot is running.</h1>
          <p className="mt-4 max-w-2xl text-base text-slate-300">
            This placeholder confirms the Next.js 14 App Router, TypeScript, and Tailwind setup is wired and ready
            for feature work.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
            <h2 className="text-lg font-semibold">Frontend stack</h2>
            <p className="mt-2 text-sm text-slate-300">Next.js 14 · TypeScript · Tailwind CSS</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
            <h2 className="text-lg font-semibold">Backend check</h2>
            <p className="mt-2 text-sm text-slate-300">Verify the API at <code>/health</code> on port 8000.</p>
          </div>
        </div>
      </div>
    </main>
  );
}
