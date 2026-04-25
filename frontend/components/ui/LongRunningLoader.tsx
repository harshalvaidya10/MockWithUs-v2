"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

interface LongRunningLoaderProps {
  title: string;
  phrases: string[];
  className?: string;
}

export function LongRunningLoader({ title, phrases, className = "" }: LongRunningLoaderProps): JSX.Element {
  const [index, setIndex] = useState(0);
  const prefersReducedMotion = useReducedMotion();

  const effectivePhrases = useMemo(
    () => (phrases.length > 0 ? phrases : ["Working on your request..."]),
    [phrases],
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % effectivePhrases.length);
    }, 2500);

    return () => {
      window.clearInterval(timer);
    };
  }, [effectivePhrases.length]);

  return (
    <div className={`rounded-xl border border-border bg-surface p-6 ${className}`.trim()}>
      <p className="text-lg font-semibold tracking-tight text-foreground">{title}</p>
      <div className="mt-2 min-h-6 text-sm text-foreground-muted" role="status" aria-live="polite" aria-atomic="true">
        <AnimatePresence mode="wait">
          <motion.p
            key={`${effectivePhrases[index]}-${index}`}
            initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 4 }}
            animate={prefersReducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
            exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: -4 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            {effectivePhrases[index]}
          </motion.p>
        </AnimatePresence>
      </div>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-surface-hover" aria-hidden="true">
        <motion.div
          className={`h-full rounded-full bg-primary ${prefersReducedMotion ? "w-full" : "w-1/3"}`}
          animate={prefersReducedMotion ? undefined : { x: ["-120%", "320%"] }}
          transition={prefersReducedMotion ? undefined : { duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
    </div>
  );
}
