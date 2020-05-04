from dataclasses import dataclass
from typing import Generic
from typing import TypeVar

T = TypeVar("T")


@dataclass
class Boxed(Generic[T]):
    t: T
