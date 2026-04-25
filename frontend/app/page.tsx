import Image from "next/image";
import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const AUTH_COOKIE_NAME = "mockwithus_access_token";

export default function HomePage(): JSX.Element {
  const token = cookies().get(AUTH_COOKIE_NAME)?.value;
  if (token) {
    redirect("/home");
  }

  return (
    <main className="min-h-screen bg-background px-6 text-foreground">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl items-center justify-center">
        <section className="w-full max-w-2xl rounded-xl border border-border bg-surface p-10 text-center shadow-[0_4px_12px_rgba(0,0,0,0.04)]">
          <div className="flex justify-center">
            <Image
              src="/brand/logo-wordmark.svg"
              alt="MockWithUs"
              width={340}
              height={88}
              className="h-12 w-auto"
              priority
            />
          </div>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight md:text-5xl">
            Practice Interviews With Confidence
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-foreground-muted">
            Upload your resume, match it to your target role, and prepare with focused interview practice.
          </p>

          <div className="mt-8">
            <Link
              href="/login"
              className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-6 text-sm font-semibold text-primary-foreground transition-colors duration-150 hover:bg-primary-hover"
            >
              Get Started
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
