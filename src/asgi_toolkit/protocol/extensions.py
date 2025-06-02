"""ASGI protocol extension message types.

This module defines TypedDict classes for various ASGI extensions including
HTTP/2 Server Push, Zero Copy Send, Early Hints, WebSocket HTTP responses,
and TLS connection information.
"""

from collections.abc import Iterable
from typing import TypedDict, Required, NotRequired, Literal, Any


class HTTPResponsePushMessage(TypedDict):
    """HTTP/2 Server Push extension message."""

    type: Literal["http.response.push"]
    path: Required[str]  # HTTP path with percent-encoded sequences decoded
    headers: Required[list[tuple[bytes, bytes]]]  # Headers for the pushed resource


class HTTPResponseZeroCopySendMessage(TypedDict):
    """Zero-copy file send extension message."""

    type: Literal["http.response.zerocopysend"]
    file: Required[Any]  # File descriptor object with underlying OS file descriptor
    offset: NotRequired[int]  # Offset to start reading from file
    count: NotRequired[int]  # Number of bytes to copy
    more_body: NotRequired[bool]  # Whether more content follows


class HTTPResponsePathSendMessage(TypedDict):
    """File path send extension message."""

    type: Literal["http.response.pathsend"]
    path: Required[str]  # Absolute file path to send


class HTTPResponseEarlyHintMessage(TypedDict):
    """HTTP Early Hints (103) extension message."""

    type: Literal["http.response.early_hint"]
    links: Required[list[bytes]]  # Link header field values (RFC 8288)


class HTTPResponseTrailers(TypedDict):
    """HTTP response trailers extension message."""

    type: Literal["http.response.trailers"]
    # An iterable of [header name, header value] iterables . Names must be lowercased. Pseudo headers must not be present.
    headers: Iterable[Iterable[bytes]]
    more_trailers: NotRequired[bool]


class WebSocketHTTPResponseStartMessage(TypedDict):
    """WebSocket HTTP response start message for denial responses."""

    type: Literal["websocket.http.response.start"]
    status: Required[int]  # HTTP status code
    headers: NotRequired[list[tuple[bytes, bytes]]]


class WebSocketHTTPResponseBodyMessage(TypedDict):
    """WebSocket HTTP response body message for denial responses."""

    type: Literal["websocket.http.response.body"]
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


class TLSExtension(TypedDict):
    """TLS connection information extension."""

    server_cert: Required[str | None]  # PEM-encoded x509 certificate or None
    client_cert_chain: NotRequired[list[str]]  # Iterable of PEM-encoded x509 certificates
    client_cert_name: NotRequired[str | None]  # RFC4514 Distinguished Name or None
    client_cert_error: NotRequired[str | None]  # Error message if cert verification failed
    tls_version: Required[int | None]  # TLS version number (e.g., 0x0303 for TLS 1.2)
    cipher_suite: Required[int | None]  # 16-bit cipher suite identifier


class ASGIExtensions(TypedDict, total=False):
    """Container for all ASGI protocol extensions."""

    # WebSocket denial response extension - allows sending HTTP response to deny WebSocket upgrade
    websocket_http_response: WebSocketHTTPResponseStartMessage | WebSocketHTTPResponseBodyMessage

    # HTTP/2 Server Push extension - allows server to push resources to client
    http_response_push: HTTPResponsePushMessage
    # Zero Copy Send extension - allows sending file descriptors with zero copy
    http_response_zerocopysend: HTTPResponseZeroCopySendMessage
    # Path Send extension - allows sending file paths directly
    http_response_pathsend: HTTPResponsePathSendMessage
    # Early Hints extension (RFC 8297) - allows sending 103 Early Hints responses
    http_response_early_hint: HTTPResponseEarlyHintMessage
    # HTTP Trailers extension - allows sending trailing headers after response body
    http_response_trailers: HTTPResponseTrailers
    # Debug extension - allows sending debug information (testing only)
    http_response_debug: dict[str, Any]

    # TLS extension - provides TLS connection information with well-defined structure
    tls: TLSExtension
