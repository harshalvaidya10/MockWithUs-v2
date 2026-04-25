import type { ResumeUploadResponse } from "@/types";

interface ResumeCardProps {
  resume: ResumeUploadResponse;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function ResumeCard({ resume, selected, onSelect }: ResumeCardProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onSelect(resume.id)}
      className={`w-full rounded-xl border p-4 text-left transition-all duration-200 ease-out ${
        selected
          ? "border-primary bg-primary-subtle"
          : "border-border bg-surface hover:border-border-strong hover:bg-surface-hover"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm font-medium text-foreground">{resume.filename}</p>
        {selected ? (
          <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] text-primary-foreground">
            Active
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-xs text-foreground-muted">Uploaded {new Date(resume.created_at).toLocaleString()}</p>
    </button>
  );
}
