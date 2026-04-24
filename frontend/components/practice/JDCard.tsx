import type { JobOut } from "@/types";

interface JDCardProps {
  job: JobOut;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function JDCard({ job, selected, onSelect }: JDCardProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onSelect(job.id)}
      className={`w-full rounded-xl border p-4 text-left transition-all duration-200 ease-out ${
        selected
          ? "border-primary bg-primary-subtle"
          : "border-border bg-surface hover:border-border-strong hover:bg-surface-hover"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm font-medium text-foreground">{job.title ?? "Untitled job"}</p>
        {selected ? (
          <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] text-primary-foreground">
            Active
          </span>
        ) : null}
      </div>
      <p className="mt-1 text-xs text-foreground-muted">{job.company ?? "Company not specified"}</p>
      <p className="mt-1 text-xs text-foreground-subtle">Saved {new Date(job.created_at).toLocaleString()}</p>
    </button>
  );
}
