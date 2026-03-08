import inspect
from typing import Any

from cqrs_bus.discovery.exceptions import MissingDependencyError


class DependencyResolver:
    def inspect_handler_init(self, handler_class: type) -> list[str]:
        try:
            sig = inspect.signature(handler_class.__init__)  # type: ignore[misc]
        except (ValueError, TypeError) as e:
            raise MissingDependencyError(f"Failed to inspect {handler_class.__name__}.__init__: {e}")

        dependencies = []

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

            dependencies.append(param_name)

        return dependencies

    def resolve_dependencies(self, handler_class: type, dependency_map: dict[str, Any]) -> dict[str, Any]:
        required_deps = self.inspect_handler_init(handler_class)
        resolved = {}

        for dep_name in required_deps:
            if dep_name not in dependency_map:
                raise MissingDependencyError(
                    f"{handler_class.__name__} requires '{dep_name}' but it was not provided in dependency_map"
                )
            resolved[dep_name] = dependency_map[dep_name]

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
