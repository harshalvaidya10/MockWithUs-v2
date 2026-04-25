import { useState } from "react";

import { JDCard } from "@/components/practice/JDCard";
import { JDInput } from "@/components/practice/JDInput";
import { EmptyState } from "@/components/ui/EmptyState";
import type { JobOut } from "@/types";

interface JDPickerProps {
  jobs: JobOut[];
  selectedJobId: string;
  isSaving: boolean;
  onSelectJob: (id: string) => void;
  onCreateJob: (value: { title: string; company: string; content: string }) => Promise<void>;
}

export function JDPicker({
  jobs,
  selectedJobId,
  isSaving,
  onSelectJob,
  onCreateJob,
}: JDPickerProps): JSX.Element {
  const [showInput, setShowInput] = useState(jobs.length === 0);

  return (
    <div className="space-y-4">
      {jobs.length === 0 ? (
        <EmptyState
          title="No job descriptions yet"
          description="Paste a job description to continue. It will be saved automatically."
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {jobs.map((job) => (
            <JDCard key={job.id} job={job} selected={selectedJobId === job.id} onSelect={onSelectJob} />
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={() => setShowInput((value) => !value)}
        className="app-btn-secondary"
      >
        {showInput ? "Hide new JD form" : "Paste new JD"}
      </button>

      {showInput ? <JDInput isSaving={isSaving} onSubmit={onCreateJob} /> : null}
    </div>
  );
}
