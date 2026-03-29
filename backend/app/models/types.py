from __future__ import annotations

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """Minimal SQLAlchemy type for PostgreSQL pgvector columns."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        """Return the PostgreSQL column type specification."""

        return f"VECTOR({self.dimensions})"
