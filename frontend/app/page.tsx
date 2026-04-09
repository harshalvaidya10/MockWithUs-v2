import Link from "next/link";

export default function HomePage(): JSX.Element {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900 px-6 text-white">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl items-center justify-center">
        <section className="w-full max-w-2xl rounded-3xl border border-slate-800 bg-slate-900/70 p-10 text-center shadow-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-400">MockWithUs</p>
          <h1 className="mt-4 text-4xl font-bold tracking-tight md:text-5xl">
            Practice Interviews With Confidence
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base text-slate-300">
            Upload your resume, match it to your target role, and prepare with focused interview practice.
          </p>

          <div className="mt-8">
            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-xl bg-white px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-200"
            >
              Get Started
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
