import pytest
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient
from litestar import Litestar, get
from litestar.testing import TestClient as LitestarTestClient
from litestar.middleware import DefineMiddleware

from asgi_toolkit.context import http_request_context
from asgi_toolkit.headers import HeadersMiddleware, HeadersConfig, HeaderRule


def is_numeric(value: str) -> bool:
    return value.isdigit()


def always_invalid(_value: str) -> bool:
    return False


@pytest.fixture(params=["fastapi", "litestar"])
def create_client(request):
    def factory(config):
        match request.param:
            case "fastapi":
                app = FastAPI()

                @app.get("/")
                def read_headers():
                    return dict(http_request_context)

                app.add_middleware(HeadersMiddleware, config=config)
                client = FastAPITestClient(app)
            case "litestar":

                @get("/")
                async def read_headers() -> dict[str, Any]:
                    return dict(http_request_context)

                app = Litestar(
                    route_handlers=[read_headers],
                    middleware=[DefineMiddleware(HeadersMiddleware, config=config)],
                )
                client = LitestarTestClient(app)

        return client

    return factory


class TestHeadersMiddleware:
    @pytest.mark.parametrize(
        "header_config,request_headers,expected_response",
        [
            ({"X-Test-Header": {}}, {"X-Test-Header": "test_value"}, {"X-Test-Header": "test_value"}),
            (
                {"X-Header-1": {}, "X-Header-2": {}},
                {"X-Header-1": "value1", "X-Header-2": "value2"},
                {"X-Header-1": "value1", "X-Header-2": "value2"},
            ),
            ({"X-Optional-Header": {"required": False}}, {}, {}),
            (
                {"X-Required-Header": {"required": True}},
                {"X-Required-Header": "present_value"},
                {"X-Required-Header": "present_value"},
            ),
        ],
    )
    def test_successful_header_processing(self, create_client, header_config, request_headers, expected_response):
        config = HeadersConfig()
        for header_name, header_opts in header_config.items():
            config.add_header(header_name, **header_opts)

        client = create_client(config)

        response = client.get("/", headers=request_headers)

        assert response.status_code == 200
        assert response.json() == expected_response

    @pytest.mark.parametrize(
        "headers,expected_status,expected_data",
        [
            (
                {},
                HTTPStatus.BAD_REQUEST,
                {"error": "Required header 'X-Factory-Header' is missing", "header": "X-Factory-Header"},
            ),
            ({"X-Factory-Header": "factory_value"}, HTTPStatus.OK, {"X-Factory-Header": "factory_value"}),
        ],
    )
    def test_headers_middleware_factory(self, create_client, headers, expected_status, expected_data):
        config = HeadersConfig(rules=[HeaderRule("X-Factory-Header", required=True)])
        client = create_client(config)

        response = client.get("/", headers=headers)
        assert response.status_code == expected_status
        assert response.json() == expected_data

    @pytest.mark.parametrize("custom_status", [None, HTTPStatus.UNAUTHORIZED])
    def test_missing_required_header(self, create_client, custom_status):
        header_opts = {"required": True}
        if custom_status:
            header_opts["error_status_missing"] = custom_status

        config = HeadersConfig()
        config.add_header("X-Required-Header", **header_opts)

        client = create_client(config)

        response = client.get("/")

        expected_status = custom_status or HTTPStatus.BAD_REQUEST
        expected_data = {
            "error": "Required header 'X-Required-Header' is missing",
            "header": "X-Required-Header",
        }
        assert response.status_code == expected_status
        assert response.json() == expected_data

    @pytest.mark.parametrize(
        "header_value,is_valid",
        [
            ("123", True),
            ("abc", False),
        ],
    )
    def test_header_with_validator(self, create_client, header_value, is_valid):
        config = HeadersConfig()
        config.add_header("X-Numeric-Header", validator=is_numeric)

        client = create_client(config)

        response = client.get("/", headers={"X-Numeric-Header": header_value})

        if is_valid:
            assert response.status_code == 200
            assert response.json() == {"X-Numeric-Header": header_value}
        else:
            assert response.status_code == HTTPStatus.BAD_REQUEST
            assert response.json() == {
                "error": f"Header 'X-Numeric-Header' has invalid value: {header_value}",
                "header": "X-Numeric-Header",
            }

    @pytest.mark.parametrize(
        "sent_header,expected_key",
        [
            ("x-case-header", "X-Case-Header"),
            ("X-CASE-HEADER", "X-Case-Header"),
        ],
    )
    def test_case_insensitive_headers(self, create_client, sent_header, expected_key):
        config = HeadersConfig()
        config.add_header("X-Case-Header")

        client = create_client(config)

        response = client.get("/", headers={sent_header: "case_value"})
        assert response.status_code == 200
        assert response.json() == {expected_key: "case_value"}

    @pytest.mark.parametrize(
        "header_name,header_config,request_headers,expected_status,expected_error",
        [
            (
                "X-Missing-Custom-Status",
                {"required": True, "error_status_missing": HTTPStatus.UNAUTHORIZED},
                {},
                HTTPStatus.UNAUTHORIZED,
                {"error": "Required header 'X-Missing-Custom-Status' is missing", "header": "X-Missing-Custom-Status"},
            ),
            (
                "X-Invalid-Custom-Status",
                {"validator": lambda v: v == "valid", "error_status_invalid": HTTPStatus.FORBIDDEN},
                {"X-Invalid-Custom-Status": "invalid"},
                HTTPStatus.FORBIDDEN,
                {
                    "error": "Header 'X-Invalid-Custom-Status' has invalid value: invalid",
                    "header": "X-Invalid-Custom-Status",
                },
            ),
        ],
    )
    def test_custom_status_codes(
        self, create_client, header_name, header_config, request_headers, expected_status, expected_error
    ):
        config = HeadersConfig()
        config.add_header(header_name, **header_config)

        client = create_client(config)

        response = client.get("/", headers=request_headers)
        assert response.status_code == expected_status
        assert response.json() == expected_error
