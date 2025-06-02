import json
from collections.abc import Callable
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, TypeAlias

from asgi_toolkit.context import http_request_context, new_context
from asgi_toolkit.protocol import ASGIApp, Receive, Scope, Send

HeaderValidator: TypeAlias = Callable[[str], bool]
ErrorFormatter: TypeAlias = Callable[[str, str], dict[str, Any]]


@dataclass(frozen=True)
class HeaderRule:
    """Configuration for a single header extraction and validation rule.

    Args:
        name: Header name to extract
        required: Whether the header is required
        validator: Optional function to validate header value
        error_status_missing: HTTP status for missing required headers
        error_status_invalid: HTTP status for invalid header values
    """

    name: str
    required: bool = False
    validator: HeaderValidator | None = None
    error_status_missing: HTTPStatus = HTTPStatus.BAD_REQUEST
    error_status_invalid: HTTPStatus = HTTPStatus.BAD_REQUEST


@dataclass(slots=True)
class HeadersConfig:
    rules: list[HeaderRule] = field(default_factory=list)

class HeadersMiddleware:
    """ASGI middleware for extracting and validating HTTP headers."""

    __slots__ = ("app", "config")

    def __init__(self, app: ASGIApp, config: HeadersConfig) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        with new_context():
            headers = {name.decode(): value.decode() for name, value in scope["headers"]}

            for rule in self.config.rules:
                header_key = rule.name.lower()
                header_value = headers.get(header_key)

                if header_value is None:
                    if rule.required:
                        await self._send_error_response(
                            send,
                            rule=rule,
                            error_type="missing",
                            message=f"Required header '{rule.name}' is missing",
                        )
                        return
                    else:
                        continue

                if header_value is not None and rule.validator:
                    if not rule.validator(header_value):
                        await self._send_error_response(
                            send,
                            rule=rule,
                            error_type="invalid",
                            message=f"Header '{rule.name}' has invalid value: {header_value}",
                        )
                        return

                http_request_context[rule.name] = header_value

            await self.app(scope, receive, send)

    async def _send_error_response(self, send: Send, *, rule: HeaderRule, error_type: str, message: str) -> None:
        """Send an error response for header validation failures."""
        status = rule.error_status_missing if error_type == "missing" else rule.error_status_invalid
        error_body = {"error": message, "header": rule.name}

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps(error_body).encode(),
                "more_body": False,
            }
        )
