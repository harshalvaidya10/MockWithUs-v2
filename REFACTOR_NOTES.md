# MockWithUs Frontend Refactor Notes

## Scope
Frontend-focused, with required backend additions/alignments (includes new endpoints, schemas, and migrations where noted).

## Routes Added
- `/home`
- `/practice`
- `/library`
- `/interview/[sessionId]/results`
- `/coding/[sessionId]/results`
- Authenticated shell group: `app/(app)/layout.tsx`

## Routes Replaced With Redirects
- `/dashboard` -> `/home`
- `/dashboard/resumes` -> `/library?tab=resumes`
- `/dashboard/jobs` -> `/library?tab=jobs`
- `/dashboard/matching` -> `/practice`
- `/interview/results/[sessionId]` -> `/interview/[sessionId]/results`
- `/coding/results/[sessionId]` -> `/coding/[sessionId]/results`
- `/interview/new` -> `/practice`
- `/jobs` -> `/library?tab=jobs`
- `/jobs/new` -> `/library?tab=jobs`
- `/jobs/[jobId]` -> `/library?tab=jobs`
- `/resumes` -> `/library?tab=resumes`

## New / Consolidated Components
- Layout shell:
  - `frontend/components/layout/AppShell.tsx`
  - `frontend/components/layout/Sidebar.tsx`
  - `frontend/components/layout/Topbar.tsx`
- Dashboard + display:
  - `frontend/components/dashboard/SessionCard.tsx`
  - `frontend/components/ui/StatCard.tsx`
  - `frontend/components/ui/ScoreBar.tsx`
  - `frontend/components/ui/FeedbackAccordion.tsx`
  - `frontend/components/ui/EmptyState.tsx`
  - `frontend/components/ui/Skeleton.tsx`
- Practice flow:
  - `frontend/components/practice/StepperWizard.tsx`
  - `frontend/components/practice/ModeSelector.tsx`
  - `frontend/components/practice/MatchPreview.tsx`
  - `frontend/components/practice/ResumePicker.tsx`
  - `frontend/components/practice/ResumeCard.tsx`
  - `frontend/components/practice/ResumeUploadDropzone.tsx`
  - `frontend/components/practice/JDPicker.tsx`
  - `frontend/components/practice/JDCard.tsx`
  - `frontend/components/practice/JDInput.tsx`
- Session UX:
  - `frontend/components/interview/QuestionPlayer.tsx`
  - `frontend/components/ui/LongRunningLoader.tsx`
  - `frontend/components/ui/PageTransition.tsx`
  - `frontend/components/ui/ConfirmDialog.tsx`

## Components Deleted
- No legacy component files were deleted because prior `components/` structure had no conflicting production components to remove.

## Major UX / IA Changes
- Replaced old dashboard CRUD hub with:
  - `/home` for action-first overview and recent sessions
  - `/practice` for unified setup wizard
  - `/library` for combined resumes + job descriptions
- Matching now auto-runs when resume + JD are selected in `/practice`.
- Active interview/coding routes use focus mode (no app shell chrome).
- Results routes moved to nested structure under session id.
- Resume/JD previews are available in-app from Library.
- Delete actions now use custom confirm dialog + toast feedback.

## Visual System Changes
- Introduced CSS variable-driven light theme in `frontend/app/globals.css`.
- Updated Tailwind token mapping in `frontend/tailwind.config.ts`.
- Standardized card/button/input styles with reusable utility classes.
- Added subtle page fade transitions (Framer Motion).
- Added long-running operation loaders with cycling status phrases.
- Monaco on coding page is enforced to light theme (`vs`).

## Dependency Changes
- Added:
  - `framer-motion`
  - `sonner`
  - `lucide-react`

## Preserved Behavior
- Audio TTS playback for interview questions.
- Mic recording, preview, and `/answers/audio` submission.
- Interview session resume via `sessionStorage` + `/answers/session/{sessionId}`.
- Quit-early completion flow via `/interviews/{sessionId}/complete`.
- Coding multi-language persistence via `localStorage`, cleared on submit.
- Interview results auto-evaluation fallback (`/evaluate/{sessionId}` if needed).
- Coding results -> start interview cross-mode flow.

## Validation
- `npm run build` passed successfully in `frontend/`.

## Known Spec Decisions
- `/home/history` was implemented as inline expand/collapse of recent sessions on `/home` (allowed by spec alternative).
