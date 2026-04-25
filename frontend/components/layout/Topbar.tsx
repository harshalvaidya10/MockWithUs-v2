"use client";

import Link from "next/link";
import { Menu } from "lucide-react";

interface TopbarProps {
  title: string;
  onToggleSidebar: () => void;
}

export function Topbar({ title, onToggleSidebar }: TopbarProps): JSX.Element {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
      <div className="flex items-center justify-between px-4 py-3 lg:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="app-btn-ghost h-8 w-8 px-0 lg:hidden"
            aria-label="Open sidebar"
          >
            <Menu className="h-4 w-4" />
          </button>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">{title}</h1>
        </div>

        <Link
          href="/practice"
          className="app-btn-secondary"
        >
          Start Practice
        </Link>
      </div>
    </header>
  );
}
