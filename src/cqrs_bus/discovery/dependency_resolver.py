import inspect
from typing import Any, Union, get_args, get_origin

from cqrs_bus.discovery.exceptions import MissingDependencyError

_SENTINEL = object()


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

    def resolve_dependencies(self, handler_class: type, dependency_map: dict[Any, Any]) -> dict[str, Any]:
        try:
            sig = inspect.signature(handler_class.__init__)  # type: ignore[misc]
        except (ValueError, TypeError) as e:
            raise MissingDependencyError(f"Failed to inspect {handler_class.__name__}.__init__: {e}")

        resolved = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            annotation = param.annotation
            has_default = param.default is not inspect.Parameter.empty

            value = self._lookup(annotation, dependency_map)

            if value is _SENTINEL:
                if has_default:
                    continue
                raise MissingDependencyError(
                    f"{handler_class.__name__} parameter '{param_name}: {annotation!r}' "
                    f"is not registered in dependency_map"
                )

            resolved[param_name] = value

        return resolved

    def _lookup(self, annotation: Any, dependency_map: dict[Any, Any]) -> Any:
        # 1. Exact match — covers concrete types, ABCs, Protocols, and generic
        #    aliases like Callable[[], UnitOfWork] which are hashable and equality-comparable
        if annotation in dependency_map:
            return dependency_map[annotation]

        # 2. Unwrap Union (X | Y, Optional[X]) — try each member in order
        if get_origin(annotation) is Union:
            for arg in get_args(annotation):
                if arg in dependency_map:
                    return dependency_map[arg]

        # 3. Subclass fallback for ABCs and base classes
        if isinstance(annotation, type):
            for registered_type, value in dependency_map.items():
                if isinstance(registered_type, type):
                    try:
                        if issubclass(annotation, registered_type):
                            return value
                    except TypeError:
                        pass

        return _SENTINEL

    def create_handler_instance(self, handler_class: type, dependency_map: dict[Any, Any]) -> Any:
        resolved_deps = self.resolve_dependencies(handler_class, dependency_map)

        try:
            return handler_class(**resolved_deps)
        except TypeError as e:
            raise MissingDependencyError(
                f"Failed to instantiate {handler_class.__name__}: {e}. "
                f"Check that constructor parameters match resolved dependencies."
            )
