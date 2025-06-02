"""WebSocket protocol message types and constants for ASGI.

This module defines all WebSocket-related ASGI protocol types including connection
messages, data transfer messages, and WebSocket-specific constants.
"""

from typing import TypedDict, Literal, Required, NotRequired, TypeAlias
from .extensions import ASGIExtensions
from .http import HTTPVersion


WebSocketScheme: TypeAlias = Literal["ws", "wss"]
WebSocketCloseCode: TypeAlias = (
    Literal[
        1000,  # Normal Closure
        1001,  # Going Away
        1002,  # Protocol Error
        1003,  # Unsupported Data
        1005,  # No Status Received
        1006,  # Abnormal Closure
        1007,  # Invalid frame payload data
        1008,  # Policy Violation
        1009,  # Message Too Big
        1010,  # Mandatory Extension
        1011,  # Internal Server Error
        1015,  # TLS handshake
    ]
    | int
)  # Allow custom codes 3000-4999


class WebSocketScope(TypedDict):
    type: Literal["websocket"]
    asgi: Required[dict[str, str]]
    http_version: NotRequired[HTTPVersion]
    scheme: NotRequired[WebSocketScheme]
    path: Required[str]
    raw_path: NotRequired[bytes | None]
    query_string: NotRequired[bytes]
    root_path: NotRequired[str]
    headers: Required[list[tuple[bytes, bytes]]]
    client: NotRequired[tuple[str, int] | None]
    server: NotRequired[tuple[str, int | None] | None]
    subprotocols: NotRequired[list[str]]
    state: NotRequired[dict[str, object]]
    extensions: NotRequired[ASGIExtensions]


class WebSocketConnectMessage(TypedDict):
    type: Literal["websocket.connect"]


class WebSocketAcceptMessage(TypedDict):
    type: Literal["websocket.accept"]
    subprotocol: NotRequired[str | None]
    headers: NotRequired[list[tuple[bytes, bytes]]]


class WebSocketReceiveMessage(TypedDict):
    type: Literal["websocket.receive"]
    bytes: NotRequired[bytes]
    text: NotRequired[str]


class WebSocketSendMessage(TypedDict):
    type: Literal["websocket.send"]
    bytes: NotRequired[bytes]
    text: NotRequired[str]


class WebSocketDisconnectMessage(TypedDict):
    type: Literal["websocket.disconnect"]
    code: Required[WebSocketCloseCode]
    reason: NotRequired[str | None]


class WebSocketCloseMessage(TypedDict):
    type: Literal["websocket.close"]
    code: WebSocketCloseCode
    reason: str | None


WebSocketMessage: TypeAlias = (
    WebSocketConnectMessage
    | WebSocketAcceptMessage
    | WebSocketReceiveMessage
    | WebSocketSendMessage
    | WebSocketDisconnectMessage
    | WebSocketCloseMessage
)
