class ArealistingError(Exception):
    """Base exception for the AREALISTING integration."""


class ArealistingConfigurationError(ArealistingError):
    """Raised when required local configuration is missing or invalid."""


class ArealistingAPIError(ArealistingError):
    def __init__(self, message, *, status_code=None, code=''):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class ArealistingUnauthorizedError(ArealistingAPIError):
    pass


class ArealistingForbiddenError(ArealistingAPIError):
    pass


class ArealistingRateLimitError(ArealistingAPIError):
    def __init__(self, message, *, retry_after=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ArealistingInvalidResponseError(ArealistingAPIError):
    pass


class ArealistingTransportError(ArealistingAPIError):
    pass


class ArealistingSyncInProgressError(ArealistingError):
    """Raised when another non-stale synchronization owns the global lock."""
