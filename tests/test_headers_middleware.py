import pytest
from http import HTTPStatus
from typing import Any, Callable

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
def create_client(request: pytest.FixtureRequest) -> Callable[[HeadersConfig], FastAPITestClient | LitestarTestClient]:
    def factory(config: HeadersConfig) -> FastAPITestClient | LitestarTestClient:
        if request.param == "fastapi":
            fastapi_app: FastAPI = FastAPI()

            @fastapi_app.get("/")
            def read_headers() -> dict[str, Any]:
                return dict(http_request_context)

            fastapi_app.add_middleware(HeadersMiddleware, config=config)
            client: FastAPITestClient | LitestarTestClient = FastAPITestClient(fastapi_app)
        else:  # litestar

            @get("/")
            async def read_headers() -> dict[str, Any]:
                return dict(http_request_context)

            litestar_app = Litestar(
                route_handlers=[read_headers],
                middleware=[DefineMiddleware(HeadersMiddleware, config=config)],
            )
            client = LitestarTestClient(litestar_app)

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
    def test_successful_header_processing(
        self,
        create_client: Callable[[HeadersConfig], FastAPITestClient | LitestarTestClient],
        header_config: dict[str, Any],
        request_headers: dict[str, str],
        expected_response: dict[str, str],
    ) -> None:
        rules = [HeaderRule(name=name, **opts) for name, opts in header_config.items()]
        config = HeadersConfig(rules=rules)
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
    def test_headers_middleware_factory(
        self,
        create_client: Callable[[HeadersConfig], FastAPITestClient | LitestarTestClient],
        headers: dict[str, str],
        expected_status: HTTPStatus,
        expected_data: dict[str, Any],
    ) -> None:
        config = HeadersConfig(rules=[HeaderRule("X-Factory-Header", required=True)])
        client = create_client(config)

        response = client.get("/", headers=headers)
        assert response.status_code == expected_status
        assert response.json() == expected_data

    @pytest.mark.parametrize("custom_status", [None, HTTPStatus.UNAUTHORIZED])
    def test_missing_required_header(
        self,
        create_client: Callable[[HeadersConfig], FastAPITestClient | LitestarTestClient],
        custom_status: HTTPStatus | None,
    ) -> None:
        header_opts: dict[str, Any] = {"required": True}
        if custom_status:
            header_opts["error_status_missing"] = custom_status

        rules = [HeaderRule("X-Required-Header", **header_opts)]
        config = HeadersConfig(rules=rules)
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
    def test_header_with_validator(
        self,
        create_client: Callable[[HeadersConfig], FastAPITestClient | LitestarTestClient],
        header_value: str,
        is_valid: bool,
    ) -> None:
        rules = [HeaderRule("X-Numeric-Header", validator=is_numeric)]
        config = HeadersConfig(rules=rules)
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
    def test_case_insensitive_headers(
        self,
        create_client: Callable[[HeadersConfig], FastAPITestClient | LitestarTestClient],
        sent_header: str,
        expected_key: str,
    ) -> None:
        rules = [HeaderRule("X-Case-Header")]
        config = HeadersConfig(rules=rules)
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
        self,
        create_client: Callable[[HeadersConfig], FastAPITestClient | LitestarTestClient],
        header_name: str,
        header_config: dict[str, Any],
        request_headers: dict[str, str],
        expected_status: HTTPStatus,
        expected_error: dict[str, Any],
    ) -> None:
        rules = [HeaderRule(header_name, **header_config)]
        config = HeadersConfig(rules=rules)
        client = create_client(config)

        response = client.get("/", headers=request_headers)
        assert response.status_code == expected_status
        assert response.json() == expected_error
