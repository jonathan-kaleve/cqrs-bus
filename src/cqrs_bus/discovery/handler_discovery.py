import importlib
import inspect
import logging
import pkgutil
import traceback
from abc import ABC
from typing import Any, get_args, get_origin

from cqrs_bus.commands.command import CommandHandler
from cqrs_bus.discovery.dependency_resolver import DependencyResolver
from cqrs_bus.discovery.exceptions import InvalidHandlerError
from cqrs_bus.discovery.handler_registry import HandlerMetadata, HandlerRegistry
from cqrs_bus.queries.query import QueryHandler

logger = logging.getLogger(__name__)


class HandlerDiscovery:
    def __init__(self, base_package: str, strict: bool = False):
        if not all(part.isidentifier() for part in base_package.split(".")):
            raise ValueError(
                f"Invalid base_package '{base_package}': must be a valid Python package path "
                f"(e.g. 'myapp.handlers')"
            )
        self.base_package = base_package
        self.strict = strict
        self.registry = HandlerRegistry()
        self.resolver = DependencyResolver()

    def discover_all_handlers(self) -> HandlerRegistry:
        logger.info(f"Starting handler discovery in {self.base_package}")

        for metadata in self._scan_for_handlers("commands", CommandHandler):
            self.registry.register_command_handler(metadata)

        for metadata in self._scan_for_handlers("queries", QueryHandler):
            self.registry.register_query_handler(metadata)

        logger.info(
            f"Handler discovery complete: "
            f"{self.registry.get_command_handler_count()} commands, "
            f"{self.registry.get_query_handler_count()} queries"
        )

        return self.registry

    def _scan_for_handlers(self, subdir: str, base_class: type) -> list[HandlerMetadata]:
        handlers: list[Any] = []

        try:
            base_module = importlib.import_module(self.base_package)
        except ImportError as e:
            logger.error("Failed to import base package %s: %s", self.base_package, e)
            return handlers

        if not hasattr(base_module, "__path__"):
            logger.error("Base package %s has no __path__", self.base_package)
            return handlers

        for _importer, module_name, _is_pkg in pkgutil.walk_packages(
            base_module.__path__, prefix=f"{self.base_package}."
        ):
            module_parts = module_name.split(".")
            if subdir not in module_parts:
                continue

            try:
                module = importlib.import_module(module_name)
                handlers.extend(self._scan_module(module, module_name, base_class))
            except ImportError as e:
                logger.error("Failed to import %s: %s", module_name, e)
                logger.debug(traceback.format_exc())
                if self.strict:
                    raise
            except Exception as e:
                logger.error("Unexpected error scanning %s: %s", module_name, e)
                logger.debug(traceback.format_exc())
                if self.strict:
                    raise

        return handlers

    def _scan_module(self, module: Any, module_name: str, base_class: type) -> list[HandlerMetadata]:
        handlers = []

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not self._is_valid_handler(obj, base_class, module_name):
                continue

            try:
                command_or_query_type = self._extract_command_or_query_type(obj)
                dependencies = self.resolver.inspect_handler_init(obj)

                metadata = HandlerMetadata(
                    handler_class=obj,
                    command_or_query_type=command_or_query_type,
                    dependencies=dependencies,
                    module_path=module_name,
                )

                handlers.append(metadata)
                logger.debug(f"Discovered {obj.__name__} for {command_or_query_type.__name__} deps={dependencies}")

            except Exception as e:
                logger.error("Error processing handler %s in %s: %s", name, module_name, e)
                logger.debug(traceback.format_exc())
                if self.strict:
                    raise

        return handlers

    def _is_valid_handler(self, cls: type, base_class: type, module_name: str) -> bool:
        try:
            if not issubclass(cls, base_class):
                return False
        except TypeError:
            return False

        if cls is base_class:
            return False

        if ABC in cls.__bases__ or inspect.isabstract(cls):
            return False

        if cls.__module__ != module_name:
            logger.debug(
                "Skipping %s: defined in '%s', not '%s'",
                cls.__name__,
                cls.__module__,
                module_name,
            )
            return False

        return True

    def _extract_command_or_query_type(self, handler_class: type) -> type:
        if not hasattr(handler_class, "__orig_bases__"):
            raise InvalidHandlerError(
                f"{handler_class.__name__} does not have __orig_bases__. "
                f"Ensure it properly inherits from CommandHandler or QueryHandler."
            )

        for base in handler_class.__orig_bases__:
            origin = get_origin(base)

            if origin in (CommandHandler, QueryHandler):
                args = get_args(base)
                if args:
                    return args[0]

            if origin is not None:
                try:
                    if issubclass(origin, (CommandHandler, QueryHandler)):
                        args = get_args(base)
                        if args:
                            return args[0]
                except TypeError:
                    pass

        raise InvalidHandlerError(
            f"{handler_class.__name__} does not properly specify Command/Query type in generic parameters"
        )
