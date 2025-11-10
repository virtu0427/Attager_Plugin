"""Frontend compatibility wrapper for IAM database utilities."""

from iam.database import IAMDatabase, get_db  # noqa: F401

__all__ = ["IAMDatabase", "get_db"]
