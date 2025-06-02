from collections.abc import Awaitable, Callable
from typing import cast

from asgi_toolkit.protocol import ASGIApp, Message, Scope, Receive, Send, HTTPRequestScope
from asgi_toolkit.profiling.types import (
    ReportOutputFile,
    ReportOutputLogger,
    ReportOutputResponse,
)
from asgi_toolkit.profiling.config import ProfilingConfig


class ProfilingMiddleware:
    """
    ASGI middleware for profiling requests.

    Args:
        app: The ASGI application.
        config: The profiling configuration.
    """

    __slots__ = ("app", "config")

    def __init__(self, app: ASGIApp, config: ProfilingConfig) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match scope["type"]:
            case "http":
                http_scope = cast(HTTPRequestScope, scope)

                if self._is_profiling_active(http_scope):
                    report = None
                    original_send = send

                    async def wrapped_send(message: Message) -> None:
                        if isinstance(self.config.report_output, ReportOutputResponse):
                            if message["type"] in ["http.response.start", "http.response.body"]:
                                return
                        await original_send(message)

                    match self.config.report_output:
                        case ReportOutputResponse():
                            app_send: Callable[[Message], Awaitable[None]] = wrapped_send
                        case _:
                            app_send = original_send

                    self.config.profiler.start()
                    await self.app(scope, receive, app_send)
                    self.config.profiler.stop()
                    report = self.config.profiler.report()

                    if report:
                        await self._output_report(report, original_send)
                else:
                    await self.app(scope, receive, send)
            case _:
                await self.app(scope, receive, send)

    def _is_profiling_active(self, scope: HTTPRequestScope) -> bool:
        if self.config.activation_query_param:
            query_string = scope.get("query_string", b"").decode("utf-8")
            if f"{self.config.activation_query_param}=true" in query_string:
                return True
        if self.config.activation_header:
            headers = dict(scope.get("headers", []))
            if self.config.activation_header.lower().encode("utf-8") in headers:
                return True
        return False

    async def _output_report(self, report: str, send: Send) -> None:
        match self.config.report_output:
            case ReportOutputFile(filepath=filepath):
                with open(filepath, "w") as f:
                    f.write(report)
            case ReportOutputLogger(logger=output_logger):
                output_logger.info("Profiling Report:\n" + report)
            case ReportOutputResponse():
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [(b"content-type", b"text/plain")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": report.encode("utf-8"),
                    }
                )
