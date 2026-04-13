import { redirect } from "next/navigation";


export default function LegacyResumesPage(): never {
  redirect("/dashboard/resumes");
}
