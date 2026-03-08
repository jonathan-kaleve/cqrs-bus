from abc import ABC, abstractmethod
from typing import Generic, TypeVar


class Command(ABC):
    pass


TCommand = TypeVar("TCommand", bound=Command)
TResult = TypeVar("TResult")


class CommandHandler(ABC, Generic[TCommand, TResult]):
    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        pass
