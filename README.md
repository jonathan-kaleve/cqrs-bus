# cqrs-bus

An async CQRS command/query bus for Python with handler auto-discovery.

The idea is simple: your app dispatches commands and queries without knowing anything about what handles them. Handlers live in their own modules, get picked up automatically at startup, and dependencies are resolved from their `__init__` signatures. No decorators, no registries you have to maintain by hand.

## Installation

```bash
pip install cqrs-bus
```

With Prometheus metrics:

```bash
pip install "cqrs-bus[prometheus]"
```

## Quick start

Define a command and its handler:

```python
from cqrs_bus import Command, CommandHandler

class CreateOrder(Command):
    customer_id: str
    total: float

class CreateOrderHandler(CommandHandler[CreateOrder]):
    def __init__(self, db: Database):
        self.db = db

    async def handle(self, command: CreateOrder) -> str:
        order_id = await self.db.insert_order(command.customer_id, command.total)
        return order_id
```

Wire it up and dispatch:

```python
from cqrs_bus import CommandBus

bus = CommandBus()
bus.register(CreateOrder, CreateOrderHandler(db=my_db))

order_id = await bus.dispatch(CreateOrder(customer_id="c-123", total=49.99))
```

Queries work the same way, just using `Query` and `QueryHandler` instead.

## Auto-discovery

If you have more than a handful of handlers, use `HandlerDiscovery` instead of registering them manually. Point it at your handlers package and it scans for all concrete `CommandHandler` and `QueryHandler` subclasses:

```
myapp/
  handlers/
    commands/
      create_order.py   # contains CreateOrderHandler
      cancel_order.py   # contains CancelOrderHandler
    queries/
      get_order.py      # contains GetOrderHandler
```

```python
from cqrs_bus import HandlerDiscovery, CommandBus, QueryBus

discovery = HandlerDiscovery(base_package="myapp.handlers")
registry = discovery.discover_all_handlers()

command_bus = CommandBus()
query_bus = QueryBus()

for meta in registry.command_handlers.values():
    deps = {name: resolve(dep) for name, dep in meta.dependencies.items()}
    command_bus.register(meta.command_or_query_type, meta.handler_class(**deps))

for meta in registry.query_handlers.values():
    deps = {name: resolve(dep) for name, dep in meta.dependencies.items()}
    query_bus.register(meta.command_or_query_type, meta.handler_class(**deps))
```

Handler dependencies are inferred from type annotations in `__init__`. The `DependencyResolver` inspects each handler class and returns a `{param_name: type}` dict that you can use with whatever DI container or factory you already have.

## Observability

The bus logs at `DEBUG` for normal dispatches and `INFO` for anything that takes over a second. It logs at `ERROR` with full traceback on handler failures. All log records include `command_type` and `command_id` (a UUID generated per dispatch) as structured extras.

If `prometheus-client` is installed, the bus automatically tracks:

- `command_executions_total` / `query_executions_total`
- `command_duration_seconds` / `query_duration_seconds`
- `command_errors_total` / `query_errors_total`

No setup required — the metrics are registered on import.

You can also pass an `on_dispatch` callback to the bus constructor if you want to hook into your own telemetry:

```python
def my_hook(name: str, duration: float, error: Exception | None):
    ...

bus = CommandBus(on_dispatch=my_hook)
```

## Requirements

Python 3.11+. No runtime dependencies unless you opt into the `prometheus` extra.

## License

MIT
