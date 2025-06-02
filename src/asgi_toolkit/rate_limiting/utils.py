"""Utility functions for rate limiting."""

from urllib.parse import parse_qs

from asgi_toolkit.protocol import HTTPRequestScope

from asgi_toolkit.rate_limiting.config import PolicyConfig, RateLimitConfig


def is_rate_limiting_activated(scope: HTTPRequestScope, config: RateLimitConfig) -> bool:
    """Check if rate limiting is activated for this request."""
    headers: dict[bytes, bytes] = dict(scope["headers"])
    query_string = scope["query_string"].decode()
    query_params = parse_qs(query_string)

    is_active = False

    if config.activation_header:
        header_name = config.activation_header.lower().encode()
        if header_name in headers:
            header_value = headers[header_name].decode().lower()
            if header_value != "off":
                is_active = True
            else:
                return False

    if config.activation_query_param:
        param_name = config.activation_query_param
        if param_name in query_params:
            param_value = query_params[param_name][0].lower()
            if param_value != "off":
                is_active = True
            else:
                return False

    return is_active


def get_rate_limit_policy(route: str, method: str, config: RateLimitConfig) -> tuple[int, int]:
    """Get rate limiting policy for the given route and method."""
    if not config.policy_overrides or route not in config.policy_overrides:
        return config.default_limit, config.default_window

    route_policy = config.policy_overrides[route]

    match route_policy:
        case PolicyConfig():
            return route_policy.limit, route_policy.window
        case dict() if method in route_policy:
            method_policy = route_policy[method]
            return method_policy.limit, method_policy.window
        case _:
            return config.default_limit, config.default_window


def generate_rate_limit_key(client_id: str, route: str, method: str) -> str:
    """Generate a normalized key for rate limiting."""

    safe_client_id = client_id.replace(":", "_")
    safe_route = route.replace(":", "_")
    safe_method = method.replace(":", "_")
    return f"ratelimit:{safe_client_id}:{safe_route}:{safe_method}"
