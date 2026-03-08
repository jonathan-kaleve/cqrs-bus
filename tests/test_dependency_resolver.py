import pytest

from cqrs_bus.discovery.dependency_resolver import DependencyResolver
from cqrs_bus.discovery.exceptions import MissingDependencyError


class ServiceA:
    pass


class ServiceB:
    pass


class NoDepsHandler:
    def __init__(self):
        pass


class SingleDepHandler:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a


class MultiDepHandler:
    def __init__(self, service_a: ServiceA, service_b: ServiceB):
        self.service_a = service_a
        self.service_b = service_b


class MissingAnnotationHandler:
    def __init__(self, service_a):  # no type annotation
        self.service_a = service_a


class TestInspectHandlerInit:
    def test_no_dependencies(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(NoDepsHandler)
        assert deps == []

    def test_single_dependency(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(SingleDepHandler)
        assert deps == ["service_a"]

    def test_multiple_dependencies(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(MultiDepHandler)
        assert deps == ["service_a", "service_b"]

    def test_missing_annotation_raises(self):
        resolver = DependencyResolver()
        with pytest.raises(MissingDependencyError, match="missing type annotation"):
            resolver.inspect_handler_init(MissingAnnotationHandler)

    def test_uninspectable_class_raises(self):
        resolver = DependencyResolver()

        class BadInit:
            pass

        # Patch __init__ to raise TypeError on signature inspection
        BadInit.__init__ = None  # type: ignore[method-assign]
        with pytest.raises(MissingDependencyError, match="Failed to inspect"):
            resolver.inspect_handler_init(BadInit)


class TestResolveDependencies:
    def test_resolves_single_dependency(self):
        resolver = DependencyResolver()
        svc = ServiceA()
        resolved = resolver.resolve_dependencies(SingleDepHandler, {"service_a": svc})
        assert resolved == {"service_a": svc}

    def test_resolves_multiple_dependencies(self):
        resolver = DependencyResolver()
        svc_a, svc_b = ServiceA(), ServiceB()
        resolved = resolver.resolve_dependencies(MultiDepHandler, {"service_a": svc_a, "service_b": svc_b})
        assert resolved == {"service_a": svc_a, "service_b": svc_b}

    def test_ignores_extra_dependencies_in_map(self):
        resolver = DependencyResolver()
        svc = ServiceA()
        resolved = resolver.resolve_dependencies(SingleDepHandler, {"service_a": svc, "extra": object()})
        assert "extra" not in resolved
        assert resolved["service_a"] is svc

    def test_missing_dependency_raises(self):
        resolver = DependencyResolver()
        with pytest.raises(MissingDependencyError, match="requires 'service_a'"):
            resolver.resolve_dependencies(SingleDepHandler, {})

    def test_no_deps_returns_empty(self):
        resolver = DependencyResolver()
        resolved = resolver.resolve_dependencies(NoDepsHandler, {})
        assert resolved == {}


class TestCreateHandlerInstance:
    def test_creates_instance_no_deps(self):
        resolver = DependencyResolver()
        instance = resolver.create_handler_instance(NoDepsHandler, {})
        assert isinstance(instance, NoDepsHandler)

    def test_creates_instance_with_deps(self):
        resolver = DependencyResolver()
        svc_a, svc_b = ServiceA(), ServiceB()
        instance = resolver.create_handler_instance(MultiDepHandler, {"service_a": svc_a, "service_b": svc_b})
        assert isinstance(instance, MultiDepHandler)
        assert instance.service_a is svc_a
        assert instance.service_b is svc_b

    def test_missing_dep_raises(self):
        resolver = DependencyResolver()
        with pytest.raises(MissingDependencyError):
            resolver.create_handler_instance(SingleDepHandler, {})

    def test_wrong_constructor_args_raises(self):
        resolver = DependencyResolver()

        class StrictHandler:
            def __init__(self, count: int):
                if not isinstance(count, int):
                    raise TypeError("count must be int")
                self.count = count

        # Constructor raises TypeError which create_handler_instance wraps as MissingDependencyError
        with pytest.raises(MissingDependencyError):
            resolver.create_handler_instance(StrictHandler, {"count": "not-an-int"})
