import inspect
import logging
from typing import Any, get_origin

from cqrs_bus.discovery.exceptions import MissingDependencyError

logger = logging.getLogger(__name__)


class DependencyResolver:
    def inspect_handler_init(self, handler_class: type) -> dict[str, type]:
        try:
            sig = inspect.signature(handler_class.__init__)  # type: ignore[misc]
        except (ValueError, TypeError) as e:
            raise MissingDependencyError(f"Failed to inspect {handler_class.__name__}.__init__: {e}")

        dependencies: dict[str, type] = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            if param.annotation == inspect.Parameter.empty:
                raise MissingDependencyError(
                    f"{handler_class.__name__}.__init__ parameter '{param_name}' "
                    f"is missing type annotation. Add type hint for automatic dependency injection."
                )

            dependencies[param_name] = param.annotation

        return dependencies

    def resolve_dependencies(self, handler_class: type, dependency_map: dict[str, Any]) -> dict[str, Any]:
        required_deps = self.inspect_handler_init(handler_class)
        resolved = {}

        for dep_name, dep_type in required_deps.items():
            if dep_name not in dependency_map:
                raise MissingDependencyError(
                    f"{handler_class.__name__} requires '{dep_name}' but it was not provided in dependency_map"
                )

            value = dependency_map[dep_name]

            # Runtime type check — skip for generic aliases (e.g. list[str]) that isinstance can't handle
            if get_origin(dep_type) is None and isinstance(dep_type, type):
                try:
                    if not isinstance(value, dep_type):
                        logger.warning(
                            "%s: dependency '%s' expected %s but got %s",
                            handler_class.__name__,
                            dep_name,
                            dep_type.__name__,
                            type(value).__name__,
                        )
                except TypeError:
                    pass

            resolved[dep_name] = value

        return resolved

    def create_handler_instance(self, handler_class: type, dependency_map: dict[str, Any]) -> Any:
        resolved_deps = self.resolve_dependencies(handler_class, dependency_map)

        try:
            return handler_class(**resolved_deps)
        except TypeError as e:
            raise MissingDependencyError(
                f"Failed to instantiate {handler_class.__name__}: {e}. "
                f"Check that constructor parameters match resolved dependencies."
            )
