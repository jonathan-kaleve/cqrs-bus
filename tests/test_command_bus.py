import logging
from unittest.mock import MagicMock, patch

import pytest

import cqrs_bus.commands.command_bus as cmd_module
from cqrs_bus.commands.command import Command, CommandHandler
from cqrs_bus.commands.command_bus import CommandBus


class SampleCommand(Command):
    def __init__(self, value: int = 0):
        self.value = value


class AnotherCommand(Command):
    pass


class SampleHandler(CommandHandler[SampleCommand, int]):
    async def handle(self, command: SampleCommand) -> int:
        return command.value * 2


class AnotherHandler(CommandHandler[AnotherCommand, None]):
    async def handle(self, command: AnotherCommand) -> None:
        return None


class ErrorHandler(CommandHandler[SampleCommand, int]):
    async def handle(self, command: SampleCommand) -> int:
        raise RuntimeError("boom")


class TestCommandBusRegister:
    def test_register_handler_succeeds(self):
        bus = CommandBus()
        bus.register(SampleCommand, SampleHandler())
        assert SampleCommand in bus._handlers

    def test_register_duplicate_raises(self):
        bus = CommandBus()
        bus.register(SampleCommand, SampleHandler())
        with pytest.raises(ValueError, match="Handler already registered for command type SampleCommand"):
            bus.register(SampleCommand, SampleHandler())

    def test_register_multiple_command_types(self):
        bus = CommandBus()
        bus.register(SampleCommand, SampleHandler())
        bus.register(AnotherCommand, AnotherHandler())
        assert len(bus._handlers) == 2


class TestCommandBusDispatch:
    async def test_dispatch_returns_result(self):
        bus = CommandBus()
        bus.register(SampleCommand, SampleHandler())
        result = await bus.dispatch(SampleCommand(value=5))
        assert result == 10

    async def test_dispatch_unregistered_raises(self):
        bus = CommandBus()
        with pytest.raises(ValueError, match="No handler registered for command type SampleCommand"):
            await bus.dispatch(SampleCommand())

    async def test_dispatch_propagates_handler_exception(self):
        bus = CommandBus()
        bus.register(SampleCommand, ErrorHandler())
        with pytest.raises(RuntimeError, match="boom"):
            await bus.dispatch(SampleCommand())

    async def test_on_dispatch_callback_called_on_success(self):
        callback = MagicMock()
        bus = CommandBus(on_dispatch=callback)
        bus.register(SampleCommand, SampleHandler())
        await bus.dispatch(SampleCommand(value=3))

        callback.assert_called_once()
        name, duration, exc = callback.call_args[0]
        assert name == "SampleCommand"
        assert isinstance(duration, float)
        assert duration >= 0
        assert exc is None

    async def test_on_dispatch_callback_called_on_error(self):
        callback = MagicMock()
        bus = CommandBus(on_dispatch=callback)
        bus.register(SampleCommand, ErrorHandler())

        with pytest.raises(RuntimeError):
            await bus.dispatch(SampleCommand())

        callback.assert_called_once()
        name, duration, exc = callback.call_args[0]
        assert name == "SampleCommand"
        assert isinstance(exc, RuntimeError)

    async def test_no_callback_works(self):
        bus = CommandBus()
        bus.register(SampleCommand, SampleHandler())
        result = await bus.dispatch(SampleCommand(value=1))
        assert result == 2

    async def test_slow_command_logs_info(self, caplog):
        class SlowHandler(CommandHandler[SampleCommand, None]):
            async def handle(self, command: SampleCommand) -> None:
                return None

        bus = CommandBus()
        bus.register(SampleCommand, SlowHandler())

        with patch("cqrs_bus.commands.command_bus.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 2.0]
            with caplog.at_level(logging.INFO, logger="cqrs_bus.commands.command_bus"):
                await bus.dispatch(SampleCommand())

        assert any("Slow command" in r.message for r in caplog.records)

    async def test_fast_command_does_not_log_slow(self, caplog):
        bus = CommandBus()
        bus.register(SampleCommand, SampleHandler())

        with caplog.at_level(logging.INFO, logger="cqrs_bus.commands.command_bus"):
            await bus.dispatch(SampleCommand(value=1))

        assert not any("Slow command" in r.message for r in caplog.records)

    async def test_prometheus_increments_total_and_duration_on_success(self, monkeypatch):
        mock_histogram = MagicMock()
        mock_total = MagicMock()
        mock_errors = MagicMock()
        monkeypatch.setattr(cmd_module, "_prometheus", True, raising=False)
        monkeypatch.setattr(cmd_module, "_command_duration", mock_histogram, raising=False)
        monkeypatch.setattr(cmd_module, "_command_total", mock_total, raising=False)
        monkeypatch.setattr(cmd_module, "_command_errors", mock_errors, raising=False)

        bus = CommandBus()
        bus.register(SampleCommand, SampleHandler())
        await bus.dispatch(SampleCommand(value=2))

        mock_total.labels.assert_called_once_with(command_type="SampleCommand")
        mock_total.labels.return_value.inc.assert_called_once()
        mock_histogram.labels.assert_called_once_with(command_type="SampleCommand")
        mock_histogram.labels.return_value.observe.assert_called_once()
        mock_errors.labels.assert_not_called()

    async def test_prometheus_increments_errors_on_failure(self, monkeypatch):
        mock_histogram = MagicMock()
        mock_total = MagicMock()
        mock_errors = MagicMock()
        monkeypatch.setattr(cmd_module, "_prometheus", True, raising=False)
        monkeypatch.setattr(cmd_module, "_command_duration", mock_histogram, raising=False)
        monkeypatch.setattr(cmd_module, "_command_total", mock_total, raising=False)
        monkeypatch.setattr(cmd_module, "_command_errors", mock_errors, raising=False)

        bus = CommandBus()
        bus.register(SampleCommand, ErrorHandler())

        with pytest.raises(RuntimeError):
            await bus.dispatch(SampleCommand())

        mock_errors.labels.assert_called_once_with(command_type="SampleCommand", error_type="RuntimeError")
        mock_errors.labels.return_value.inc.assert_called_once()
        mock_histogram.labels.assert_not_called()
