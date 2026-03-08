from abc import ABC, abstractmethod
from typing import Generic, TypeVar


class Query(ABC):
    pass


TQuery = TypeVar("TQuery", bound=Query)
TResult = TypeVar("TResult")


class QueryHandler(ABC, Generic[TQuery, TResult]):
    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        pass
