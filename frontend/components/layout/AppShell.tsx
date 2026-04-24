"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/hooks/useAuth";

interface AppShellProps {
  children: import("react").ReactNode;
}

function titleForPath(pathname: string): string {
  if (pathname.startsWith("/practice")) return "Practice";
  if (pathname.startsWith("/library")) return "Library";
  if (pathname.startsWith("/interview")) return "Interview Results";
  if (pathname.startsWith("/coding")) return "Coding Results";
  return "Home";
}

export function AppShell({ children }: AppShellProps): JSX.Element {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const nextPath = pathname || "/home";
      router.push(`/login?next=${encodeURIComponent(nextPath)}`);
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  const pageTitle = useMemo(() => titleForPath(pathname), [pathname]);

  function handleLogout(): void {
    logout();
    router.push("/login");
  }

  if (isLoading) {
    return (
      <main className="min-h-screen bg-background px-4 py-6 lg:px-6">
        <div className="mx-auto max-w-6xl space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="mx-auto max-w-3xl rounded-xl border border-border bg-surface p-6">
          <p className="text-sm text-foreground-muted">Redirecting to login...</p>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user}
        onLogout={handleLogout}
      />
      <div className="lg:pl-64">
        <Topbar title={pageTitle} onToggleSidebar={() => setSidebarOpen((value) => !value)} />
        <main className="px-4 py-6 lg:px-6">{children}</main>
      </div>
    </div>
  );
}
