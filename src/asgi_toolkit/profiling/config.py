"""Configuration classes for profiling middleware."""

from dataclasses import dataclass
from typing import Optional

from asgi_toolkit.profiling.types import Profiler, ReportOutput


@dataclass(slots=True, frozen=True)
class ProfilingConfig:
    """Configuration for profiling middleware."""

    profiler: Profiler
    report_output: ReportOutput

    activation_query_param: Optional[str] = None
    activation_header: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.activation_query_param and not self.activation_header:
            raise ValueError("At least one of activation_query_param or activation_header must be provided.")
