from dataclasses import dataclass

from cqrs_bus import Command, CommandHandler


@dataclass
class SharedCommand(Command):
    data: str


class SharedCommandHandler(CommandHandler[SharedCommand, str]):
    async def handle(self, command: SharedCommand) -> str:
        return f"shared:{command.data}"
