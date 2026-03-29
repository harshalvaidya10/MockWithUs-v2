from __future__ import annotations

import pytest

from app.services.evaluator import evaluate_answer


def test_evaluator_is_deferred() -> None:
    """Ensure the scaffold makes the deferred boundary explicit."""

    with pytest.raises(NotImplementedError):
        evaluate_answer("Tell me about yourself", "I build products.")
