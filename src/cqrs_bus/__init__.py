from cqrs_bus.commands.command import Command, CommandHandler, TCommand
from cqrs_bus.commands.command_bus import CommandBus
from cqrs_bus.discovery.dependency_resolver import DependencyResolver
from cqrs_bus.discovery.exceptions import (
    DuplicateHandlerError,
    HandlerDiscoveryError,
    InvalidHandlerError,
    MissingDependencyError,
)
from cqrs_bus.discovery.handler_discovery import HandlerDiscovery
from cqrs_bus.discovery.handler_registry import HandlerMetadata, HandlerRegistry
from cqrs_bus.queries.query import Query, QueryHandler, TQuery
from cqrs_bus.queries.query_bus import QueryBus
from typing import TypeVar

TResult = TypeVar("TResult")

__all__ = [
    "Command",
    "CommandHandler",
    "CommandBus",
    "TCommand",
    "Query",
    "QueryHandler",
    "QueryBus",
    "TQuery",
    "TResult",
    "HandlerDiscovery",
    "HandlerRegistry",
    "HandlerMetadata",
    "DependencyResolver",
    "HandlerDiscoveryError",
    "MissingDependencyError",
    "DuplicateHandlerError",
    "InvalidHandlerError",
]
