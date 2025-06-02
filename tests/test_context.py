import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient
from litestar import Litestar, get
from litestar.testing import TestClient as LitestarTestClient
from typing import Any

from asgi_toolkit.context import (
    ContextMiddleware,
    RequestContextException,
    http_request_context,
    new_context,
)


def assert_context_value(key: str, expected_value: str):
    assert http_request_context[key] == expected_value
    assert http_request_context.get(key) == expected_value


def assert_context_empty():
    assert len(http_request_context) == 0


def assert_response_success(response, expected_data: dict):
    assert response.status_code == 200
    assert response.json() == expected_data


class TestContextBasicOperations:
    def test_context_outside_request_raises_exception(self):
        with pytest.raises(RequestContextException, match="No request context available"):
            _ = http_request_context["key"]

    def test_context_setting_outside_request_raises_exception(self):
        with pytest.raises(RequestContextException, match="No request context available"):
            http_request_context["key"] = "value"

    def test_context_with_new_context_manager(self):
        with new_context():
            http_request_context["key"] = "value"
            assert_context_value("key", "value")
            assert http_request_context.get("missing", "default") == "default"

    def test_context_dict_operations(self):
        with new_context():
            http_request_context["key"] = "value"
            assert_context_value("key", "value")

            assert "key" in http_request_context
            assert "missing" not in http_request_context

            assert http_request_context.get("missing", "default") == "default"

            result = http_request_context.setdefault("new_key", "new_value")
            assert result == "new_value"
            assert http_request_context["new_key"] == "new_value"

            http_request_context["another"] = "another_value"
            assert set(http_request_context.keys()) == {"key", "new_key", "another"}
            assert "value" in http_request_context.values()
            assert ("key", "value") in http_request_context.items()

            assert len(http_request_context) == 3
            http_request_context.clear()
            assert_context_empty()


class TestContextMiddleware:
    @pytest.fixture(params=["fastapi", "litestar"])
    def client(self, request):
        request_counter = {"count": 0}

        match request.param:
            case "fastapi":
                app = FastAPI()

                @app.get("/")
                def read_root():
                    http_request_context["test_key"] = "test_value"
                    return {"value": http_request_context["test_key"]}

                @app.get("/set/{value}")
                def set_value(value: str):
                    request_counter["count"] += 1
                    http_request_context["request_id"] = request_counter["count"]
                    http_request_context["value"] = value
                    return {"request_id": http_request_context["request_id"], "value": http_request_context["value"]}

                @app.get("/get")
                def get_value():
                    return {
                        "request_id": http_request_context.get("request_id"),
                        "value": http_request_context.get("value"),
                    }

                app.add_middleware(ContextMiddleware)
                client = FastAPITestClient(app)
            case "litestar":

                @get("/", sync_to_thread=False)
                def read_root() -> dict:
                    http_request_context["test_key"] = "test_value"
                    return {"value": http_request_context["test_key"]}

                @get("/set/{value:str}", sync_to_thread=False)
                def set_value(value: str) -> dict[str, Any]:
                    request_counter["count"] += 1
                    http_request_context["request_id"] = request_counter["count"]
                    http_request_context["value"] = value
                    return {"request_id": http_request_context["request_id"], "value": http_request_context["value"]}

                @get("/get", sync_to_thread=False)
                def get_value() -> dict[str, Any]:
                    return {
                        "request_id": http_request_context.get("request_id"),
                        "value": http_request_context.get("value"),
                    }

                app = Litestar(route_handlers=[read_root, set_value, get_value], middleware=[ContextMiddleware])
                client = LitestarTestClient(app)
        return client

    def test_context_middleware_basic_functionality(self, client):
        response = client.get("/")
        assert_response_success(response, {"value": "test_value"})

    def test_context_isolation_between_requests(self, client):
        response1 = client.get("/set/first")
        assert_response_success(response1, {"request_id": 1, "value": "first"})

        response2 = client.get("/set/second")
        assert_response_success(response2, {"request_id": 2, "value": "second"})

        response3 = client.get("/get")
        assert_response_success(response3, {"request_id": None, "value": None})

    def test_context_exception_message(self):
        with pytest.raises(RequestContextException) as exc_info:
            _ = http_request_context["key"]

        error_message = str(exc_info.value)
        assert "No request context available" in error_message
        assert "ContextMiddleware" in error_message
        assert "add_middleware" in error_message


class TestNewContextManager:
    def test_new_context_cleanup(self):
        with pytest.raises(ValueError):
            with new_context():
                http_request_context["key"] = "value"
                assert_context_value("key", "value")
                raise ValueError("test error")

        with pytest.raises(RequestContextException):
            _ = http_request_context["key"]
