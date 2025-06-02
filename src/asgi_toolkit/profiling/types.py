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


@dataclass
class ReportOutputFile:
    filepath: Path
    type: Literal["file"] = "file"


@dataclass
class ReportOutputLogger:
    logger: logging.Logger
    type: Literal["logger"] = "logger"


@dataclass
class ReportOutputResponse:
    type: Literal["response"]


ReportOutput = ReportOutputFile | ReportOutputLogger | ReportOutputResponse
