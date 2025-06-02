"""HTTP protocol message types and constants for ASGI.

This module defines all HTTP-related ASGI protocol types including request/response
messages, scopes, and common HTTP constants like methods, versions, and status codes.
"""

from typing import TypedDict, Literal, Required, NotRequired, TypeAlias
from .extensions import ASGIExtensions

HTTPMethod: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE", "CONNECT"]
HTTPVersion: TypeAlias = Literal["1.0", "1.1", "2", "3"]
HTTPScheme: TypeAlias = Literal["http", "https"]

# fmt: off
HTTPStatusCode: TypeAlias = (
    Literal[
        # 1xx Informational
        100, 101, 102, 103,
        # 2xx Success
        200, 201, 202, 203,
        204, 205, 206, 207,
        208, 226,
        # 3xx Redirection
        300, 301, 302, 303,
        304, 305, 307, 308,
        # 4xx Client Error
        400, 401, 402, 403,
        404, 405, 406, 407,
        408, 409, 410, 411,
        412, 413, 414, 415,
        416, 417, 418, 421,
        422, 423, 424, 425,
        426, 428, 429, 431,
        451,
        # 5xx Server Error
        500, 501, 502, 503,
        504, 505, 506, 507,
        508, 510, 511,
    ]
    | int
)  # Allow any valid HTTP status code
# fmt: on


class HTTPRequestScope(TypedDict):
    type: Literal["http"]
    asgi: Required[dict[str, str]]
    http_version: Required[HTTPVersion]
    method: Required[HTTPMethod]
    scheme: NotRequired[HTTPScheme]
    path: Required[str]
    raw_path: NotRequired[bytes | None]
    query_string: Required[bytes]
    root_path: NotRequired[str]
    headers: Required[list[tuple[bytes, bytes]]]
    client: NotRequired[tuple[str, int] | None]
    server: NotRequired[tuple[str, int | None] | None]
    state: NotRequired[dict[str, object]]
    extensions: NotRequired[ASGIExtensions]


class HTTPRequestMessage(TypedDict):
    type: Literal["http.request"]
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


class HTTPDisconnectMessage(TypedDict):
    type: Literal["http.disconnect"]


class HTTPResponseStartMessage(TypedDict):
    type: Literal["http.response.start"]
    status: Required[HTTPStatusCode]
    headers: NotRequired[list[tuple[bytes, bytes]]]
    trailers: NotRequired[bool]


class HTTPResponseBodyMessage(TypedDict):
    type: Literal["http.response.body"]
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


class HTTPResponseTrailersMessage(TypedDict):
    type: Literal["http.response.trailers"]
    headers: Required[list[tuple[bytes, bytes]]]
    more_trailers: NotRequired[bool]


# Extension Messages
HTTPMessage: TypeAlias = HTTPRequestMessage | HTTPDisconnectMessage
HTTPResponseMessage: TypeAlias = HTTPResponseStartMessage | HTTPResponseBodyMessage | HTTPResponseTrailersMessage
