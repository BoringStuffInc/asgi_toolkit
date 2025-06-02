"""Type-safe ASGI protocol definitions.

This module provides comprehensive TypedDict definitions for all ASGI protocol
messages, scopes, and extensions. It ensures type safety when working with
ASGI applications and middleware.
"""

from typing import Callable, Awaitable

from .http import (
    HTTPRequestScope,
    HTTPMessage,
    HTTPResponseMessage,
    HTTPMethod,
    HTTPVersion,
    HTTPScheme,
    HTTPStatusCode,
    HTTPRequestMessage,
    HTTPDisconnectMessage,
    HTTPResponseStartMessage,
    HTTPResponseBodyMessage,
    HTTPResponseTrailersMessage,
)
from .ws import (
    WebSocketScope,
    WebSocketMessage,
    WebSocketScheme,
    WebSocketCloseCode,
    WebSocketConnectMessage,
    WebSocketAcceptMessage,
    WebSocketReceiveMessage,
    WebSocketSendMessage,
    WebSocketDisconnectMessage,
    WebSocketCloseMessage,
)
from .lifespan import (
    LifespanScope,
    LifespanMessage,
    LifespanResponseMessage,
    LifespanStartupMessage,
    LifespanShutdownMessage,
    LifespanStartupCompleteMessage,
    LifespanStartupFailedMessage,
    LifespanShutdownCompleteMessage,
    LifespanShutdownFailedMessage,
)
from .extensions import (
    HTTPResponsePushMessage,
    HTTPResponseZeroCopySendMessage,
    HTTPResponsePathSendMessage,
    HTTPResponseEarlyHintMessage,
    WebSocketHTTPResponseStartMessage,
    WebSocketHTTPResponseBodyMessage,
    TLSExtension,
    ASGIExtensions,
)


Scope = HTTPRequestScope | WebSocketScope | LifespanScope
Message = HTTPMessage | HTTPResponseMessage | WebSocketMessage | LifespanMessage | LifespanResponseMessage
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

__all__: tuple[str, ...] = (
    # Core ASGI types
    "Scope",
    "Message",
    "Receive",
    "Send",
    "ASGIApp",
    # HTTP types
    "HTTPRequestScope",
    "HTTPMessage",
    "HTTPResponseMessage",
    "HTTPMethod",
    "HTTPVersion",
    "HTTPScheme",
    "HTTPStatusCode",
    "HTTPRequestMessage",
    "HTTPDisconnectMessage",
    "HTTPResponseStartMessage",
    "HTTPResponseBodyMessage",
    "HTTPResponseTrailersMessage",
    # WebSocket types
    "WebSocketScope",
    "WebSocketMessage",
    "WebSocketScheme",
    "WebSocketCloseCode",
    "WebSocketConnectMessage",
    "WebSocketAcceptMessage",
    "WebSocketReceiveMessage",
    "WebSocketSendMessage",
    "WebSocketDisconnectMessage",
    "WebSocketCloseMessage",
    # Lifespan types
    "LifespanScope",
    "LifespanMessage",
    "LifespanResponseMessage",
    "LifespanStartupMessage",
    "LifespanShutdownMessage",
    "LifespanStartupCompleteMessage",
    "LifespanStartupFailedMessage",
    "LifespanShutdownCompleteMessage",
    "LifespanShutdownFailedMessage",
    # Extension types
    "HTTPResponsePushMessage",
    "HTTPResponseZeroCopySendMessage",
    "HTTPResponsePathSendMessage",
    "HTTPResponseEarlyHintMessage",
    "WebSocketHTTPResponseStartMessage",
    "WebSocketHTTPResponseBodyMessage",
    "TLSExtension",
    "ASGIExtensions",
)
