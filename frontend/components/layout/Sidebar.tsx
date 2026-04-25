"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenText, House, LogOut, Sparkles } from "lucide-react";

import type { CurrentUser } from "@/hooks/useAuth";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  user: CurrentUser | null;
  onLogout: () => void;
}

interface NavItem {
  label: string;
  href: string;
  icon: typeof House;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/home", icon: House },
  { label: "Practice", href: "/practice", icon: Sparkles },
  { label: "Library", href: "/library", icon: BookOpenText },
];

export function Sidebar({ isOpen, onClose, user, onLogout }: SidebarProps): JSX.Element {
  const pathname = usePathname();

  return (
    <>
      {isOpen ? (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-foreground/20 lg:hidden"
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 border-r border-border bg-surface p-4 transition-transform duration-200 ease-out lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="mb-6 border-b border-border pb-4">
            <Image
              src="/brand/logo-wordmark.svg"
              alt="MockWithUs"
              width={208}
              height={56}
              className="h-9 w-auto"
              priority
            />
            <p className="mt-2 text-xs text-foreground-muted">Interview Copilot</p>
          </div>

          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onClose}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                    active
                      ? "border border-transparent bg-primary-subtle text-primary"
                      : "text-foreground-muted hover:bg-surface-hover hover:text-foreground"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto border-t border-border pt-4">
            <p className="truncate text-xs text-foreground-muted">{user?.full_name ?? user?.email ?? "Logged in"}</p>
            <button
              type="button"
              onClick={onLogout}
              className="app-btn-secondary mt-3 w-full justify-center gap-2"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
