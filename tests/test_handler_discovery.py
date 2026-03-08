import importlib
from abc import abstractmethod
from unittest.mock import MagicMock, patch

import pytest

from cqrs_bus.commands.command import Command, CommandHandler
from cqrs_bus.discovery.exceptions import InvalidHandlerError
from cqrs_bus.discovery.handler_discovery import HandlerDiscovery
from cqrs_bus.queries.query import Query, QueryHandler


# ---------------------------------------------------------------------------
# Helpers used in multiple test classes
# ---------------------------------------------------------------------------


class _SampleCommand(Command):
    pass


class _SampleQuery(Query):
    pass


# ---------------------------------------------------------------------------
# discover_all_handlers — happy path using the fake_app fixture package
# ---------------------------------------------------------------------------


class TestDiscoverAllHandlers:
    def test_discovers_command_handlers(self):
        discovery = HandlerDiscovery("fake_app")
        registry = discovery.discover_all_handlers()
        # fake_app/commands/ has CreateItemHandler
        # fake_app/shared/commands/ has SharedCommandHandler
        assert registry.get_command_handler_count() == 2

    def test_discovers_query_handlers(self):
        discovery = HandlerDiscovery("fake_app")
        registry = discovery.discover_all_handlers()
        # fake_app/queries/ has GetItemHandler
        assert registry.get_query_handler_count() == 1

    def test_shared_commands_excluded_from_queries(self):
        # SharedCommandHandler lives in shared/commands — must not appear as a query handler
        discovery = HandlerDiscovery("fake_app")
        registry = discovery.discover_all_handlers()
        query_classes = {m.handler_class.__name__ for m in registry.get_all_query_handlers()}
        assert "SharedCommandHandler" not in query_classes

    def test_invalid_package_returns_empty_registry(self):
        discovery = HandlerDiscovery("nonexistent_package_xyz")
        registry = discovery.discover_all_handlers()
        assert registry.get_command_handler_count() == 0
        assert registry.get_query_handler_count() == 0

    def test_non_package_module_returns_empty(self):
        # A module with no __path__ (i.e. a plain .py file, not a package)
        discovery = HandlerDiscovery("os.path")
        registry = discovery.discover_all_handlers()
        assert registry.get_command_handler_count() == 0
        assert registry.get_query_handler_count() == 0


# ---------------------------------------------------------------------------
# _is_valid_handler
# ---------------------------------------------------------------------------


class TestIsValidHandler:
    def setup_method(self):
        self.discovery = HandlerDiscovery("fake_app")

    def test_valid_concrete_command_handler(self):
        class MyHandler(CommandHandler[_SampleCommand, str]):
            async def handle(self, command: _SampleCommand) -> str:
                return "ok"

        assert self.discovery._is_valid_handler(MyHandler, CommandHandler, MyHandler.__module__)

    def test_rejects_base_class_itself(self):
        assert not self.discovery._is_valid_handler(CommandHandler, CommandHandler, CommandHandler.__module__)

    def test_rejects_abstract_class_with_abc_in_bases(self):
        from abc import ABC

        class AbstractHandler(CommandHandler[_SampleCommand, str], ABC):
            pass

        assert not self.discovery._is_valid_handler(AbstractHandler, CommandHandler, AbstractHandler.__module__)

    def test_rejects_class_with_unimplemented_abstract_method(self):
        class IncompleteHandler(CommandHandler[_SampleCommand, str]):
            # does not implement handle()
            pass

        assert not self.discovery._is_valid_handler(
            IncompleteHandler, CommandHandler, IncompleteHandler.__module__
        )

    def test_rejects_non_handler_class(self):
        class NotAHandler:
            pass

        assert not self.discovery._is_valid_handler(NotAHandler, CommandHandler, NotAHandler.__module__)

    def test_rejects_handler_from_different_module(self):
        class MyHandler(CommandHandler[_SampleCommand, str]):
            async def handle(self, command: _SampleCommand) -> str:
                return "ok"

        assert not self.discovery._is_valid_handler(MyHandler, CommandHandler, "some.other.module")

    def test_rejects_query_handler_when_checking_for_command_handler(self):
        class MyQueryHandler(QueryHandler[_SampleQuery, str]):
            async def handle(self, query: _SampleQuery) -> str:
                return "ok"

        assert not self.discovery._is_valid_handler(MyQueryHandler, CommandHandler, MyQueryHandler.__module__)


# ---------------------------------------------------------------------------
# _extract_command_or_query_type
# ---------------------------------------------------------------------------


class TestExtractCommandOrQueryType:
    def setup_method(self):
        self.discovery = HandlerDiscovery("fake_app")

    def test_extracts_command_type(self):
        class MyHandler(CommandHandler[_SampleCommand, str]):
            async def handle(self, command: _SampleCommand) -> str:
                return "ok"

        assert self.discovery._extract_command_or_query_type(MyHandler) is _SampleCommand

    def test_extracts_query_type(self):
        class MyHandler(QueryHandler[_SampleQuery, int]):
            async def handle(self, query: _SampleQuery) -> int:
                return 0

        assert self.discovery._extract_command_or_query_type(MyHandler) is _SampleQuery

    def test_raises_when_no_orig_bases(self):
        class BadHandler:
            __orig_bases__ = ()  # empty — loop runs zero iterations, raises at end

        with pytest.raises(InvalidHandlerError):
            self.discovery._extract_command_or_query_type(BadHandler)

    def test_raises_when_orig_bases_do_not_match(self):
        class Unrelated:
            pass

        class BadHandler(Unrelated):
            pass

        # __orig_bases__ won't have CommandHandler or QueryHandler as origin
        with pytest.raises(InvalidHandlerError):
            self.discovery._extract_command_or_query_type(BadHandler)


# ---------------------------------------------------------------------------
# Error resilience during scanning
# ---------------------------------------------------------------------------


class TestScanErrorResilience:
    def test_import_error_during_scan_is_logged_not_raised(self, caplog):
        import logging

        discovery = HandlerDiscovery("fake_app")

        original_import = importlib.import_module

        def failing_import(name, *args, **kwargs):
            if name == "fake_app.commands.create_item_handler":
                raise ImportError("simulated import failure")
            return original_import(name, *args, **kwargs)

        with patch("cqrs_bus.discovery.handler_discovery.importlib.import_module", side_effect=failing_import):
            with caplog.at_level(logging.ERROR, logger="cqrs_bus.discovery.handler_discovery"):
                registry = discovery.discover_all_handlers()

        assert any("Failed to import" in r.message for r in caplog.records)
        # Other handlers should still be discovered despite the one failure
        assert registry.get_query_handler_count() == 1

    def test_unexpected_error_during_scan_is_logged_not_raised(self, caplog):
        import logging

        discovery = HandlerDiscovery("fake_app")

        original_import = importlib.import_module

        def broken_import(name, *args, **kwargs):
            if name == "fake_app.commands.create_item_handler":
                raise RuntimeError("unexpected error")
            return original_import(name, *args, **kwargs)

        with patch("cqrs_bus.discovery.handler_discovery.importlib.import_module", side_effect=broken_import):
            with caplog.at_level(logging.ERROR, logger="cqrs_bus.discovery.handler_discovery"):
                discovery.discover_all_handlers()

        assert any("Unexpected error" in r.message for r in caplog.records)
