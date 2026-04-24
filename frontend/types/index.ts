export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface Session {
  id: string;
  status: string;
  session_type: "interview" | "coding";
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

export interface SessionAnswerItem {
  answer_id: string;
  session_id: string;
  question_id: string;
  transcript_text: string | null;
  created_at: string;
}

export interface SessionAnswerListResponse {
  session_id: string;
  answers: SessionAnswerItem[];
}

export interface AudioAnswerSubmissionResponse {
  answer_id: string;
  session_id: string;
  question_id: string;
  transcript_text: string;
  created_at: string;
}

export interface InterviewHistoryItem {
  session_id: string;
  resume_id: string | null;
  job_id: string | null;
  status: string;
  session_type: "interview" | "coding";
  match_score: number | null;
  match_summary: string | null;
  question_count: number;
  answered_count: number;
  is_complete: boolean;
  created_at: string;
  completed_at: string | null;
  problem_title?: string | null;
  difficulty?: "medium" | "hard" | null;
  tests_passed?: number | null;
  tests_total?: number | null;
  overall_score?: number | null;
}

export interface InterviewHistoryResponse {
  sessions: InterviewHistoryItem[];
}

export type CodingLanguage = "python" | "javascript" | "java" | "cpp";
export type CodingDifficulty = "medium" | "hard";

export interface CodingFunctionSignatureEntry {
  name: string;
  params: string;
  return_type: string;
}

export interface CodingProblem {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  category: string | null;
  function_signature: Record<string, CodingFunctionSignatureEntry>;
  starter_code: Record<string, string>;
  constraints: string | null;
}

export interface TestCase {
  id: string;
  input_data: string;
  expected_output: string;
  order_index: number | null;
}

export interface TestResult {
  test_case_id: string;
  passed: boolean;
  actual_output: string | null;
  expected_output: string | null;
  runtime_ms: number | null;
  error_output: string | null;
  status: string;
}

export interface CodeEvaluation {
  tests_passed: number;
  tests_total: number;
  pass_rate: number;
  correctness_score: number;
  efficiency_score: number;
  code_quality_score: number;
  problem_solving_score: number;
  overall_score: number;
  feedback_text: string;
  strengths: string[];
  improvements: string[];
  expected_solution: string;
  complexity_analysis: string;
}

export interface CodingSessionResponse {
  session_id: string;
  problem: CodingProblem;
  sample_test_cases: TestCase[];
}

export interface CodingProblemResponse {
  problem: CodingProblem;
  sample_test_cases: TestCase[];
}

export interface CodeRunResponse {
  submission_id: string;
  results: TestResult[];
}

export interface CodeSubmitResponse {
  submission_id: string;
  results: TestResult[];
  evaluation: CodeEvaluation;
}
