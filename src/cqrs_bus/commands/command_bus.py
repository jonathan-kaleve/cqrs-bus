import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import uuid4

from cqrs_bus.commands.command import Command, CommandHandler

logger = logging.getLogger(__name__)

TCommand = TypeVar("TCommand", bound=Command)

try:
    from prometheus_client import Counter, Histogram

    _command_duration = Histogram(
        "command_duration_seconds",
        "Command handler execution duration",
        ["command_type"],
    )
    _command_errors = Counter(
        "command_errors_total",
        "Total command handler errors",
        ["command_type", "error_type"],
    )
    _command_total = Counter(
        "command_executions_total",
        "Total command executions",
        ["command_type"],
    )
    _prometheus = True
except ImportError:
    _prometheus = False


class CommandBus:
    def __init__(self, on_dispatch: Callable[[str, float, Exception | None], None] | None = None):
        self._handlers: dict[type[Command], CommandHandler] = {}
        self._on_dispatch = on_dispatch

    def register(self, command_type: type[TCommand], handler: CommandHandler[TCommand, Any]) -> None:
        if command_type in self._handlers:
            raise ValueError(f"Handler already registered for command type {command_type.__name__}")
        self._handlers[command_type] = handler

    async def dispatch(self, command: TCommand) -> Any:
        command_type = type(command)
        command_name = command_type.__name__
        command_id = str(uuid4())[:8]

        if command_type not in self._handlers:
            logger.error(
                f"[CommandBus] No handler registered for {command_name}",
                extra={"command_id": command_id, "command_type": command_name},
            )
            raise ValueError(f"No handler registered for command type {command_name}")

        handler = self._handlers[command_type]
        handler_name = type(handler).__name__

        logger.debug(
            f"[CommandBus] Dispatching {command_name} to {handler_name}",
            extra={"command_id": command_id, "command_type": command_name, "handler_type": handler_name},
        )

        if _prometheus:
            _command_total.labels(command_type=command_name).inc()

        start_time = time.time()

        try:
            result = await handler.handle(command)
            duration = time.time() - start_time

            if _prometheus:
                _command_duration.labels(command_type=command_name).observe(duration)

            if self._on_dispatch:
                self._on_dispatch(command_name, duration, None)

            if duration > 1.0:
                logger.info(
                    f"[CommandBus] Slow command: {command_name} ({duration:.3f}s)",
                    extra={"command_id": command_id, "command_type": command_name, "duration_seconds": duration},
                )
            else:
                logger.debug(
                    f"[CommandBus] Success: {command_name} ({duration:.3f}s)",
                    extra={"command_id": command_id, "command_type": command_name, "duration_seconds": duration},
                )

            return result

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__

            if _prometheus:
                _command_errors.labels(command_type=command_name, error_type=error_type).inc()

            if self._on_dispatch:
                self._on_dispatch(command_name, duration, e)

            logger.error(
                f"[CommandBus] Failed: {command_name} - {error_type}: {str(e)[:200]}",
                extra={"command_id": command_id, "command_type": command_name, "error_type": error_type},
                exc_info=True,
            )
            raise
