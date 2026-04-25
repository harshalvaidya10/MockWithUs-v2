import { redirect } from "next/navigation";

interface LegacyInterviewResultsPageProps {
  params: {
    sessionId: string;
  };
}

export default function LegacyInterviewResultsPage({ params }: LegacyInterviewResultsPageProps): never {
  redirect(`/interview/${params.sessionId}/results`);
}
