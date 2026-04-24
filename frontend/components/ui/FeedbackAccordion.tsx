import { useState } from "react";
import type { ReactNode } from "react";

interface FeedbackAccordionProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export function FeedbackAccordion({
  title,
  subtitle,
  children,
  defaultOpen = false,
}: FeedbackAccordionProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <article className="rounded-xl border border-border bg-surface">
      <button
        type="button"
        onClick={() => setIsOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <p className="text-sm font-semibold text-foreground">{title}</p>
          {subtitle ? <p className="mt-0.5 text-xs text-foreground-muted">{subtitle}</p> : null}
        </div>
        <span className="text-xs text-foreground-muted">{isOpen ? "Hide" : "Show"}</span>
      </button>
      {isOpen ? <div className="border-t border-border px-4 py-4">{children}</div> : null}
    </article>
  );
}
