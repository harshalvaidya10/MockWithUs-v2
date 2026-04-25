import { ResumeCard } from "@/components/practice/ResumeCard";
import { ResumeUploadDropzone } from "@/components/practice/ResumeUploadDropzone";
import { EmptyState } from "@/components/ui/EmptyState";
import type { ResumeUploadResponse } from "@/types";

interface ResumePickerProps {
  resumes: ResumeUploadResponse[];
  selectedResumeId: string;
  isUploading: boolean;
  onSelectResume: (id: string) => void;
  onUploadResume: (file: File) => void;
}

export function ResumePicker({
  resumes,
  selectedResumeId,
  isUploading,
  onSelectResume,
  onUploadResume,
}: ResumePickerProps): JSX.Element {
  if (resumes.length === 0) {
    return (
      <div className="space-y-4">
        <EmptyState
          title="No resumes yet"
          description="Upload your first resume to start practice sessions."
        />
        <ResumeUploadDropzone onFileSelect={onUploadResume} disabled={isUploading} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        {resumes.map((resume) => (
          <ResumeCard
            key={resume.id}
            resume={resume}
            selected={selectedResumeId === resume.id}
            onSelect={onSelectResume}
          />
        ))}
      </div>
      <ResumeUploadDropzone onFileSelect={onUploadResume} disabled={isUploading} />
    </div>
  );
}
