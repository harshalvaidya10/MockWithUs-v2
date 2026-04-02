export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface Session {
  id: string;
  status: string;
  match_score: number | null;
  match_summary: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Question {
  id: string;
  session_id: string;
  question_text: string;
  category: string | null;
  rationale: string | null;
  order_index: number;
  created_at: string;
}

export interface Answer {
  id: string;
  question_id: string;
  session_id: string;
  answer_text: string | null;
  transcript_text: string | null;
  audio_file_path: string | null;
  created_at: string;
}

export interface Evaluation {
  id: string;
  answer_id: string;
  session_id: string;
  relevance_score: number | null;
  clarity_score: number | null;
  depth_score: number | null;
  structure_score: number | null;
  overall_score: number | null;
  feedback_text: string | null;
  strengths: string[];
  improvements: string[];
  created_at: string;
}

export interface ResumeUploadResponse {
  id: string;
  filename: string;
  skills: string[];
  created_at: string;
}
