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
etag_config = ETagConfig(
    etag_generator=generate_etag,
    ignore_paths=[("POST", "/webhook")]
)

app.add_middleware(ETagMiddleware, config=etag_config)
```

### Header Middleware

```python
from fastapi import FastAPI
from asgi_toolkit.headers import HeadersMiddleware, HeadersConfig, HeaderRule

headers_config = HeadersConfig(
    rules=[
        HeaderRule(
            name="x-api-key", 
            required=True, 
            validator=lambda x: len(x) == 32
        )
    ]
)

app = FastAPI()
app.add_middleware(HeadersMiddleware, config=headers_config)
```

### Rate Limiting

```python
from fastapi import FastAPI
from asgi_toolkit.rate_limiting import RateLimitMiddleware
from asgi_toolkit.rate_limiting.backends import InMemoryBackend

from asgi_toolkit.rate_limiting import RateLimitConfig, PolicyConfig

rate_limit_config = RateLimitConfig(
    default_limit=100,  # Default: 100 requests
    default_window=60,  # Default: per 60 seconds
    policy_overrides={
        "/": PolicyConfig(limit=10, window=60),  # 10 requests per minute
        "/protected": PolicyConfig(limit=5, window=60)  # 5 requests per minute
    },
    activation_header='X-RateLimit-Enabled',  # Optional activation header
    whitelist={'127.0.0.1'}  # Optional IP whitelist
)

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
