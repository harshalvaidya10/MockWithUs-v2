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
  is_resume_like?: boolean;
}

export interface JobOut {
  id: string;
  title: string | null;
  company: string | null;
  keywords: string[];
  required_skills: string[];
  created_at: string;
}

export interface JobDetailOut extends JobOut {
  content: string;
}

export interface SkillGap {
  matched: string[];
  missing: string[];
  coverage: number;
}

export interface MatchResult {
  match_score: number;
  skill_gaps: SkillGap;
  match_summary: string;
  resume_id: string;
  job_id: string;
}

export interface InterviewStartQuestion {
  id: string;
  question_text: string;
  category: string;
  rationale: string;
  order_index: number;
}

export interface InterviewStartResponse {
  session_id: string;
  match_score: number;
  match_summary: string;
  questions: InterviewStartQuestion[];
}
