import cProfile
import io
import pstats

from asgi_toolkit.profiling.types import Profiler


class CProfileProfiler(Profiler):
    def __init__(self) -> None:
        self._profiler = cProfile.Profile()

    def start(self) -> None:
        self._profiler.enable()

    def stop(self) -> None:
        self._profiler.disable()

    def report(self) -> str:
        s = io.StringIO()
        ps = pstats.Stats(self._profiler, stream=s).sort_stats("cumulative")
        ps.print_stats()
        return s.getvalue()
