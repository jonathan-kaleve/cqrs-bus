import logging
from unittest.mock import MagicMock, patch

import pytest

import cqrs_bus.queries.query_bus as qry_module
from cqrs_bus.queries.query import Query, QueryHandler
from cqrs_bus.queries.query_bus import QueryBus


class SampleQuery(Query):
    def __init__(self, value: int = 0):
        self.value = value


class AnotherQuery(Query):
    pass


class SampleHandler(QueryHandler[SampleQuery, int]):
    async def handle(self, query: SampleQuery) -> int:
        return query.value * 3


class AnotherHandler(QueryHandler[AnotherQuery, None]):
    async def handle(self, query: AnotherQuery) -> None:
        return None


class ErrorHandler(QueryHandler[SampleQuery, int]):
    async def handle(self, query: SampleQuery) -> int:
        raise ValueError("query failed")


class TestQueryBusRegister:
    def test_register_handler_succeeds(self):
        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())
        assert SampleQuery in bus._handlers

    def test_register_duplicate_raises(self):
        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())
        with pytest.raises(ValueError, match="Handler already registered for query type SampleQuery"):
            bus.register(SampleQuery, SampleHandler())

    def test_register_multiple_query_types(self):
        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())
        bus.register(AnotherQuery, AnotherHandler())
        assert len(bus._handlers) == 2


class TestQueryBusDispatch:
    async def test_dispatch_returns_result(self):
        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())
        result = await bus.dispatch(SampleQuery(value=4))
        assert result == 12

    async def test_dispatch_unregistered_raises(self):
        bus = QueryBus()
        with pytest.raises(ValueError, match="No handler registered for query type SampleQuery"):
            await bus.dispatch(SampleQuery())

    async def test_dispatch_propagates_handler_exception(self):
        bus = QueryBus()
        bus.register(SampleQuery, ErrorHandler())
        with pytest.raises(ValueError, match="query failed"):
            await bus.dispatch(SampleQuery())

    async def test_on_dispatch_callback_called_on_success(self):
        callback = MagicMock()
        bus = QueryBus(on_dispatch=callback)
        bus.register(SampleQuery, SampleHandler())
        await bus.dispatch(SampleQuery(value=2))

        callback.assert_called_once()
        name, duration, exc = callback.call_args[0]
        assert name == "SampleQuery"
        assert isinstance(duration, float)
        assert exc is None

    async def test_on_dispatch_callback_called_on_error(self):
        callback = MagicMock()
        bus = QueryBus(on_dispatch=callback)
        bus.register(SampleQuery, ErrorHandler())

        with pytest.raises(ValueError):
            await bus.dispatch(SampleQuery())

        callback.assert_called_once()
        name, duration, exc = callback.call_args[0]
        assert name == "SampleQuery"
        assert isinstance(exc, ValueError)

    async def test_no_callback_works(self):
        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())
        result = await bus.dispatch(SampleQuery(value=1))
        assert result == 3

    async def test_prometheus_increments_total_and_duration_on_success(self, monkeypatch):
        mock_histogram = MagicMock()
        mock_total = MagicMock()
        mock_errors = MagicMock()
        monkeypatch.setattr(qry_module, "_prometheus", True, raising=False)
        monkeypatch.setattr(qry_module, "_query_duration", mock_histogram, raising=False)
        monkeypatch.setattr(qry_module, "_query_total", mock_total, raising=False)
        monkeypatch.setattr(qry_module, "_query_errors", mock_errors, raising=False)

        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())
        await bus.dispatch(SampleQuery(value=1))

        mock_total.labels.assert_called_once_with(query_type="SampleQuery")
        mock_total.labels.return_value.inc.assert_called_once()
        mock_histogram.labels.assert_called_once_with(query_type="SampleQuery")
        mock_histogram.labels.return_value.observe.assert_called_once()
        mock_errors.labels.assert_not_called()

    async def test_prometheus_increments_errors_on_failure(self, monkeypatch):
        mock_histogram = MagicMock()
        mock_total = MagicMock()
        mock_errors = MagicMock()
        monkeypatch.setattr(qry_module, "_prometheus", True, raising=False)
        monkeypatch.setattr(qry_module, "_query_duration", mock_histogram, raising=False)
        monkeypatch.setattr(qry_module, "_query_total", mock_total, raising=False)
        monkeypatch.setattr(qry_module, "_query_errors", mock_errors, raising=False)

        bus = QueryBus()
        bus.register(SampleQuery, ErrorHandler())

        with pytest.raises(ValueError):
            await bus.dispatch(SampleQuery())

        mock_errors.labels.assert_called_once_with(query_type="SampleQuery", error_type="ValueError")
        mock_errors.labels.return_value.inc.assert_called_once()
        mock_histogram.labels.assert_not_called()

    async def test_success_logs_debug(self, caplog):
        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())

        with caplog.at_level(logging.DEBUG, logger="cqrs_bus.queries.query_bus"):
            await bus.dispatch(SampleQuery(value=1))

        assert any("Success" in r.message for r in caplog.records)

    async def test_slow_query_does_not_emit_slow_log(self, caplog):
        # QueryBus has no slow-query detection (unlike CommandBus); verify no "Slow" log
        bus = QueryBus()
        bus.register(SampleQuery, SampleHandler())

        with patch("cqrs_bus.queries.query_bus.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 5.0]
            with caplog.at_level(logging.INFO, logger="cqrs_bus.queries.query_bus"):
                await bus.dispatch(SampleQuery(value=1))

        assert not any("Slow" in r.message for r in caplog.records)
