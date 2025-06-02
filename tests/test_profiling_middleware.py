import pytest
import logging
import os
import tempfile
import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient

from litestar import Litestar, get
from litestar.testing import TestClient as LitestarTestClient
from litestar.middleware import DefineMiddleware

from asgi_toolkit.profiling import (
    ProfilingMiddleware,
    Profiler,
    ReportOutputFile,
    ReportOutputLogger,
    ReportOutputResponse,
)


class MockManualProfiler(Profiler):
    def __init__(self):
        self.started = False
        self.stopped = False
        self._report_content = "Manual Profiler Report"

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def report(self) -> str:
        return self._report_content


def create_client(framework, activation_method, report_output, profiler=None):
    if profiler is None:
        profiler = MockManualProfiler()

    middleware_kwargs = {
        "report_output": report_output,
        f"activation_{activation_method}_param"
        if activation_method == "query"
        else f"activation_{activation_method}": "profile" if activation_method == "query" else "X-Profile",
    }

    if framework == "fastapi":
        app = FastAPI()

        @app.get("/")
        async def read_root():
            return {"Hello": "world"}

        app.add_middleware(ProfilingMiddleware, profiler=profiler, **middleware_kwargs)
        return FastAPITestClient(app), profiler
    else:  # litestar

        @get("/")
        async def read_root() -> dict[str, str]:
            return {"Hello": "world"}

        app = Litestar(
            route_handlers=[read_root],
            middleware=[DefineMiddleware(ProfilingMiddleware, profiler=profiler, **middleware_kwargs)],
        )
        return LitestarTestClient(app), profiler


def assert_profiler_state(profiler: MockManualProfiler, should_be_active: bool):
    if should_be_active:
        assert profiler.started, "Profiler should have started"
        assert profiler.stopped, "Profiler should have stopped"
    else:
        assert not profiler.started, "Profiler should not have started"
        assert not profiler.stopped, "Profiler should not have stopped"


def assert_response_output(response, profiler: Profiler):
    assert response.status_code == 200
    assert response.text == profiler.report()


def assert_file_output(filepath: str, profiler: Profiler):
    assert os.path.exists(filepath), "Report file should exist"
    with open(filepath, "r") as f:
        assert f.read() == profiler.report(), "File should contain profiler report"


def assert_logger_output(caplog, profiler: Profiler, logger_name: str = "test_logger"):
    log_messages = [record.message for record in caplog.records if record.name == logger_name]
    assert any("Profiling Report:" in msg for msg in log_messages), "Log should contain 'Profiling Report:'"
    assert any(profiler.report() in msg for msg in log_messages), "Log should contain profiler report"


class TestProfilingMiddleware:
    @pytest.mark.parametrize(
        "framework,activation_method,activation_value",
        [
            ("fastapi", "query", "/?profile=true"),
            ("fastapi", "header", "/"),
            ("litestar", "query", "/?profile=true"),
            ("litestar", "header", "/"),
        ],
    )
    def test_profiling_response_output(self, framework, activation_method, activation_value):
        report_output = ReportOutputResponse(type="response")
        client, profiler = create_client(framework, activation_method, report_output)

        if activation_method == "query":
            response = client.get(activation_value)
        else:
            response = client.get(activation_value, headers={"X-Profile": "true"})

        assert_profiler_state(profiler, True)
        assert_response_output(response, profiler)

    @pytest.mark.parametrize(
        "framework,activation_method",
        [
            ("fastapi", "query"),
            ("fastapi", "header"),
            ("litestar", "query"),
            ("litestar", "header"),
        ],
    )
    def test_profiling_file_output(self, framework, activation_method):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.txt")
            report_output = ReportOutputFile(filepath=filepath)
            client, profiler = create_client(framework, activation_method, report_output)

            if activation_method == "query":
                response = client.get("/?profile=true")
            else:
                response = client.get("/", headers={"X-Profile": "true"})

            assert response.status_code == 200
            assert_profiler_state(profiler, True)
            assert_file_output(filepath, profiler)

    @pytest.mark.parametrize(
        "activation_method",
        ["query", "header"],
    )
    def test_profiling_logger_output(self, activation_method, caplog):
        test_logger = logging.getLogger("test_logger")
        report_output = ReportOutputLogger(logger=test_logger)
        client, profiler = create_client("fastapi", activation_method, report_output)

        with caplog.at_level(logging.INFO):
            if activation_method == "query":
                response = client.get("/?profile=true")
            else:
                response = client.get("/", headers={"X-Profile": "true"})

        assert response.status_code == 200
        assert_profiler_state(profiler, True)
        assert_logger_output(caplog, profiler)

    @pytest.mark.parametrize("framework", ["fastapi", "litestar"])
    def test_profiling_not_activated(self, framework):
        report_output = ReportOutputResponse(type="response")
        client, profiler = create_client(framework, "query", report_output)

        response = client.get("/")

        assert response.status_code == 200
        assert_profiler_state(profiler, False)
        assert response.json() == {"Hello": "world"}

    def test_profiling_skipped_for_websocket_scope(self):
        profiler = MockManualProfiler()

        async def dummy_websocket_app(scope, receive, send):
            pass

        websocket_scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"profile=true",
            "headers": [],
            "client": ("127.0.0.1", 8000),
            "server": ("127.0.0.1", 8000),
            "subprotocol": None,
            "extensions": {},
        }

        async def websocket_receive():
            return {"type": "websocket.connect"}

        async def websocket_send(message):
            pass

        middleware = ProfilingMiddleware(
            dummy_websocket_app,
            profiler=profiler,
            report_output=ReportOutputResponse(type="response"),
            activation_query_param="profile",
        )

        asyncio.run(middleware(websocket_scope, websocket_receive, websocket_send))

        assert_profiler_state(profiler, False)
