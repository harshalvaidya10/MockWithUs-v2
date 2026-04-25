import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description: string;
  ctaLabel?: string;
  ctaHref?: string;
  onCtaClick?: () => void;
  icon?: LucideIcon;
}

export function EmptyState({
  title,
  description,
  ctaLabel,
  ctaHref,
  onCtaClick,
  icon: Icon = Inbox,
}: EmptyStateProps): JSX.Element {
  return (
    <div className="rounded-xl border border-border bg-surface p-6 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface-hover">
        <Icon className="h-6 w-6 text-foreground-subtle" />
      </div>
      <p className="mt-4 text-base font-semibold tracking-tight text-foreground">{title}</p>
      <p className="mx-auto mt-1 max-w-xl text-sm leading-relaxed text-foreground-muted">{description}</p>
      {ctaLabel ? (
        <div className="mt-5">
          {ctaHref ? (
            <Link
              href={ctaHref}
              className="app-btn-primary"
            >
              {ctaLabel}
            </Link>
          ) : (
            <button
              type="button"
              onClick={onCtaClick}
              className="app-btn-primary"
            >
              {ctaLabel}
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}
