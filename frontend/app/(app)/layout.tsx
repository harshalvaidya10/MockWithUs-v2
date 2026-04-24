import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";

export default function AuthenticatedLayout({ children }: { children: ReactNode }): JSX.Element {
  return <AppShell>{children}</AppShell>;
}
