from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class PagedResult(Generic[T]):
    items: list[T]
    total: int


__all__ = ["PagedResult"]
