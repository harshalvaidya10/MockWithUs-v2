import { redirect } from "next/navigation";

export default function LegacyNewJobPage(): never {
  redirect("/library?tab=jobs");
}
