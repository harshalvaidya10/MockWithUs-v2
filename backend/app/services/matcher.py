from __future__ import annotations

import json
import logging
from typing import TypedDict

import numpy as np

logger = logging.getLogger(__name__)


class SkillGapResult(TypedDict):
    """Outcome of comparing resume skills against JD requirements."""

    matched: list[str]
    missing: list[str]
    coverage: float  # len(matched) / len(jd_skills), clamped to [0.0, 1.0]


class MatchResult(TypedDict):
    """Complete resume-to-JD match result passed into interview session creation."""

    match_score: float  # 0.0 – 1.0
    skill_gaps: SkillGapResult
    match_summary: str


def parse_embedding_vector(raw: object) -> list[float] | None:
    """Parse persisted embedding payloads into float vectors.

    Supported input shapes:
    - `None` -> no embedding
    - JSON string containing a numeric list
    - list/tuple of numeric values
    """
    if raw is None:
        return None

    candidate = raw
    if isinstance(raw, str):
        try:
            candidate = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    if not isinstance(candidate, (list, tuple)):
        return None

    parsed: list[float] = []
    try:
        for value in candidate:
            parsed.append(float(value))
    except (TypeError, ValueError):
        return None

    return parsed if parsed else None


def compute_similarity(
    resume_embedding: list[float],
    jd_embedding: list[float],
) -> float:
    """Return the dot product of two pre-normalised embedding vectors.

    all-MiniLM-L6-v2 produces unit-norm vectors, so the dot product equals
    cosine similarity. Result is clamped to [0.0, 1.0] to guard against
    floating-point imprecision near the boundaries.
    """
    if not resume_embedding or not jd_embedding:
        raise ValueError("Embeddings must not be empty.")
    if len(resume_embedding) != len(jd_embedding):
        raise ValueError("Embedding vectors must have the same dimensionality.")

    a = np.array(resume_embedding, dtype=np.float32)
    b = np.array(jd_embedding, dtype=np.float32)

    score = float(np.dot(a, b))
    if not np.isfinite(score):
        raise ValueError("Embedding similarity is not finite.")

    return max(0.0, min(1.0, score))


def compute_match_score(
    resume_embedding: list[float],
    job_embedding: list[float],
) -> float:
    """Backward-compatible wrapper used by older matcher call sites/tests."""
    return compute_similarity(resume_embedding, job_embedding)


def find_skill_gaps(
    resume_skills: list[str],
    jd_required_skills: list[str],
) -> SkillGapResult:
    """Compute matched, missing, and coverage from two skill lists.

    Both lists are normalised to lowercase before set operations so that
    'Python' and 'python' are treated as the same skill.
    Empty JD requirements → coverage = 1.0 (no requirements means no gaps).
    """
    resume_set = {s.lower().strip() for s in resume_skills if s and s.strip()}
    jd_set = {s.lower().strip() for s in jd_required_skills if s and s.strip()}

    if not jd_set:
        return SkillGapResult(matched=[], missing=[], coverage=1.0)

    matched = sorted(resume_set & jd_set)
    missing = sorted(jd_set - resume_set)
    coverage = len(matched) / len(jd_set)

    return SkillGapResult(matched=matched, missing=missing, coverage=coverage)


def generate_match_summary(
    match_score: float,
    skill_gaps: SkillGapResult,
    job_title: str | None = None,
) -> str:
    """Build a deterministic, information-dense summary string for LLM consumption.

    Score bands:
      >= 0.80 → Strong match
      >= 0.60 → Solid match with some gaps
      >= 0.40 → Moderate match, targeted prep recommended
      <  0.40 → Low match, significant prep needed

    Up to 5 matched and 5 missing skills are surfaced inline.
    This string is passed directly into the question-generation prompt in Phase 4,
    so it is kept information-dense rather than conversational.
    """
    pct = round(match_score * 100)
    role = f" for {job_title}" if job_title else ""

    if match_score >= 0.80:
        headline = f"Strong match{role} ({pct}%)."
    elif match_score >= 0.60:
        headline = f"Solid match{role} ({pct}%) with some gaps to address."
    elif match_score >= 0.40:
        headline = f"Moderate match{role} ({pct}%) — targeted preparation recommended."
    else:
        headline = f"Low match{role} ({pct}%) — significant preparation needed."

    parts = [headline]

    matched_sample = skill_gaps["matched"][:5]
    missing_sample = skill_gaps["missing"][:5]

    if matched_sample:
        parts.append(f"Matched skills: {', '.join(matched_sample)}.")
    if missing_sample:
        parts.append(f"Skills to develop: {', '.join(missing_sample)}.")

    return " ".join(parts)


def run_match(
    resume_embedding: list[float] | None,
    jd_embedding: list[float] | None,
    resume_skills: list[str],
    jd_required_skills: list[str],
    job_title: str | None = None,
) -> MatchResult:
    """Compute a complete resume-to-JD match result from embeddings and skill lists.

    Graceful fallback: if either embedding is None, skill-coverage score is used
    instead of semantic similarity. A WARNING is logged so operators know that
    semantic matching was bypassed — this is common for documents uploaded before
    the embedding service was enabled.

    The returned MatchResult is consumed by POST /interviews/start in Phase 4.
    """
    skill_gaps = find_skill_gaps(resume_skills, jd_required_skills)

    if resume_embedding is None or jd_embedding is None:
        logger.warning(
            "One or both embeddings are missing — falling back to skill-coverage score. "
            "Re-process documents to enable semantic matching."
        )
        match_score: float = skill_gaps["coverage"]
    else:
        try:
            match_score = compute_similarity(resume_embedding, jd_embedding)
        except ValueError:
            logger.warning(
                "Invalid embeddings supplied to matcher — falling back to skill coverage.",
                exc_info=True,
            )
            match_score = skill_gaps["coverage"]

    match_score = max(0.0, min(1.0, match_score))
    summary = generate_match_summary(match_score, skill_gaps, job_title=job_title)

    return MatchResult(match_score=match_score, skill_gaps=skill_gaps, match_summary=summary)
