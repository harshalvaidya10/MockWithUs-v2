"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

interface LongRunningLoaderProps {
  title: string;
  phrases: string[];
  className?: string;
}

export function LongRunningLoader({ title, phrases, className = "" }: LongRunningLoaderProps): JSX.Element {
  const [index, setIndex] = useState(0);

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
      <div className="mt-2 min-h-6 text-sm text-foreground-muted">
        <AnimatePresence mode="wait">
          <motion.p
            key={`${effectivePhrases[index]}-${index}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            {effectivePhrases[index]}
          </motion.p>
        </AnimatePresence>
      </div>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-surface-hover">
        <motion.div
          className="h-full w-1/3 rounded-full bg-primary"
          animate={{ x: ["-120%", "320%"] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
    </div>
  );
}
