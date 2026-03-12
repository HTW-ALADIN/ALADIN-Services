from abc import ABC, abstractmethod
from typing import TypeVar

unknown = TypeVar("unknown")


class IOAdapter(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def transform_data(self, data: unknown) -> unknown:
        return
