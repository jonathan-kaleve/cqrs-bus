import logging

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


class VarArgsHandler:
    def __init__(self, *args, **kwargs):
        pass


class MixedVarArgsHandler:
    def __init__(self, service_a: ServiceA, *args, **kwargs):
        self.service_a = service_a


class TestInspectHandlerInit:
    def test_no_dependencies(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(NoDepsHandler)
        assert deps == {}

    def test_single_dependency(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(SingleDepHandler)
        assert deps == {"service_a": ServiceA}

    def test_multiple_dependencies(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(MultiDepHandler)
        assert deps == {"service_a": ServiceA, "service_b": ServiceB}

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

    def test_var_positional_and_var_keyword_are_ignored(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(VarArgsHandler)
        assert deps == {}

    def test_mixed_varargs_only_returns_typed_params(self):
        resolver = DependencyResolver()
        deps = resolver.inspect_handler_init(MixedVarArgsHandler)
        assert deps == {"service_a": ServiceA}


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

    def test_type_mismatch_logs_warning(self, caplog):
        resolver = DependencyResolver()
        with caplog.at_level(logging.WARNING, logger="cqrs_bus.discovery.dependency_resolver"):
            resolved = resolver.resolve_dependencies(SingleDepHandler, {"service_a": "wrong_type"})
        assert any("expected ServiceA" in r.message for r in caplog.records)
        assert resolved == {"service_a": "wrong_type"}  # still resolves; warning only

    def test_isinstance_type_error_is_silenced(self):
        # A type whose __instancecheck__ raises TypeError should not propagate — the
        # dependency is still resolved (the warning is just skipped).
        class _RaisingMeta(type):
            def __instancecheck__(cls, instance):
                raise TypeError("custom isinstance error")

        class _BadType(metaclass=_RaisingMeta):
            pass

        class _HandlerWithBadType:
            def __init__(self, dep: _BadType):
                self.dep = dep

        resolver = DependencyResolver()
        resolved = resolver.resolve_dependencies(_HandlerWithBadType, {"dep": object()})
        assert "dep" in resolved


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

        # Type mismatch is warned (not raised); constructor TypeError wraps as MissingDependencyError
        with pytest.raises(MissingDependencyError):
            resolver.create_handler_instance(StrictHandler, {"count": "not-an-int"})
