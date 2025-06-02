"""Lifespan protocol message types for ASGI.

This module defines ASGI lifespan protocol types for handling application
startup and shutdown events in ASGI applications.
"""

from typing import TypedDict, Literal, Required, NotRequired


class LifespanScope(TypedDict):
    type: Literal["lifespan"]
    asgi: Required[dict[str, str]]
    state: NotRequired[dict[str, object]]


class LifespanStartupMessage(TypedDict):
    type: Literal["lifespan.startup"]


class LifespanShutdownMessage(TypedDict):
    type: Literal["lifespan.shutdown"]


class LifespanStartupCompleteMessage(TypedDict):
    type: Literal["lifespan.startup.complete"]


class LifespanStartupFailedMessage(TypedDict):
    type: Literal["lifespan.startup.failed"]
    message: NotRequired[str]


class LifespanShutdownCompleteMessage(TypedDict):
    type: Literal["lifespan.shutdown.complete"]


class LifespanShutdownFailedMessage(TypedDict):
    type: Literal["lifespan.shutdown.failed"]
    message: NotRequired[str]


LifespanMessage = LifespanStartupMessage | LifespanShutdownMessage
LifespanResponseMessage = (
    LifespanStartupCompleteMessage
    | LifespanStartupFailedMessage
    | LifespanShutdownCompleteMessage
    | LifespanShutdownFailedMessage
)
