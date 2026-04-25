import { redirect } from "next/navigation";

interface LegacyCodingResultsPageProps {
  params: {
    sessionId: string;
  };
}

export default function LegacyCodingResultsPage({ params }: LegacyCodingResultsPageProps): never {
  redirect(`/coding/${params.sessionId}/results`);
}
