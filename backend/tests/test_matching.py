from __future__ import annotations

import pytest

from app.services.matcher import compute_match_score


def test_matcher_is_deferred() -> None:
    """Ensure the scaffold makes the deferred boundary explicit."""

    with pytest.raises(NotImplementedError):
        compute_match_score([0.1], [0.1])
