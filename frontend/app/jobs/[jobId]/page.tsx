import { redirect } from "next/navigation";

export default function LegacyJobDetailPage(): never {
  redirect("/library?tab=jobs");
}
