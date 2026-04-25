import { redirect } from "next/navigation";

export default function LegacyDashboardResumesPage(): never {
  redirect("/library?tab=resumes");
}
