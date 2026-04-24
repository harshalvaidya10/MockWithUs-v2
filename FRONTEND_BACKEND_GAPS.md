# Frontend-Backend Gaps

## 1) Interview question-count control is not backend-configurable
- The `/practice` UI supports optional settings, but `/interviews/start` does not currently accept a question-count parameter.
- Impact: question count cannot be user-configured end-to-end yet.

## 2) Interview results payload lacks answer-audio URLs
- Per-question results include transcript and scoring, but no stable audio URL for playback.
- Impact: interview results page cannot render per-answer audio players yet.

## 3) Active resume preference is frontend-local
- Library supports "Set Active" resume in localStorage only.
- Impact: active resume preference does not persist across devices/sessions unless backend persistence is added.
