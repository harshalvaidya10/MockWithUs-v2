from __future__ import annotations

import pytest

from app.services.resume_parser import parse_resume_file


def test_resume_parser_is_deferred() -> None:
    """Ensure the scaffold makes the deferred boundary explicit."""

    with pytest.raises(NotImplementedError):
        parse_resume_file("resume.pdf")
