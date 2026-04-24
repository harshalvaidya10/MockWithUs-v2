import { useRef } from "react";

interface ResumeUploadDropzoneProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export function ResumeUploadDropzone({ onFileSelect, disabled = false }: ResumeUploadDropzoneProps): JSX.Element {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className="rounded-xl border border-dashed border-border-strong bg-surface p-6 text-center">
      <p className="text-sm text-foreground">Drop your resume here or choose a file</p>
      <p className="mt-1 text-xs text-foreground-muted">Accepted formats: PDF, DOCX</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            onFileSelect(file);
          }
          event.currentTarget.value = "";
        }}
        className="hidden"
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="app-btn-secondary mt-4"
      >
        {disabled ? "Uploading..." : "Choose File"}
      </button>
    </div>
  );
}
