from collections.abc import Sequence
from http import HTTPStatus
from enum import Enum, auto
from typing import TypeAlias
from collections.abc import Callable

from asgi_toolkit.protocol import ASGIApp, Message, Receive, Scope, Send, HTTPResponseStartMessage

ETagGenerator: TypeAlias = Callable[[bytes], str]
Method: TypeAlias = str
Path: TypeAlias = str


class ConditionalEtagHeader(Enum):
    IF_MATCH = auto()
    IF_NONE_MATCH = auto()


class ETagMiddleware:
    """ASGI middleware for HTTP ETag support with conditional requests."""

    __slots__ = (
        "app",
        "etag_generator",
        "ignore_paths",
    )

    def __init__(
        self,
        app: ASGIApp,
        etag_generator: ETagGenerator,
        ignore_paths: Sequence[tuple[Method, Path]] | None = None,
    ) -> None:
        """Initialize ETag middleware.

        Args:
            app: ASGI application to wrap
            etag_generator: Function to generate ETags from response body
            ignore_paths: Optional paths to skip ETag processing
        """
        self.app = app
        self.etag_generator = etag_generator
        self.ignore_paths = ignore_paths or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not scope["type"] == "http" or (scope["method"], scope["path"]) in self.ignore_paths:
            await self.app(scope, receive, send)
            return

        client_etag = None
        conditional_header = None

        for header, value in scope["headers"]:
            match header, value:
                case (b"if-match", etag):
                    conditional_header = ConditionalEtagHeader.IF_MATCH
                    client_etag = etag.decode()
                    break
                case (b"if-none-match", etag):
                    conditional_header = ConditionalEtagHeader.IF_NONE_MATCH
                    client_etag = etag.decode()
                    break
                case _:
                    continue

        await self.app(
            scope,
            receive,
            ETagSendWrapper(
                send=send,
                client_etag=client_etag,
                conditional_header=conditional_header,
                etag_generator=self.etag_generator,
            ),
        )


def etag_middleware(
    etag_generator: ETagGenerator, ignore_paths: Sequence[tuple[Method, Path]] | None = None
) -> Callable[[ASGIApp], ETagMiddleware]:
    """Create an ETag middleware factory function.

    Args:
        etag_generator: Function to generate ETags from response body
        ignore_paths: Optional sequence of (method, path) tuples to ignore

    Returns:
        A function that takes an ASGI app and returns ETagMiddleware
    """

    def middleware_factory(app: ASGIApp) -> ETagMiddleware:
        return ETagMiddleware(app, etag_generator, ignore_paths)

    return middleware_factory


class ETagSendWrapper:
    """Wrapper for ASGI send callable that handles ETag processing."""

    __slots__: tuple[str, ...] = (
        "send",
        "client_etag",
        "conditional_header",
        "etag_generator",
        "original_message",
    )

    def __init__(
        self,
        send: Send,
        client_etag: str | None,
        conditional_header: ConditionalEtagHeader | None,
        etag_generator: ETagGenerator,
    ) -> None:
        self.send = send
        self.client_etag = client_etag
        self.conditional_header = conditional_header
        self.etag_generator = etag_generator

        self.original_message: HTTPResponseStartMessage | None = None

    def _is_modified(self, server_etag: str, client_etag: str | None) -> bool:
        return server_etag != client_etag

    async def __call__(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.original_message = message.copy()
            return

        if message["type"] == "http.response.body":
            assert self.original_message is not None, "_ETagSendWrapper called before http.response.start"

            server_etag = self.etag_generator(message["body"])

            match self.conditional_header:
                case ConditionalEtagHeader.IF_MATCH:
                    if self._is_modified(server_etag, self.client_etag):
                        await self.send(
                            {
                                "type": "http.response.start",
                                "status": HTTPStatus.PRECONDITION_FAILED,
                                "headers": self.original_message["headers"],
                            }
                        )
                        await self.send(
                            {
                                "type": "http.response.body",
                                "body": b"",
                                "more_body": False,
                            }
                        )
                        return
                case ConditionalEtagHeader.IF_NONE_MATCH:
                    print(server_etag, self.client_etag)
                    if not self._is_modified(server_etag, self.client_etag):
                        await self.send(
                            {
                                "type": "http.response.start",
                                "status": HTTPStatus.NOT_MODIFIED,
                                "headers": self.original_message["headers"],
                            }
                        )
                        await self.send(
                            {
                                "type": "http.response.body",
                                "body": b"",
                                "more_body": False,
                            }
                        )
                        return

            self.original_message["headers"].append(("ETag".encode(), server_etag.encode()))
            await self.send(self.original_message)

            await self.send(message)
            return
