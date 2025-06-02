# ASGI Toolkit

A middleware toolkit for Python web applications.

## Features

- Context Management: Request-scoped data storage
- ETag Support: HTTP caching middleware
- Header Validation: Robust header processing
- Type-Safe ASGI Protocols
- Rate Limiting: Request rate control
- Framework Agnostic

## Installation

```bash
pip install asgi-toolkit
```

## Usage Examples

### Context Management

```python
from fastapi import FastAPI
from asgi_toolkit.context import ContextMiddleware, http_request_context

app = FastAPI()
app.add_middleware(ContextMiddleware)

@app.get("/")
async def root():
    http_request_context["custom_data"] = "Hello, World!"
    return {"message": http_request_context["custom_data"]}
```

### ETag Middleware

```python
from fastapi import FastAPI
from asgi_toolkit.etags import ETagMiddleware

def generate_etag(body: bytes) -> str:
    return f'"{hashlib.md5(body).hexdigest()}"'

app = FastAPI()
app.add_middleware(
    ETagMiddleware,
    etag_generator=generate_etag,
    ignore_paths=[("POST", "/webhook")]
)
```

### Header Middleware

```python
from fastapi import FastAPI
from asgi_toolkit.headers import HeadersMiddleware, HeadersConfig

headers_config = (
    HeadersConfig()
    .add_header(
        "x-api-key", 
        required=True, 
        validator=lambda x: len(x) == 32
    )
)

app = FastAPI()
app.add_middleware(HeadersMiddleware, config=headers_config)
```

### Rate Limiting

```python
from fastapi import FastAPI
from asgi_toolkit.rate_limiting import RateLimitMiddleware
from asgi_toolkit.rate_limiting.backends import InMemoryBackend

rate_limit_config = {
    "/": {"rate": "10/minute"},
    "/protected": {"rate": "5/minute"}
}

app = FastAPI()
app.add_middleware(
    RateLimitMiddleware, 
    backend=InMemoryBackend(),
    config=rate_limit_config
)
```

## Compatibility

- Python 3.10+
- Works with FastAPI, Litestar, Starlette, and other ASGI frameworks

## License

MIT License
