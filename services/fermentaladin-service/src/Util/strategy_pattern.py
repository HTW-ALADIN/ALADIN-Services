from typing import Dict, Generic, TypeVar

T = TypeVar("T")


class Strategy(Generic[T]):
    strategies: Dict[str, T] = {}

    @staticmethod
    def register_strategy(strategy: T) -> None:
        Strategy.strategies[strategy.__qualname__] = strategy

    @staticmethod
    def select_strategy(strategy_name: str) -> T:
        return Strategy.strategies[strategy_name]()
