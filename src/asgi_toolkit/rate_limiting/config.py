"""Configuration classes for rate limiting middleware."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyConfig:
    """Rate limiting policy configuration."""

    limit: int
    window: int

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.window <= 0:
            raise ValueError("window must be positive")


# Type definitions for policy configuration
MethodPolicyDict = dict[str, PolicyConfig]  # {"GET": PolicyConfig(100, 60)}
RoutePolicyDict = dict[str, PolicyConfig | MethodPolicyDict]  # Route -> policy or method-specific policies


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for rate limiting middleware."""

    default_limit: int = 100
    default_window: int = 60

    activation_header: str | None = None
    activation_query_param: str | None = None

    whitelist: set[str] = field(default_factory=set)
    policy_overrides: RoutePolicyDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.default_limit <= 0:
            raise ValueError("default_limit must be positive")
        if self.default_window <= 0:
            raise ValueError("default_window must be positive")

        match self.activation_header, self.activation_query_param:
            case None, None:
                raise ValueError("At least one of [`activation_header`, `activation_query_param] must be set")
