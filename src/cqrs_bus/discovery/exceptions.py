class HandlerDiscoveryError(Exception):
    pass


class MissingDependencyError(HandlerDiscoveryError):
    pass


class DuplicateHandlerError(HandlerDiscoveryError):
    pass


class InvalidHandlerError(HandlerDiscoveryError):
    pass
