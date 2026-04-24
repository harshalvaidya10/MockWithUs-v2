import { redirect } from "next/navigation";

export default function LegacyJobsPage(): never {
  redirect("/library?tab=jobs");
}
