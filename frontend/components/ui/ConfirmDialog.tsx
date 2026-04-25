"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isConfirming?: boolean;
  icon?: ReactNode;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  isConfirming = false,
  icon,
}: ConfirmDialogProps): JSX.Element {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    previouslyFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }

    const firstFocusable = dialog.querySelector<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    (firstFocusable ?? dialog).focus();
  }, [open]);

  useEffect(() => {
    if (open) {
      return;
    }
    const previouslyFocused = previouslyFocusedRef.current;
    if (previouslyFocused) {
      previouslyFocused.focus();
      previouslyFocusedRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onCancel]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[70] flex items-center justify-center bg-foreground/20 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15, ease: "easeInOut" }}
        >
          <motion.div
            className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-[0_4px_12px_rgba(0,0,0,0.04)]"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            tabIndex={-1}
            ref={dialogRef}
          >
            <div className="flex items-start gap-3">
              {icon ? <div className="mt-0.5 text-danger">{icon}</div> : null}
              <div>
                <h2 id={titleId} className="text-lg font-semibold tracking-tight text-foreground">
                  {title}
                </h2>
                <p id={descriptionId} className="mt-1 text-sm leading-relaxed text-foreground-muted">
                  {description}
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button type="button" onClick={onCancel} className="app-btn-ghost" disabled={isConfirming}>
                {cancelLabel}
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={isConfirming}
                className="inline-flex h-9 items-center justify-center rounded-lg bg-danger px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isConfirming ? "Working..." : confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
