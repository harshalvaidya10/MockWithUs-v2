import { redirect } from "next/navigation";

export default function LegacyDashboardPage(): never {
  redirect("/home");
}
