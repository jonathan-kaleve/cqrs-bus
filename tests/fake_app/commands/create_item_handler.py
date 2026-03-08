from dataclasses import dataclass

from cqrs_bus import Command, CommandHandler


@dataclass
class CreateItemCommand(Command):
    name: str


class CreateItemHandler(CommandHandler[CreateItemCommand, str]):
    async def handle(self, command: CreateItemCommand) -> str:
        return f"created:{command.name}"
