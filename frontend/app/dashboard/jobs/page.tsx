import { redirect } from "next/navigation";

export default function LegacyDashboardJobsPage(): never {
  redirect("/library?tab=jobs");
}
