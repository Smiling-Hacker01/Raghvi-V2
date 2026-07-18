class AIServiceError(Exception):
    """Base error for AI service failures.

    This is intended for user-facing failures that should be handled
    gracefully by the API layer instead of surfacing as a server crash.
    """

    def __init__(self, user_message: str, *, cause: Exception | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.cause = cause


class AIConfigurationError(AIServiceError):
    """Raised when an AI provider is misconfigured or unavailable."""


class AIProviderFailureError(AIServiceError):
    """Raised when a provider fails during request processing."""
