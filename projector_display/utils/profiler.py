"""
Performance profiler for projector display server.

Lightweight frame-level and command-level timing instrumentation
designed for diagnosing latency on resource-constrained hardware
like Raspberry Pi.

Usage:
    profiler = FrameProfiler(interval=5.0)

    # In render loop:
    profiler.begin_frame()
    do_clear()
    profiler.mark("clear")
    do_snapshots()
    profiler.mark("snapshot")
    ...
    profiler.end_frame()

    # In command handler:
    profiler.record_command("update_position", duration_s)
"""

import time
import collections
from typing import Dict, Optional

from projector_display.utils.logging import get_logger

logger = get_logger(__name__)


class _Stats:
    """Rolling statistics tracker using a fixed-size deque."""

    __slots__ = ("_values", "_sorted_dirty")

    def __init__(self, window: int = 300):
        self._values = collections.deque(maxlen=window)
        self._sorted_dirty = True

    def add(self, value: float):
        self._values.append(value)
        self._sorted_dirty = True

    @property
    def count(self) -> int:
        return len(self._values)

    @property
    def min(self) -> float:
        return min(self._values) if self._values else 0.0

    @property
    def max(self) -> float:
        return max(self._values) if self._values else 0.0

    @property
    def avg(self) -> float:
        return sum(self._values) / len(self._values) if self._values else 0.0

    @property
    def p95(self) -> float:
        if not self._values:
            return 0.0
        sorted_vals = sorted(self._values)
        idx = int(len(sorted_vals) * 0.95)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    def reset(self):
        self._values.clear()
        self._sorted_dirty = True


def _fmt_ms(seconds: float) -> str:
    """Format seconds as milliseconds string."""
    return f"{seconds * 1000:.2f}ms"


class FrameProfiler:
    """Collects per-frame section timings and logs periodic summaries.

    Sections are defined dynamically by calls to mark(name) between
    begin_frame() and end_frame(). Command processing times are
    recorded separately via record_command().

    Args:
        interval: Seconds between summary log outputs.
        window: Number of recent samples to keep for statistics.
    """

    def __init__(self, interval: float = 5.0, window: int = 300):
        self._interval = interval
        self._window = window

        # Frame section stats: section_name -> _Stats
        self._sections: Dict[str, _Stats] = {}
        self._section_order: list = []
        self._frame_stats = _Stats(window)

        # Command stats: command_name -> _Stats
        self._commands: Dict[str, _Stats] = {}

        # Current frame state
        self._frame_start: float = 0.0
        self._last_mark: float = 0.0

        # Reporting
        self._last_report: float = time.monotonic()
        self._frame_count: int = 0

    def begin_frame(self):
        """Call at the start of each render frame."""
        now = time.perf_counter()
        self._frame_start = now
        self._last_mark = now

    def mark(self, section: str):
        """Record time elapsed since last mark (or begin_frame) as a named section."""
        now = time.perf_counter()
        elapsed = now - self._last_mark
        self._last_mark = now

        if section not in self._sections:
            self._sections[section] = _Stats(self._window)
            self._section_order.append(section)
        self._sections[section].add(elapsed)

    def end_frame(self):
        """Call at the end of each render frame. Triggers periodic reporting."""
        now = time.perf_counter()
        total = now - self._frame_start
        self._frame_stats.add(total)
        self._frame_count += 1

        # Check if it's time to report
        mono_now = time.monotonic()
        if mono_now - self._last_report >= self._interval:
            self._report()
            self._last_report = mono_now

    def record_command(self, action: str, duration: float):
        """Record a command processing duration.

        Args:
            action: Command action name (e.g. "update_position")
            duration: Time in seconds
        """
        if action not in self._commands:
            self._commands[action] = _Stats(self._window)
        self._commands[action].add(duration)

    def _report(self):
        """Log a profiling summary."""
        if self._frame_stats.count == 0:
            return

        fps = self._frame_count / self._interval if self._interval > 0 else 0
        lines = [
            f"=== PROFILE ({self._frame_stats.count} frames, {fps:.1f} FPS) ===",
            f"  {'Section':<20s} {'avg':>8s} {'p95':>8s} {'max':>8s}",
        ]

        for name in self._section_order:
            s = self._sections[name]
            if s.count > 0:
                lines.append(
                    f"  {name:<20s} {_fmt_ms(s.avg):>8s} {_fmt_ms(s.p95):>8s} {_fmt_ms(s.max):>8s}"
                )

        s = self._frame_stats
        lines.append(
            f"  {'TOTAL':<20s} {_fmt_ms(s.avg):>8s} {_fmt_ms(s.p95):>8s} {_fmt_ms(s.max):>8s}"
        )

        # Command stats (top 5 by call count)
        if self._commands:
            cmd_items = sorted(self._commands.items(), key=lambda x: x[1].count, reverse=True)
            lines.append(f"  --- Commands ---")
            lines.append(f"  {'Command':<20s} {'n':>5s} {'avg':>8s} {'p95':>8s} {'max':>8s}")
            for name, cs in cmd_items[:5]:
                lines.append(
                    f"  {name:<20s} {cs.count:>5d} {_fmt_ms(cs.avg):>8s} "
                    f"{_fmt_ms(cs.p95):>8s} {_fmt_ms(cs.max):>8s}"
                )

        logger.info("\n".join(lines))

        # Reset frame counter for next interval
        self._frame_count = 0
