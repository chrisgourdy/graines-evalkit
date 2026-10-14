"""STORAGE — interchangeable persistence. V1: SQLite + JSONL + artifact files."""

from evalkit.storage.interfaces import Repository
from evalkit.storage.sqlite import NotFoundError, SQLiteRepository

__all__ = ["NotFoundError", "Repository", "SQLiteRepository"]
