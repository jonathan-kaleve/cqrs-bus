import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import uuid4

from cqrs_bus.queries.query import Query, QueryHandler

logger = logging.getLogger(__name__)

TQuery = TypeVar("TQuery", bound=Query)

try:
    from prometheus_client import Counter, Histogram

    _query_duration = Histogram(
        "query_duration_seconds",
        "Query handler execution duration",
        ["query_type"],
    )
    _query_errors = Counter(
        "query_errors_total",
        "Total query handler errors",
        ["query_type", "error_type"],
    )
    _query_total = Counter(
        "query_executions_total",
        "Total query executions",
        ["query_type"],
    )
    _prometheus = True
except ImportError:
    _prometheus = False


class QueryBus:
    def __init__(self, on_dispatch: Callable[[str, float, Exception | None], None] | None = None):
        self._handlers: dict[type[Query], QueryHandler] = {}
        self._on_dispatch = on_dispatch

    def register(self, query_type: type[TQuery], handler: QueryHandler[TQuery, Any]) -> None:
        if query_type in self._handlers:
            raise ValueError(f"Handler already registered for query type {query_type.__name__}")
        self._handlers[query_type] = handler

    async def dispatch(self, query: TQuery) -> Any:
        query_type = type(query)
        query_name = query_type.__name__
        query_id = str(uuid4())

        if query_type not in self._handlers:
            logger.error(
                f"[QueryBus] No handler registered for {query_name}",
                extra={"query_id": query_id, "query_type": query_name},
            )
            raise ValueError(f"No handler registered for query type {query_name}")

        handler = self._handlers[query_type]
        handler_name = type(handler).__name__

        logger.debug(
            f"[QueryBus] Dispatching {query_name} to {handler_name}",
            extra={"query_id": query_id, "query_type": query_name, "handler_type": handler_name},
        )

        if _prometheus:
            _query_total.labels(query_type=query_name).inc()

        start_time = time.time()

        try:
            result = await handler.handle(query)
            duration = time.time() - start_time

            if _prometheus:
                _query_duration.labels(query_type=query_name).observe(duration)

            if self._on_dispatch:
                self._on_dispatch(query_name, duration, None)

            logger.debug(
                f"[QueryBus] Success: {query_name} ({duration:.3f}s)",
                extra={"query_id": query_id, "query_type": query_name, "duration_seconds": duration},
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__

            if _prometheus:
                _query_errors.labels(query_type=query_name, error_type=error_type).inc()

            if self._on_dispatch:
                self._on_dispatch(query_name, duration, e)

            logger.error(
                "[QueryBus] Failed: %s - %s",
                query_name,
                error_type,
                extra={"query_id": query_id, "query_type": query_name, "error_type": error_type},
                exc_info=True,
            )
            raise
