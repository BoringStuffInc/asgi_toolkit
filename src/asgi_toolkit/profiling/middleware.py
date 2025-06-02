from collections.abc import Awaitable, Callable
from typing import Optional, cast

from asgi_toolkit.protocol import ASGIApp, Message, Scope, Receive, Send, HTTPRequestScope
from asgi_toolkit.profiling.types import (
    ReportOutput,
    ReportOutputFile,
    ReportOutputLogger,
    ReportOutputResponse,
    Profiler,
)


class ProfilingMiddleware:
    """
    ASGI middleware for profiling requests.

    Args:
        app: The ASGI application.
        profiler: The profiler instance to use.
        report_output: Configuration for where to output the report.
        activation_query_param: Query parameter to activate profiling.
        activation_header: Header to activate profiling.
    """

    __slots__ = (
        "app",
        "profiler",
        "report_output",
        "activation_query_param",
        "activation_header",
    )

    def __init__(
        self,
        app: ASGIApp,
        *,
        profiler: Profiler,
        report_output: ReportOutput,
        activation_query_param: Optional[str] = None,
        activation_header: Optional[str] = None,
    ) -> None:
        if not activation_query_param and not activation_header:
            raise ValueError("At least one of activation_query_param or activation_header must be provided.")

        self.app: ASGIApp = app
        self.profiler: Profiler = profiler
        self.report_output: ReportOutput = report_output
        self.activation_query_param: Optional[str] = activation_query_param
        self.activation_header: Optional[str] = activation_header

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match scope["type"]:
            case "http":
                http_scope = cast(HTTPRequestScope, scope)

                if self._is_profiling_active(http_scope):
                    report = None
                    original_send = send

                    async def wrapped_send(message: Message) -> None:
                        if isinstance(self.report_output, ReportOutputResponse):
                            if message["type"] in ["http.response.start", "http.response.body"]:
                                return
                        await original_send(message)

                    match self.report_output:
                        case ReportOutputResponse():
                            app_send: Callable[[Message], Awaitable[None]] = wrapped_send
                        case _:
                            app_send = original_send

                    self.profiler.start()
                    await self.app(scope, receive, app_send)
                    self.profiler.stop()
                    report = self.profiler.report()

                    if report:
                        await self._output_report(report, original_send)
                else:
                    await self.app(scope, receive, send)
            case _:
                await self.app(scope, receive, send)

    def _is_profiling_active(self, scope: HTTPRequestScope) -> bool:
        if self.activation_query_param:
            query_string = scope.get("query_string", b"").decode("utf-8")
            if f"{self.activation_query_param}=true" in query_string:
                return True
        if self.activation_header:
            headers = dict(scope.get("headers", []))
            if self.activation_header.lower().encode("utf-8") in headers:
                return True
        return False

    async def _output_report(self, report: str, send: Send) -> None:
        match self.report_output:
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
