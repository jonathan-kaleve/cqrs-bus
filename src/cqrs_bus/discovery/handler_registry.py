from dataclasses import dataclass

from cqrs_bus.discovery.exceptions import DuplicateHandlerError


@dataclass
class HandlerMetadata:
    handler_class: type
    command_or_query_type: type
    dependencies: list[str]
    module_path: str


class HandlerRegistry:
    def __init__(self):
        self._command_handlers: dict[type, HandlerMetadata] = {}
        self._query_handlers: dict[type, HandlerMetadata] = {}

    def register_command_handler(self, metadata: HandlerMetadata) -> None:
        if metadata.command_or_query_type in self._command_handlers:
            existing = self._command_handlers[metadata.command_or_query_type]
            raise DuplicateHandlerError(
                f"Multiple handlers found for {metadata.command_or_query_type.__name__}: "
                f"{existing.handler_class.__name__} and {metadata.handler_class.__name__}"
            )
        self._command_handlers[metadata.command_or_query_type] = metadata

    def register_query_handler(self, metadata: HandlerMetadata) -> None:
        if metadata.command_or_query_type in self._query_handlers:
            existing = self._query_handlers[metadata.command_or_query_type]
            raise DuplicateHandlerError(
                f"Multiple handlers found for {metadata.command_or_query_type.__name__}: "
                f"{existing.handler_class.__name__} and {metadata.handler_class.__name__}"
            )
        self._query_handlers[metadata.command_or_query_type] = metadata

    def get_all_command_handlers(self) -> list[HandlerMetadata]:
        return list(self._command_handlers.values())

    def get_all_query_handlers(self) -> list[HandlerMetadata]:
        return list(self._query_handlers.values())

    def get_command_handler_count(self) -> int:
        return len(self._command_handlers)

    def get_query_handler_count(self) -> int:
        return len(self._query_handlers)
