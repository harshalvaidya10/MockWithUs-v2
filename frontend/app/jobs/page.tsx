import { redirect } from "next/navigation";


export default function LegacyJobsPage(): never {
  redirect("/dashboard/jobs");
}
