import { useState } from "react";
import { useEffect, useRef } from "react";

interface JDInputValue {
  title: string;
  company: string;
  content: string;
}

interface JDInputProps {
  isSaving: boolean;
  onSubmit: (value: JDInputValue) => Promise<void>;
}

export function JDInput({ isSaving, onSubmit }: JDInputProps): JSX.Element {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [content, setContent] = useState("");
  const lastSubmittedKeyRef = useRef<string>("");

  useEffect(() => {
    const normalized = content.trim();
    if (normalized.length < 50 || isSaving) return;

    const submissionKey = JSON.stringify({
      title: title.trim(),
      company: company.trim(),
      content: normalized,
    });
    if (lastSubmittedKeyRef.current === submissionKey) return;

    const timeoutId = window.setTimeout(() => {
      void onSubmit({
        title,
        company,
        content,
      });
      lastSubmittedKeyRef.current = submissionKey;
    }, 900);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [company, content, isSaving, onSubmit, title]);

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-sm font-medium text-foreground">Paste new job description</p>
      <p className="mt-1 text-xs text-foreground-muted">
        Auto-saves after you pause typing.
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Job title (optional)"
          className="app-input"
        />
        <input
          type="text"
          value={company}
          onChange={(event) => setCompany(event.target.value)}
          placeholder="Company (optional)"
          className="app-input"
        />
      </div>
      <textarea
        rows={7}
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder="Paste full job description here..."
        className="mt-3 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 focus:border-primary focus:ring-1 focus:ring-primary"
      />
      <p className="mt-3 text-xs text-foreground-muted">
        {isSaving ? "Saving..." : content.trim().length < 50 ? "Add at least 50 characters to save." : "Ready to auto-save."}
      </p>
    </div>
  );
}
