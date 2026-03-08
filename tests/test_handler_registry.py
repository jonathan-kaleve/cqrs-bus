import pytest

from cqrs_bus.discovery.exceptions import DuplicateHandlerError
from cqrs_bus.discovery.handler_registry import HandlerMetadata, HandlerRegistry


def _make_metadata(handler_class, command_or_query_type):
    return HandlerMetadata(
        handler_class=handler_class,
        command_or_query_type=command_or_query_type,
        dependencies={},
        module_path="some.module",
    )


class FakeCommandType:
    pass


class AnotherCommandType:
    pass


class FakeQueryType:
    pass


class FakeHandler:
    pass


class AnotherHandler:
    pass


class TestHandlerRegistryCommands:
    def test_register_command_handler(self):
        registry = HandlerRegistry()
        meta = _make_metadata(FakeHandler, FakeCommandType)
        registry.register_command_handler(meta)
        assert registry.get_command_handler_count() == 1

    def test_register_duplicate_command_raises(self):
        registry = HandlerRegistry()
        registry.register_command_handler(_make_metadata(FakeHandler, FakeCommandType))
        with pytest.raises(DuplicateHandlerError, match="Multiple handlers found for FakeCommandType"):
            registry.register_command_handler(_make_metadata(AnotherHandler, FakeCommandType))

    def test_register_different_command_types(self):
        registry = HandlerRegistry()
        registry.register_command_handler(_make_metadata(FakeHandler, FakeCommandType))
        registry.register_command_handler(_make_metadata(AnotherHandler, AnotherCommandType))
        assert registry.get_command_handler_count() == 2

    def test_get_all_command_handlers_returns_list(self):
        registry = HandlerRegistry()
        meta = _make_metadata(FakeHandler, FakeCommandType)
        registry.register_command_handler(meta)
        result = registry.get_all_command_handlers()
        assert isinstance(result, list)
        assert result[0] is meta

    def test_get_command_handler_count_empty(self):
        registry = HandlerRegistry()
        assert registry.get_command_handler_count() == 0


class TestHandlerRegistryQueries:
    def test_register_query_handler(self):
        registry = HandlerRegistry()
        meta = _make_metadata(FakeHandler, FakeQueryType)
        registry.register_query_handler(meta)
        assert registry.get_query_handler_count() == 1

    def test_register_duplicate_query_raises(self):
        registry = HandlerRegistry()
        registry.register_query_handler(_make_metadata(FakeHandler, FakeQueryType))
        with pytest.raises(DuplicateHandlerError, match="Multiple handlers found for FakeQueryType"):
            registry.register_query_handler(_make_metadata(AnotherHandler, FakeQueryType))

    def test_get_all_query_handlers_returns_list(self):
        registry = HandlerRegistry()
        meta = _make_metadata(FakeHandler, FakeQueryType)
        registry.register_query_handler(meta)
        result = registry.get_all_query_handlers()
        assert isinstance(result, list)
        assert result[0] is meta

    def test_get_query_handler_count_empty(self):
        registry = HandlerRegistry()
        assert registry.get_query_handler_count() == 0

    def test_command_and_query_registries_are_independent(self):
        registry = HandlerRegistry()
        registry.register_command_handler(_make_metadata(FakeHandler, FakeCommandType))
        registry.register_query_handler(_make_metadata(FakeHandler, FakeQueryType))
        assert registry.get_command_handler_count() == 1
        assert registry.get_query_handler_count() == 1
        # Same command type registered as a query should not conflict (separate dicts)
        registry.register_query_handler(_make_metadata(AnotherHandler, FakeCommandType))
        assert registry.get_query_handler_count() == 2
