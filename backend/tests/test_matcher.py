from __future__ import annotations

import math

import numpy as np
import pytest

from app.services.matcher import (
    MatchResult,
    SkillGapResult,
    compute_match_score,
    compute_similarity,
    find_skill_gaps,
    generate_match_summary,
    parse_embedding_vector,
    run_match,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit_vec(values: list[float]) -> list[float]:
    """Return a unit-normalised version of the input vector."""
    arr = np.array(values, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    return (arr / norm).tolist()


# ---------------------------------------------------------------------------
# compute_similarity
# ---------------------------------------------------------------------------


def test_parse_embedding_vector_parses_json_string() -> None:
    """Serialized JSON vectors should parse into float lists."""
    parsed = parse_embedding_vector("[1, 2.5, 3]")
    assert parsed == [1.0, 2.5, 3.0]


def test_parse_embedding_vector_returns_none_for_invalid_payload() -> None:
    """Malformed persisted embeddings should fail safe to None."""
    assert parse_embedding_vector("{bad json") is None
    assert parse_embedding_vector("not-a-list") is None
    assert parse_embedding_vector(["x", 2]) is None

def test_similarity_identical_vectors_returns_one() -> None:
    """Dot product of a unit vector with itself must equal 1.0."""
    vec = _unit_vec([1.0, 2.0, 3.0, 4.0])
    assert math.isclose(compute_similarity(vec, vec), 1.0, abs_tol=1e-6)


def test_similarity_orthogonal_vectors_returns_zero() -> None:
    """Dot product of two orthogonal unit vectors must equal 0.0."""
    a = _unit_vec([1.0, 0.0, 0.0])
    b = _unit_vec([0.0, 1.0, 0.0])
    assert math.isclose(compute_similarity(a, b), 0.0, abs_tol=1e-6)


def test_similarity_result_clamped_between_zero_and_one() -> None:
    """Anti-parallel vectors would yield -1 raw; clamp must bring it to 0.0."""
    a = _unit_vec([1.0, 0.0])
    b = _unit_vec([-1.0, 0.0])
    result = compute_similarity(a, b)
    assert 0.0 <= result <= 1.0
    assert math.isclose(result, 0.0, abs_tol=1e-6)


def test_similarity_raises_for_dimension_mismatch() -> None:
    """Mismatched vector lengths should fail fast with a clear ValueError."""
    with pytest.raises(ValueError):
        compute_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_compute_match_score_backwards_compatibility_wrapper() -> None:
    """Legacy compute_match_score should delegate to similarity scoring."""
    score = compute_match_score([1.0, 0.0], [1.0, 0.0])
    assert math.isclose(score, 1.0, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# find_skill_gaps
# ---------------------------------------------------------------------------

def test_skill_gap_detects_matched_and_missing() -> None:
    """Skills present in both lists are matched; JD-only skills are missing."""
    result = find_skill_gaps(
        resume_skills=["python", "fastapi", "docker"],
        jd_required_skills=["python", "kubernetes", "docker"],
    )
    assert "python" in result["matched"]
    assert "docker" in result["matched"]
    assert "kubernetes" in result["missing"]
    assert "fastapi" not in result["missing"]


def test_skill_gap_full_match_has_empty_missing() -> None:
    """When resume covers all JD skills, missing must be empty and coverage 1.0."""
    result = find_skill_gaps(["python", "docker"], ["python", "docker"])
    assert result["missing"] == []
    assert math.isclose(result["coverage"], 1.0)


def test_skill_gap_empty_jd_skills_gives_full_coverage() -> None:
    """No JD requirements → no gaps by definition; coverage is 1.0."""
    result = find_skill_gaps(["python"], [])
    assert math.isclose(result["coverage"], 1.0)
    assert result["missing"] == []
    assert result["matched"] == []


def test_skill_gap_is_case_insensitive() -> None:
    """'Python' and 'DOCKER' in resume must match 'python' and 'docker' in JD."""
    result = find_skill_gaps(["Python", "DOCKER"], ["python", "docker"])
    assert result["missing"] == []
    assert math.isclose(result["coverage"], 1.0)


def test_skill_gap_coverage_ratio_correct() -> None:
    """Coverage = matched / total JD skills; 1 of 3 → ~0.333."""
    result = find_skill_gaps(["python"], ["python", "docker", "kubernetes"])
    assert math.isclose(result["coverage"], 1 / 3, rel_tol=1e-5)


def test_skill_gap_ignores_blank_tokens() -> None:
    """Blank strings should not be counted as skills in either list."""
    result = find_skill_gaps(["python", "   ", ""], ["python", ""])
    assert result["matched"] == ["python"]
    assert result["missing"] == []
    assert math.isclose(result["coverage"], 1.0)


# ---------------------------------------------------------------------------
# generate_match_summary
# ---------------------------------------------------------------------------

def test_summary_strong_match_contains_label() -> None:
    """Score >= 0.80 must produce 'Strong match' headline with role name."""
    gaps: SkillGapResult = {"matched": ["python", "docker"], "missing": [], "coverage": 1.0}
    summary = generate_match_summary(0.85, gaps, job_title="Backend Engineer")
    assert "Strong match" in summary
    assert "Backend Engineer" in summary
    assert "85%" in summary


def test_summary_solid_match_contains_label() -> None:
    """Score in [0.60, 0.80) must produce 'Solid match' headline."""
    gaps: SkillGapResult = {"matched": ["python"], "missing": ["kubernetes"], "coverage": 0.5}
    summary = generate_match_summary(0.70, gaps)
    assert "Solid match" in summary


def test_summary_moderate_match_contains_label() -> None:
    """Score in [0.40, 0.60) must produce 'Moderate match' headline."""
    gaps: SkillGapResult = {"matched": [], "missing": ["docker"], "coverage": 0.0}
    summary = generate_match_summary(0.50, gaps)
    assert "Moderate match" in summary


def test_summary_low_match_surfaces_missing_skills() -> None:
    """Score < 0.40 must produce 'Low match' and list missing skills."""
    gaps: SkillGapResult = {
        "matched": ["git"],
        "missing": ["kubernetes", "terraform", "kafka", "spark", "airflow"],
        "coverage": 0.1,
    }
    summary = generate_match_summary(0.25, gaps)
    assert "Low match" in summary
    # At least one missing skill must appear in the summary body
    assert "kubernetes" in summary


def test_summary_caps_skills_at_five() -> None:
    """Matched and missing lists must be truncated to 5 items each in the summary."""
    gaps: SkillGapResult = {
        "matched": ["a", "b", "c", "d", "e", "f", "g"],
        "missing": ["x", "y", "z", "w", "v", "u"],
        "coverage": 0.5,
    }
    summary = generate_match_summary(0.65, gaps)
    # "f" and "g" are the 6th and 7th matched items — must not appear
    assert "f" not in summary
    assert "u" not in summary


# ---------------------------------------------------------------------------
# run_match
# ---------------------------------------------------------------------------

def test_run_match_uses_semantic_score_when_embeddings_present() -> None:
    """When both embeddings are provided, match_score must come from dot product."""
    vec = _unit_vec([1.0] * 8)
    result = run_match(
        resume_embedding=vec,
        jd_embedding=vec,
        resume_skills=["python"],
        jd_required_skills=["python"],
    )
    assert math.isclose(result["match_score"], 1.0, abs_tol=1e-5)
    # TypedDict contract: all three keys must be present
    assert "match_score" in result
    assert "skill_gaps" in result
    assert "match_summary" in result


def test_run_match_falls_back_to_coverage_when_no_embeddings() -> None:
    """When embeddings are None, skill-coverage score is used as match_score."""
    result = run_match(
        resume_embedding=None,
        jd_embedding=None,
        resume_skills=["python", "docker"],
        jd_required_skills=["python", "docker", "kubernetes"],
    )
    # coverage = 2 matched / 3 required
    assert math.isclose(result["match_score"], 2 / 3, rel_tol=1e-5)


def test_run_match_no_embeddings_with_empty_jd_skills_defaults_to_zero() -> None:
    """Missing embeddings + no JD skills should not be treated as a perfect match."""
    result = run_match(
        resume_embedding=None,
        jd_embedding=None,
        resume_skills=["python", "docker"],
        jd_required_skills=[],
    )
    assert math.isclose(result["match_score"], 0.0, abs_tol=1e-6)


def test_run_match_partial_embedding_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    """A single None embedding (resume or JD) must trigger the fallback path."""
    vec = _unit_vec([1.0, 0.0])
    result = run_match(
        resume_embedding=vec,
        jd_embedding=None,
        resume_skills=["python"],
        jd_required_skills=["python"],
    )
    # coverage = 1.0 (full match)
    assert math.isclose(result["match_score"], 1.0, abs_tol=1e-5)


def test_run_match_invalid_embedding_shape_falls_back_to_coverage() -> None:
    """Invalid embeddings should degrade gracefully to coverage scoring."""
    result = run_match(
        resume_embedding=[1.0, 0.0],
        jd_embedding=[1.0, 0.0, 0.0],
        resume_skills=["python"],
        jd_required_skills=["python", "docker"],
    )
    assert math.isclose(result["match_score"], 0.5, abs_tol=1e-6)


def test_run_match_invalid_embeddings_with_empty_jd_skills_defaults_to_zero() -> None:
    """Invalid embeddings + no JD skill requirements should use safe fallback score 0.0."""
    result = run_match(
        resume_embedding=[1.0, 0.0],
        jd_embedding=[1.0, 0.0, 0.0],
        resume_skills=["python"],
        jd_required_skills=["", "   "],
    )
    assert math.isclose(result["match_score"], 0.0, abs_tol=1e-6)


def test_run_match_score_clamped() -> None:
    """match_score must always be in [0.0, 1.0] regardless of raw dot product."""
    # Anti-parallel vectors → raw dot product = -1, must be clamped to 0
    a = _unit_vec([1.0, 0.0])
    b = _unit_vec([-1.0, 0.0])
    result = run_match(a, b, [], [])
    assert 0.0 <= result["match_score"] <= 1.0


def test_run_match_returns_match_result_type() -> None:
    """Return value must satisfy the MatchResult TypedDict shape."""
    vec = _unit_vec([0.5, 0.5])
    result: MatchResult = run_match(vec, vec, ["python"], ["python", "docker"])
    assert isinstance(result["match_score"], float)
    assert isinstance(result["match_summary"], str)
    assert isinstance(result["skill_gaps"]["matched"], list)
    assert isinstance(result["skill_gaps"]["missing"], list)
    assert isinstance(result["skill_gaps"]["coverage"], float)
