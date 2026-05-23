"""Provider-related exceptions."""


class ProviderError(Exception):
    """Base exception for provider errors."""


class ProviderNotFoundError(ProviderError):
    """Raised when a provider is not registered."""


class ProviderAlreadyRegisteredError(ProviderError):
    """Raised when a provider name is already registered."""


class ProviderValidationError(ProviderError):
    """Raised when a provider does not satisfy the expected contract."""
