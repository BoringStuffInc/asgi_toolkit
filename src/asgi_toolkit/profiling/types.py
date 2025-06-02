import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


class Profiler(Protocol):
    def start(self) -> None:
        """Starts the profiler."""

    def stop(self) -> None:
        """Stops the profiler."""

    def report(self) -> str:
        """Generates and returns a profiling report as a string."""


@dataclass(slots=True, frozen=True)
class ReportOutputFile:
    filepath: Path
    type: Literal["file"] = "file"


@dataclass(slots=True, frozen=True)
class ReportOutputLogger:
    logger: logging.Logger
    type: Literal["logger"] = "logger"


@dataclass(slots=True, frozen=True)
class ReportOutputResponse:
    type: Literal["response"]


ReportOutput = ReportOutputFile | ReportOutputLogger | ReportOutputResponse
