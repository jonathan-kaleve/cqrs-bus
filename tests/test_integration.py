"""
Integration tests: full pipeline from handler discovery through dispatch.

Exercises:
  HandlerDiscovery → DependencyResolver.create_handler_instance
  → CommandBus/QueryBus.register → dispatch
"""

import pytest

from cqrs_bus import CommandBus, DependencyResolver, HandlerDiscovery, QueryBus
from fake_app.commands.create_item_handler import CreateItemCommand
from fake_app.queries.get_item_handler import GetItemQuery
from fake_app.shared.commands.shared_command_handler import SharedCommand


def _build_buses(base_package: str) -> tuple[CommandBus, QueryBus]:
    """Discover handlers and wire them into fresh bus instances."""
    registry = HandlerDiscovery(base_package).discover_all_handlers()
    resolver = DependencyResolver()

    command_bus = CommandBus()
    for meta in registry.get_all_command_handlers():
        instance = resolver.create_handler_instance(meta.handler_class, {})
        command_bus.register(meta.command_or_query_type, instance)

    query_bus = QueryBus()
    for meta in registry.get_all_query_handlers():
        instance = resolver.create_handler_instance(meta.handler_class, {})
        query_bus.register(meta.command_or_query_type, instance)

    return command_bus, query_bus


class TestFullPipeline:
    async def test_command_dispatch_end_to_end(self):
        command_bus, _ = _build_buses("fake_app")
        result = await command_bus.dispatch(CreateItemCommand(name="widget"))
        assert result == "created:widget"

    async def test_shared_command_dispatch_end_to_end(self):
        command_bus, _ = _build_buses("fake_app")
        result = await command_bus.dispatch(SharedCommand(data="hello"))
        assert result == "shared:hello"

    async def test_query_dispatch_end_to_end(self):
        _, query_bus = _build_buses("fake_app")
        result = await query_bus.dispatch(GetItemQuery(item_id=42))
        assert result == "item:42"

    async def test_all_discovered_handlers_registered(self):
        command_bus, query_bus = _build_buses("fake_app")
        # Two command handlers (CreateItemHandler + SharedCommandHandler)
        assert len(command_bus._handlers) == 2
        # One query handler (GetItemHandler)
        assert len(query_bus._handlers) == 1

    async def test_unregistered_command_raises(self):
        from cqrs_bus.commands.command import Command

        class UnknownCommand(Command):
            pass

        command_bus, _ = _build_buses("fake_app")
        with pytest.raises(ValueError, match="No handler registered"):
            await command_bus.dispatch(UnknownCommand())

    async def test_dispatch_callback_called_during_integration(self):
        from unittest.mock import MagicMock

        calls: list[tuple] = []

        def on_dispatch(name: str, duration: float, exc: Exception | None) -> None:
            calls.append((name, duration, exc))

        registry = HandlerDiscovery("fake_app").discover_all_handlers()
        resolver = DependencyResolver()
        command_bus = CommandBus(on_dispatch=on_dispatch)

        for meta in registry.get_all_command_handlers():
            instance = resolver.create_handler_instance(meta.handler_class, {})
            command_bus.register(meta.command_or_query_type, instance)

        await command_bus.dispatch(CreateItemCommand(name="test"))

        assert len(calls) == 1
        name, duration, exc = calls[0]
        assert name == "CreateItemCommand"
        assert duration >= 0
        assert exc is None
