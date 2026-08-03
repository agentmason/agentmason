class AgentMasonError(Exception):
    """Base error for AgentMason."""


class ConfigurationError(AgentMasonError):
    """Raised when configuration is invalid."""
