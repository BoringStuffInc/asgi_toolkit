import hashlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient
from litestar import Litestar, get
from litestar.testing import TestClient as LitestarTestClient

from asgi_toolkit.etags import ETagMiddleware, etag_middleware


def simple_etag_generator(body: bytes) -> str:
    return hashlib.md5(body).hexdigest()


@pytest.fixture(params=["fastapi", "litestar"])
def client(request):
    match request.param:
        case "fastapi":
            app = FastAPI()

            @app.get("/")
            def read_root():
                return {"message": "hello world"}

            @app.get("/health")
            def health_check():
                return {"status": "ok"}

            ignore_paths = [("GET", "/health")]
            app.add_middleware(ETagMiddleware, etag_generator=simple_etag_generator, ignore_paths=ignore_paths)
            client = FastAPITestClient(app)
        case "litestar":

            @get("/", sync_to_thread=False)
            def read_root() -> dict:
                return {"message": "hello world"}

            @get("/health", sync_to_thread=False)
            def health_check() -> dict:
                return {"status": "ok"}

            ignore_paths = [("GET", "/health")]
            app = Litestar(
                route_handlers=[read_root, health_check],
                middleware=[etag_middleware(simple_etag_generator, ignore_paths=ignore_paths)],
            )
            client = LitestarTestClient(app)
    return client


@pytest.fixture(params=["fastapi", "litestar"])
def client_with_counter(request):
    counter = {"value": 0}
    if request.param == "fastapi":
        app = FastAPI()

        @app.get("/")
        def read_root():
            counter["value"] += 1
            return {"message": f"hello world {counter['value']}"}

        app.add_middleware(ETagMiddleware, etag_generator=simple_etag_generator)
        client = FastAPITestClient(app)
    else:  # litestar

        @get("/", sync_to_thread=False)
        def read_root() -> dict:
            counter["value"] += 1
            return {"message": f"hello world {counter['value']}"}

        app = Litestar(route_handlers=[read_root], middleware=[etag_middleware(simple_etag_generator)])
        client = LitestarTestClient(app)
    return client


def assert_response_success(response, expected_status: int = 200):
    assert response.status_code == expected_status


def assert_etag_present(response, expected_etag: str | None = None):
    assert "etag" in response.headers
    if expected_etag:
        assert response.headers["etag"] == expected_etag


def assert_etag_absent(response):
    assert "etag" not in response.headers


def assert_not_modified_response(response):
    assert response.status_code == 304
    assert response.content == b""


def assert_precondition_failed_response(response):
    assert response.status_code == 412
    assert response.content == b""


class TestETagMiddleware:
    def test_etag_generation(self, client):
        response = client.get("/")
        assert_response_success(response)
        expected_etag = hashlib.md5(response.content).hexdigest()
        assert_etag_present(response, expected_etag)

    def test_if_none_match_not_modified(self, client):
        response = client.get("/")
        etag = response.headers["etag"]

        response = client.get("/", headers={"If-None-Match": etag})
        assert_not_modified_response(response)

    def test_if_none_match_modified(self, client):
        etag = "mumbo-jumbo"

        response = client.get("/", headers={"If-None-Match": etag})
        assert_response_success(response)
        assert_etag_present(response)
        assert response.headers["etag"] != etag

    def test_if_match_precondition_failed(self, client_with_counter):
        response = client_with_counter.get("/")
        etag = response.headers["etag"]

        response = client_with_counter.get("/", headers={"If-Match": etag})
        assert_precondition_failed_response(response)

    def test_if_match_success(self, client):
        response = client.get("/")
        etag = response.headers["etag"]

        response = client.get("/", headers={"If-Match": etag})
        assert_response_success(response)
        assert_etag_present(response)

    def test_ignore_paths(self, client):
        response = client.get("/")
        assert_response_success(response)
        assert_etag_present(response)

        response = client.get("/health")
        assert_response_success(response)
        assert_etag_absent(response)

    def test_non_http_requests_passthrough(self, client):
        response = client.get("/")
        assert_response_success(response)


class TestETagMiddlewareFactory:
    def test_factory_basic_functionality(self):
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"message": "hello world"}

        app.add_middleware(ETagMiddleware, etag_generator=simple_etag_generator)
        client = FastAPITestClient(app)

        response = client.get("/")
        assert_response_success(response)
        assert_etag_present(response)

    def test_factory_with_ignore_paths(self):
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"message": "hello world"}

        @app.get("/health")
        def health_check():
            return {"status": "ok"}

        ignore_paths = [("GET", "/health")]
        app.add_middleware(ETagMiddleware, etag_generator=simple_etag_generator, ignore_paths=ignore_paths)
        client = FastAPITestClient(app)

        response = client.get("/")
        assert_response_success(response)
        assert_etag_present(response)

        response = client.get("/health")
        assert_response_success(response)
        assert_etag_absent(response)
