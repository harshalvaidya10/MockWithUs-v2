from __future__ import annotations

import math

from app.services.matcher import compute_match_score


def test_compute_match_score_uses_cosine_similarity() -> None:
    """Identical unit vectors should produce a perfect score."""
    score = compute_match_score([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert math.isclose(score, 1.0, abs_tol=1e-6)


def test_compute_match_score_clamps_negative_values() -> None:
    """Anti-parallel vectors produce -1 raw dot product and must clamp to 0."""
    score = compute_match_score([1.0, 0.0], [-1.0, 0.0])
    assert math.isclose(score, 0.0, abs_tol=1e-6)
