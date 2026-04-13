import { redirect } from "next/navigation";


export default function LegacyInterviewSetupPage(): never {
  redirect("/dashboard/matching");
}
