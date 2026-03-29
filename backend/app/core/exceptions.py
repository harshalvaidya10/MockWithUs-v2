from __future__ import annotations


class MockWithUsError(Exception):
    """Base application exception for domain-level errors."""


class AuthenticationError(MockWithUsError):
    """Raised when authentication fails."""


class NotFoundError(MockWithUsError):
    """Raised when a requested resource is not found."""


class ValidationError(MockWithUsError):
    """Raised when a domain validation rule fails."""
